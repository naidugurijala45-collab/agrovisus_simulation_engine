# AGROVISUS_SIMULATION_ENGINE/app/models/rule_evaluator.py

import json
import logging
import os  # <<< FIX 1: IMPORT THE 'os' MODULE
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


class RuleEvaluator:
    def __init__(self, rule_file_path: str):
        self.rules = self._load_rules(rule_file_path)

    def _load_rules(self, file_path: str) -> List[Dict[str, Any]]:
        try:
            with open(file_path, "r") as f:
                rules_data = json.load(f)
            # Basic validation
            if "rules" not in rules_data or not isinstance(rules_data["rules"], list):
                logger.error(
                    "Rule file must have a top-level 'rules' key containing a list."
                )
                return []
            return rules_data["rules"]
        except FileNotFoundError:
            logger.error(f"Rule file not found at: {file_path}")
            return []
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from rule file: {file_path}")
            return []

    def _get_nested_value(self, data: Dict[str, Any], path: Tuple[str, ...]) -> Any:
        current_val = data
        for key in path:
            if isinstance(current_val, dict) and key in current_val:
                current_val = current_val[key]
            else:
                raise KeyError(key)
        return current_val

    def _check_condition(
        self, condition: Dict[str, Any], input_data: Dict[str, Any]
    ) -> bool:
        try:
            path_parts = tuple(condition["path"].split("."))
            data_value = self._get_nested_value(input_data, path_parts)
            operator = condition["operator"]
            threshold = condition["threshold"]

            if operator == "greater_than":
                return data_value > threshold
            elif operator == "less_than":
                return data_value < threshold
            elif operator == "equals":
                return data_value == threshold
            elif operator == "not_equals":
                return data_value != threshold
            elif operator == "in":
                return data_value in threshold
            elif operator == "not_in":
                return data_value not in threshold
            else:
                logger.warning(f"Unsupported operator '{operator}' in rule condition.")
                return False
        except KeyError as e:
            logger.debug(
                f"Data for '{e.args[0]}' (path: {path_parts}) not found or invalid in input_data. Condition fails."
            )
            return False
        except Exception as e:
            logger.error(f"Error evaluating condition {condition}: {e}")
            return False

    def evaluate_rules(self, input_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        triggered_rules = []
        for rule in self.rules:
            conditions = rule.get("conditions", [])
            # For "all" logic, all conditions must be true
            if all(self._check_condition(cond, input_data) for cond in conditions):
                # If all conditions are met, append the rule's result/recommendation
                triggered_rule_info = {
                    "rule_id": rule.get("id"),
                    "name": rule.get("name"),
                    **rule.get("result", {}),  # Merge the result dictionary
                }
                triggered_rules.append(triggered_rule_info)
        return triggered_rules


# Standalone test block
if __name__ == "__main__":
    print("\n--- Running Rule Evaluator Standalone Test (Decoupled) ---")

    # Configure a simple logger for the test to see debug messages
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s - %(message)s")

    # Create a temporary rule file for the test
    RULE_FILE_TEST = "test_rules_evaluator.json"
    test_rules = {
        "rules": [
            {
                "id": "NCLB_HighRisk_Decoupled",
                "name": "Northern Corn Leaf Blight High Risk (Decoupled Test)",
                "conditions": [
                    {
                        "path": "crop.stage",
                        "operator": "in",
                        "threshold": ["V6", "V8", "V10", "VT"],
                    },
                    {
                        "path": "weather.leaf_wetness_hours",
                        "operator": "greater_than",
                        "threshold": 6,
                    },
                    {
                        "path": "weather.humidity_percent",
                        "operator": "greater_than",
                        "threshold": 80,
                    },
                ],
                "result": {
                    "recommendation": "Scout for NCLB lesions.",
                    "severity": "High",
                },
            },
            {
                "id": "Drought_Stress_Decoupled",
                "name": "Potential Drought Stress (Decoupled Test)",
                "conditions": [
                    {
                        "path": "soil.fraction_awc",
                        "operator": "less_than",
                        "threshold": 0.3,
                    }
                ],
                "result": {
                    "recommendation": "Consider irrigation if forecast is dry.",
                    "severity": "Moderate",
                },
            },
        ]
    }
    with open(RULE_FILE_TEST, "w") as f:
        json.dump(test_rules, f, indent=2)
    print(f"Created test rule file: {RULE_FILE_TEST}\n")

    # --- Test Case 1: Favorable conditions for NCLB ---
    mock_input_favorable = {
        "weather": {
            ### FIX 2: CHANGE 'humidity' TO 'humidity_percent' TO MATCH THE RULE ###
            "humidity_percent": 85,
            "leaf_wetness_hours": 7.5,
        },
        "crop": {"stage": "V8"},
        "soil": {  # Add soil data so the test doesn't fail on missing keys
            "fraction_awc": 0.6
        },
    }
    print(f"Testing with NCLB favorable mock input: {mock_input_favorable}\n")
    evaluator = RuleEvaluator(rule_file_path=RULE_FILE_TEST)
    triggered = evaluator.evaluate_rules(mock_input_favorable)

    print("\n--- Results ---")
    if triggered:
        print("Triggered Rules:")
        for r in triggered:
            print(f"  - ID: {r['rule_id']}, Recommendation: {r['recommendation']}")
        # Assert that the correct rule was triggered
        assert triggered[0]["rule_id"] == "NCLB_HighRisk_Decoupled"
    else:
        print("No rules triggered.")

    # --- Test Case 2: Drought conditions ---
    mock_input_drought = {
        "weather": {"humidity_percent": 40, "leaf_wetness_hours": 1},
        "crop": {"stage": "V10"},
        "soil": {"fraction_awc": 0.25},
    }
    print(f"\nTesting with Drought mock input: {mock_input_drought}\n")
    triggered_drought = evaluator.evaluate_rules(mock_input_drought)

    print("\n--- Results ---")
    if triggered_drought:
        print("Triggered Rules:")
        for r in triggered_drought:
            print(f"  - ID: {r['rule_id']}, Recommendation: {r['recommendation']}")
        assert triggered_drought[0]["rule_id"] == "Drought_Stress_Decoupled"
    else:
        print("No rules triggered.")

    # Clean up the test file
    try:
        if os.path.exists(
            RULE_FILE_TEST
        ):  # This line now works because 'os' is imported
            os.remove(RULE_FILE_TEST)
            print(f"\nCleaned up test file: {RULE_FILE_TEST}")
    except Exception as e:
        print(f"An error occurred during cleanup: {e}")
