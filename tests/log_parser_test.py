# tests/test_log_parser_llm_output.py

import sys
import os
import json
from typing import List

# --- Path Setup (if needed) ---
# Adjust path if this script is outside the 'src' directory structure
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(
    os.path.join(script_dir, "..")
)  # Adjust if structure differs
src_path = os.path.join(project_root, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)
# -----------------------------

try:
    from logllm.utils.llm_model import GeminiModel, QwenModel  # Choose your model
    from logllm.utils.database import ElasticsearchDatabase
    from logllm.utils.prompts_manager.prompts_manager import PromptsManager
    from logllm.agents.log_parser_agent import (
        GrokPatternListSchema,
    )  # Import the schema
    from logllm.config import config as cfg
    from logllm.utils.logger import Logger  # Optional: for logging test steps
    from pygrok import Grok  # To validate patterns
except ImportError as e:
    print(f"Error importing necessary modules. Ensure PYTHONPATH is set correctly.")
    print(f"Import Error: {e}")
    sys.exit(1)

# --- Configuration ---
LOG_GROUP_TO_TEST = "ssh"  # <<< CHANGE THIS to the log group you want to test
SAMPLE_SIZE = 50  # Number of samples to fetch
PROMPT_KEY = (
    "logllm.agents.log_parser_agent.generate_grok_patterns"  # Key for the prompt
)

# --- Initialization ---
logger = Logger(name="LLM_Test", log_file="llm_test.log")
logger.info("--- Starting LLM Grok Pattern Generation Test ---")

try:
    db = ElasticsearchDatabase()
    if db.instance is None:
        logger.error("Failed to connect to Elasticsearch. Aborting test.")
        print("ERROR: Failed to connect to Elasticsearch.")
        sys.exit(1)

    pm = PromptsManager()  # Assumes default prompts.json or configure as needed
    # --- Choose Model ---
    # model = GeminiModel()
    model = GeminiModel()
    # --------------------

    logger.info(f"Initialized components. Using model: {model.__class__.__name__}")

except Exception as e:
    logger.error(f"Failed to initialize components: {e}", exc_info=True)
    print(f"ERROR: Failed to initialize components: {e}")
    sys.exit(1)

# --- 1. Fetch Log Samples ---
source_index = cfg.get_log_stroage_index(LOG_GROUP_TO_TEST)
logger.info(f"Fetching {SAMPLE_SIZE} samples from index '{source_index}'...")
sample_logs: List[str] = []
try:
    if not db.instance.indices.exists(index=source_index):
        logger.error(f"Source index '{source_index}' does not exist.")
        print(f"ERROR: Source index '{source_index}' does not exist.")
        sys.exit(1)

    samples_hits = db.random_sample(source_index, SAMPLE_SIZE)
    sample_logs = [hit["_source"]["content"] for hit in samples_hits]

    if not sample_logs:
        logger.warning(f"No logs found in index '{source_index}' to sample.")
        print(f"WARNING: No logs found in '{source_index}'. Cannot test LLM.")
        sys.exit(1)

    logger.info(f"Successfully fetched {len(sample_logs)} samples.")
    print(f"\n--- Fetched {len(sample_logs)} Sample Logs (First 5 shown) ---")
    for i, log in enumerate(sample_logs[:5]):
        print(f"  {i + 1}: {log.strip()}")
    if len(sample_logs) > 5:
        print("  ...")
    print("-----------------------------------------------\n")


except Exception as e:
    logger.error(f"Error fetching log samples: {e}", exc_info=True)
    print(f"ERROR: Error fetching log samples: {e}")
    sys.exit(1)

# --- 2. Get Prompt ---
logger.info(f"Retrieving prompt with key: '{PROMPT_KEY}'")
try:
    # Format the sample logs nicely for the prompt
    formatted_samples = "\n".join(f"- {line.strip()}" for line in sample_logs)
    # Use the PromptsManager - it will infer the key needs the 'sample_logs' variable
    prompt_template = pm.get_prompt(
        "logllm.agents.log_parser_agent.LogParserAgent.generate_parsing_rule",
        sample_logs=formatted_samples,
    )
    logger.info("Successfully retrieved and formatted prompt.")
    # print("\n--- Generated Prompt (Truncated) ---")
    # print(prompt_template[:500] + "...") # Print part of the prompt for verification
    # print("------------------------------------\n")

except (KeyError, ValueError) as e:
    logger.error(f"Error retrieving/formatting prompt '{PROMPT_KEY}': {e}")
    print(f"ERROR: Error retrieving/formatting prompt '{PROMPT_KEY}': {e}")
    sys.exit(1)
except RuntimeError as e:
    logger.error(
        f"PromptsManager runtime error (maybe called outside instance method?): {e}"
    )
    print(f"ERROR: PromptsManager runtime error: {e}. Make sure prompt key exists.")
    # If get_prompt fails because it wasn't called from an instance,
    # you might need to specify metadata explicitly here for testing:
    # prompt_template = pm.get_prompt(metadata=PROMPT_KEY, sample_logs=formatted_samples)
    # Handle potential errors from explicit metadata call too.
    sys.exit(1)


# --- 3. Call LLM ---
logger.info(
    f"Sending prompt to LLM ({model.__class__.__name__}) for Grok pattern generation..."
)
print(f"Querying LLM ({model.__class__.__name__})... This may take a moment.")
try:
    response: GrokPatternListSchema = model.generate(
        prompt_template, schema=GrokPatternListSchema
    )
    logger.info("Received response from LLM.")

except Exception as e:
    logger.error(f"Error during LLM call: {e}", exc_info=True)
    print(f"\nERROR: Error during LLM call: {e}")
    sys.exit(1)

# --- 4. Print & Validate Output ---
print("\n--- LLM Generated Grok Patterns ---")
if response and response.grok_patterns:
    print(f"Successfully received {len(response.grok_patterns)} patterns.")
    grok_valid = True
    for i, p_info in enumerate(response.grok_patterns):
        print(f"\nPattern #{i + 1}:")
        print(f"  Description: {p_info.pattern_description}")
        print(f"  Pattern:     {p_info.pattern_string}")

        # --- Optional: Validate Grok Pattern Syntax ---
        try:
            Grok(p_info.pattern_string)  # Try compiling the pattern
            print("  Syntax:      ✅ Valid")
        except Exception as grok_error:
            print(f"  Syntax:      ❌ INVALID - {grok_error}")
            grok_valid = False
        # --------------------------------------------

    if not grok_valid:
        logger.warning("One or more generated Grok patterns have invalid syntax.")
    else:
        logger.info("All generated Grok patterns have valid syntax.")

else:
    print("❌ LLM did not return patterns in the expected format.")
    logger.error(
        "LLM response was empty or not in the expected GrokPatternListSchema format."
    )
    # print("\nRaw LLM Response (if available):") # LLM might return None or raise error handled above
    # print(response)

print("------------------------------------\n")
logger.info("--- LLM Grok Pattern Generation Test Finished ---")
