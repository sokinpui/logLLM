# Example usage (conceptual - adapt to your main workflow)
import sys
import os

# Adjust path if necessary, assuming running from project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from logllm.utils.llm_model import GeminiModel  # Or QwenModel
from logllm.utils.database import ElasticsearchDatabase
from logllm.utils.prompts_manager.prompts_manager import PromptsManager
from logllm.agents.log_parser_agent import DrainLogParserAgent
from logllm.utils.logger import Logger  # Import Logger


def run_parser(log_directory_path):
    logger = Logger()  # Initialize logger
    logger.info(f"Starting Drain Log Parser Agent for directory: {log_directory_path}")

    try:
        # Initialize components
        db = ElasticsearchDatabase()
        if not db.instance:
            logger.error("Failed to connect to Elasticsearch. Aborting.")
            return

        pm = PromptsManager()  # Assumes prompts.json is correctly populated
        model = GeminiModel()  # Or QwenModel

        # Create the agent
        parser_agent = DrainLogParserAgent(model=model, db=db, prompts_manager=pm)

        # Define the initial state
        initial_state = {
            "input_directory": log_directory_path
            # Other fields will be initialized in agent's run method
        }

        # Run the agent
        final_state = parser_agent.run(initial_state)

        logger.info("Drain Log Parser Agent finished execution.")
        print("\n--- Agent Execution Summary ---")
        print(f"Input Directory: {log_directory_path}")
        print(f"Log Group Derived: {final_state.get('log_group')}")
        print(f"Generated Log Format: {final_state.get('log_format')}")
        print(f"Target ES Index: {final_state.get('target_index')}")
        print(f"Files Parsed by Drain: {final_state.get('processed_files_count')}")
        print(f"Lines Inserted into ES: {final_state.get('inserted_lines_count')}")

        if final_state.get("error_messages"):
            print("\n--- Errors Encountered ---")
            # Use set to avoid duplicate messages if they occurred in multiple steps
            unique_errors = set(final_state["error_messages"])
            for i, msg in enumerate(unique_errors):
                print(f"  {i + 1}. {msg}")
        print("-" * 30)

    except ValueError as ve:
        logger.error(f"Configuration error: {ve}")
        print(f"Error: {ve}")
    except ImportError:
        logger.error("Import error. Check dependencies (logparser, pandas, etc.)")
        print("Import error. Make sure 'logparser' and 'pandas' are installed.")
    except Exception as e:
        logger.error(
            f"An unexpected error occurred during agent run: {e}", exc_info=True
        )
        print(f"An unexpected error occurred: {e}")


# --- Example Call ---
if __name__ == "__main__":
    # IMPORTANT: Replace with the ACTUAL path to your log directory containing .log files
    # Example: Assuming you have logs in './log_data/ssh/' relative to where you run this script
    path_to_logs = "./log"  # MODIFY THIS

    if not os.path.isdir(path_to_logs):
        print(
            f"Error: Log directory not found at '{path_to_logs}'. Please create it or modify the path."
        )
    else:
        run_parser(path_to_logs)
