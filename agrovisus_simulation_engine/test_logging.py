
import sys
import io
import logging
import os

# Force UTF-8 for stdout/stderr to handle emojis on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(
                os.path.join(OUTPUT_DIR, "test_log.log"), mode="w", encoding="utf-8"
            ),
        ],
    )

setup_logging()

logging.info("Testing logging with emojis: ✓ 🌾 🔄")
print("Testing print with emojis: ✓ 🌾 🔄")
