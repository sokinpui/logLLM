# test_recursive_agent.py
import os
from logllm.utils.llm_model import GeminiModel
from logllm.utils.database import ElasticsearchDatabase
from logllm.agents.parser_agent import RecursiveDrainLogParserAgent


def test_recursive_agent():
    model = GeminiModel()
    db = ElasticsearchDatabase()

    test_dir = "logs/"  # Root of your log structure
    if not os.path.exists(test_dir):
        print(f"Test directory {test_dir} does not exist.")
        return

    agent = RecursiveDrainLogParserAgent(model, db)
    initial_state = {"input_directory": test_dir}
    result = agent.run(initial_state)

    print(f"Processed {len(result['processed_files'])} files:")
    for file_info in result["processed_files"]:
        print(
            f"Log: {file_info['path']}, CSV: {file_info['csv_path']}, Group: {file_info['group']}"
        )


if __name__ == "__main__":
    test_recursive_agent()
