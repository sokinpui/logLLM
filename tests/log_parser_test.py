# Example usage (conceptual)
from logllm.utils.llm_model import GeminiModel # Or QwenModel
from logllm.utils.database import ElasticsearchDatabase
from logllm.utils.prompts_manager.prompts_manager import PromptsManager
from logllm.agents.log_parser_agent import LogParserAgent

# Initialize components
db = ElasticsearchDatabase()
pm = PromptsManager() # Assumes prompts.json is correctly populated
model = GeminiModel() # Or QwenModel

# Create the agent
parser_agent = LogParserAgent(model=model, db=db, prompts_manager=pm)

# Define the initial state - only the log group is strictly required
initial_state = {
    "log_group": "ssh" # Replace with the actual group you collected
}

# Run the agent
try:
    final_state = parser_agent.run(initial_state)
    print("Log Parsing Agent finished.")
    print(f"  Parsed Index: {final_state.get('parsed_index_name')}")
    print(f"  Successfully Parsed: {final_state.get('processed_count')}")
    print(f"  Parsing Errors: {final_state.get('error_count')}")
    if final_state.get('error_messages'):
        print("  Error Messages:")
        for msg in final_state['error_messages']:
            print(f"    - {msg}")

except ValueError as e:
    print(f"Error starting agent: {e}")
except Exception as e:
    print(f"An unexpected error occurred during agent execution: {e}")
