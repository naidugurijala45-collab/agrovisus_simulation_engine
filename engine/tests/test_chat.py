"""
Tests for the /api/chat endpoint (AI field advisor).

Uses unittest.mock to patch the Anthropic client so no real API calls
are made and no ANTHROPIC_API_KEY is required.
"""
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Make both the project root and engine available on sys.path, mirroring
# how backend/main.py sets up paths at runtime.
PROJECT_ROOT = Path(__file__).parent.parent.parent  # CropDiagnosisPlatform/
ENGINE_ROOT = PROJECT_ROOT / "engine"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(ENGINE_ROOT))

from fastapi.testclient import TestClient

# We import the chat router directly to avoid pulling in the full
# simulation/weather engine, which requires config files.
from backend.routers.chat import router, SYSTEM_PROMPT, ChatRequest, FieldContext
from fastapi import FastAPI

# Build a minimal test app with just the chat router
_app = FastAPI()
_app.include_router(router, prefix="/api/chat")
client = TestClient(_app)


# ── Fixtures ──────────────────────────────────────────────────────────────

SAMPLE_PAYLOAD = {
    "message": "Should I apply fungicide now?",
    "field_context": {
        "crop_type": "corn",
        "growth_stage": "V8",
        "state_code": "IL",
        "sim_days_run": 45,
        "final_yield_kg_ha": 6200,
        "triggered_alerts": [
            {
                "rule_name": "Gray Leaf Spot",
                "severity": "MODERATE",
                "yield_impact_percent": 8,
                "days_active": 12,
                "advisory": "Apply fungicide before infection reaches upper canopy",
            }
        ],
        "roi": {
            "recommendation_strength": "STRONG BUY",
            "revenue_at_risk_per_acre": 85,
            "roi_mid": 3.2,
        },
    },
}

MINIMAL_PAYLOAD = {
    "message": "How is my corn doing?",
    "field_context": {
        "crop_type": "corn",
        "growth_stage": "V4",
        "state_code": "IA",
        "sim_days_run": 20,
        "final_yield_kg_ha": 5000,
    },
}


def _make_mock_message(text: str):
    """Return a mock Anthropic Messages response with the given text."""
    content_block = MagicMock()
    content_block.text = text
    mock_msg = MagicMock()
    mock_msg.content = [content_block]
    return mock_msg


# ── Happy-path tests ───────────────────────────────────────────────────────


class TestChatHappyPath:
    def test_returns_200_with_reply(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("backend.routers.chat.anthropic.Anthropic") as MockClient:
                MockClient.return_value.messages.create.return_value = (
                    _make_mock_message("Yes, apply fungicide immediately given the Gray Leaf Spot alert.")
                )
                resp = client.post("/api/chat", json=SAMPLE_PAYLOAD)

        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data
        assert len(data["reply"]) > 0

    def test_reply_content_is_forwarded(self):
        expected = "Your V8 corn in IL is at risk. Apply fungicide now."
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("backend.routers.chat.anthropic.Anthropic") as MockClient:
                MockClient.return_value.messages.create.return_value = (
                    _make_mock_message(expected)
                )
                resp = client.post("/api/chat", json=SAMPLE_PAYLOAD)

        assert resp.json()["reply"] == expected

    def test_minimal_payload_no_alerts_no_roi(self):
        """Payload with no triggered_alerts and no roi should still work."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("backend.routers.chat.anthropic.Anthropic") as MockClient:
                MockClient.return_value.messages.create.return_value = (
                    _make_mock_message("Your V4 corn in IA looks healthy so far.")
                )
                resp = client.post("/api/chat", json=MINIMAL_PAYLOAD)

        assert resp.status_code == 200
        assert "reply" in resp.json()

    def test_claude_called_with_correct_model(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            with patch("backend.routers.chat.anthropic.Anthropic") as MockClient:
                mock_create = MockClient.return_value.messages.create
                mock_create.return_value = _make_mock_message("OK")
                client.post("/api/chat", json=SAMPLE_PAYLOAD)

                call_kwargs = mock_create.call_args.kwargs
                assert call_kwargs["model"] == "claude-haiku-4-5-20251001"

    def test_claude_called_with_system_prompt(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            with patch("backend.routers.chat.anthropic.Anthropic") as MockClient:
                mock_create = MockClient.return_value.messages.create
                mock_create.return_value = _make_mock_message("OK")
                client.post("/api/chat", json=SAMPLE_PAYLOAD)

                call_kwargs = mock_create.call_args.kwargs
                assert call_kwargs["system"] == SYSTEM_PROMPT

    def test_user_message_contains_field_context(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            with patch("backend.routers.chat.anthropic.Anthropic") as MockClient:
                mock_create = MockClient.return_value.messages.create
                mock_create.return_value = _make_mock_message("OK")
                client.post("/api/chat", json=SAMPLE_PAYLOAD)

                call_kwargs = mock_create.call_args.kwargs
                user_content = call_kwargs["messages"][0]["content"]
                assert "Field context:" in user_content
                assert "corn" in user_content

    def test_user_message_contains_farmer_question(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            with patch("backend.routers.chat.anthropic.Anthropic") as MockClient:
                mock_create = MockClient.return_value.messages.create
                mock_create.return_value = _make_mock_message("OK")
                client.post("/api/chat", json=SAMPLE_PAYLOAD)

                call_kwargs = mock_create.call_args.kwargs
                user_content = call_kwargs["messages"][0]["content"]
                assert "Question:" in user_content
                assert "Should I apply fungicide now?" in user_content


# ── Error-handling tests ───────────────────────────────────────────────────


class TestChatErrorHandling:
    def test_missing_api_key_returns_500(self):
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            resp = client.post("/api/chat", json=SAMPLE_PAYLOAD)

        assert resp.status_code == 500
        assert "ANTHROPIC_API_KEY" in resp.json()["detail"]

    def test_auth_error_returns_500(self):
        import anthropic as _anthropic

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "bad-key"}):
            with patch("backend.routers.chat.anthropic.Anthropic") as MockClient:
                MockClient.return_value.messages.create.side_effect = (
                    _anthropic.AuthenticationError(
                        message="invalid x-api-key",
                        response=MagicMock(status_code=401),
                        body={},
                    )
                )
                resp = client.post("/api/chat", json=SAMPLE_PAYLOAD)

        assert resp.status_code == 500

    def test_api_status_error_returns_502(self):
        import anthropic as _anthropic
        import httpx

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            with patch("backend.routers.chat.anthropic.Anthropic") as MockClient:
                # Build a response with the required request attribute set
                mock_request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
                mock_response = httpx.Response(
                    status_code=529,
                    content=b'{"type":"error","error":{"type":"overloaded_error"}}',
                    request=mock_request,
                )
                MockClient.return_value.messages.create.side_effect = (
                    _anthropic.APIStatusError(
                        message="overloaded",
                        response=mock_response,
                        body={"error": {"type": "overloaded_error"}},
                    )
                )
                resp = client.post("/api/chat", json=SAMPLE_PAYLOAD)

        assert resp.status_code == 502

    def test_missing_message_field_returns_422(self):
        bad_payload = dict(SAMPLE_PAYLOAD)
        bad_payload.pop("message")
        resp = client.post("/api/chat", json=bad_payload)
        assert resp.status_code == 422

    def test_missing_field_context_returns_422(self):
        resp = client.post("/api/chat", json={"message": "Hello?"})
        assert resp.status_code == 422


# ── Request model validation tests ────────────────────────────────────────


class TestChatRequestModel:
    def test_field_context_requires_crop_type(self):
        ctx = dict(SAMPLE_PAYLOAD["field_context"])
        ctx.pop("crop_type")
        resp = client.post("/api/chat", json={"message": "Q?", "field_context": ctx})
        assert resp.status_code == 422

    def test_triggered_alerts_default_to_empty_list(self):
        ctx = {
            "crop_type": "wheat",
            "growth_stage": "Tillering",
            "state_code": "KS",
            "sim_days_run": 30,
            "final_yield_kg_ha": 3800,
        }
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            with patch("backend.routers.chat.anthropic.Anthropic") as MockClient:
                MockClient.return_value.messages.create.return_value = (
                    _make_mock_message("Wheat looks fine.")
                )
                resp = client.post("/api/chat", json={"message": "Status?", "field_context": ctx})

        assert resp.status_code == 200

    def test_roi_is_optional(self):
        ctx = dict(SAMPLE_PAYLOAD["field_context"])
        ctx.pop("roi")
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            with patch("backend.routers.chat.anthropic.Anthropic") as MockClient:
                MockClient.return_value.messages.create.return_value = (
                    _make_mock_message("No ROI data but corn looks okay.")
                )
                resp = client.post("/api/chat", json={"message": "How?", "field_context": ctx})

        assert resp.status_code == 200


# ── System prompt content tests ────────────────────────────────────────────


class TestSystemPrompt:
    def test_system_prompt_mentions_agrovisus(self):
        assert "AgroVisus" in SYSTEM_PROMPT

    def test_system_prompt_word_limit(self):
        assert "120 words" in SYSTEM_PROMPT

    def test_system_prompt_advises_specificity(self):
        assert "crop" in SYSTEM_PROMPT.lower()
        assert "stage" in SYSTEM_PROMPT.lower()
