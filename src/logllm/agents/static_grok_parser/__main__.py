# src/logllm/agents/static_grok_parser/__main__.py
import os
import sys

# Adjust path to import from project root if necessary
# This assumes __main__.py is in static_grok_parser and needs to go up 3 levels for src
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)

try:
    from ...utils.database import ElasticsearchDatabase

    # The agent is now directly in the current package's __init__.py
    from . import (
        StaticGrokParserAgent,  # Use relative import for the agent from current package
    )
except ImportError as e:
    print(f"Error importing for __main__: {e}")
    print("PYTHONPATH:", os.environ.get("PYTHONPATH"))
    print("sys.path:", sys.path)
    raise


def main():
    print(
        "Running StaticGrokParserAgent (LangGraph refactored version) main test function..."
    )

    # Ensure Elasticsearch is running and accessible via cfg.ELASTIC_SEARCH_URL
    # Ensure grok_patterns.yaml is in the project root or path is correctly specified.
    # Assumes logs have been collected by your Collector agent.

    db = ElasticsearchDatabase()
    if db.instance is None:
        print(
            "Failed to connect to Elasticsearch. Aborting StaticGrokParserAgent test."
        )
        return

    # Path to grok_patterns.yaml relative to project root (where you run `python -m src.logllm...`)
    # Or an absolute path.
    # If __main__.py is in src/logllm/agents/static_grok_parser,
    # and grok_patterns.yaml is in project root:
    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
    )
    grok_yaml_path = os.path.join(project_root, "grok_patterns.yaml")

    if not os.path.exists(grok_yaml_path):
        print(f"ERROR: grok_patterns.yaml not found at expected path: {grok_yaml_path}")
        print("Please ensure the YAML file exists or update the path in __main__.py.")
        # Try a default relative path if the complex one fails (e.g., if running from project root directly)
        grok_yaml_path = "grok_patterns.yaml"
        if not os.path.exists(grok_yaml_path):
            print(f"Also not found at simple relative path: {grok_yaml_path}")
            return

    print(f"Using Grok patterns from: {grok_yaml_path}")
    agent = StaticGrokParserAgent(db=db, grok_patterns_yaml_path=grok_yaml_path)

    try:
        final_orchestrator_state = agent.run()
        print("\n--- Static Grok Parser Agent (LangGraph) Run Summary ---")
        print(
            f"Overall Orchestrator Status: {final_orchestrator_state.get('orchestrator_status')}"
        )

        if final_orchestrator_state.get("orchestrator_error_messages"):
            print("Orchestrator Errors:")
            for err in final_orchestrator_state.get("orchestrator_error_messages", []):
                print(f"  - {err}")

        print("\nGroup Processing Summaries:")
        for group_name, group_summary in final_orchestrator_state.get(
            "overall_group_results", {}
        ).items():
            print(f"  Group: {group_name}")
            print(f"    Status: {group_summary.get('group_status')}")
            if group_summary.get("group_error_messages"):
                print("    Group Errors:")
                for err in group_summary.get("group_error_messages", []):
                    print(f"      - {err}")

            files_summary = group_summary.get("files_processed_summary_this_run", {})
            num_files_processed_info = len(files_summary)
            num_total_files_in_group = len(
                group_summary.get("all_log_file_ids_in_group", [])
            )
            print(
                f"    Files with processing info this run: {num_files_processed_info} / {num_total_files_in_group} (total known files for group)"
            )

            # You can iterate through files_summary here for more detail if needed
            # for file_id, file_detail in files_summary.items():
            #     print(f"      File ID: {file_id}, Status: {file_detail.get('status_this_session')}")

    except Exception as e:
        print(f"An critical error occurred during the agent run: {e}")
        import traceback

        traceback.print_exc()

    print(
        "\nStaticGrokParserAgent (LangGraph refactored version) main test function finished."
    )


if __name__ == "__main__":
    main()
