# src/logllm/agents/error_summarizer/__main__.py
import os
import sys
from datetime import datetime, timedelta, timezone

# Adjust path for imports
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)

try:
    from src.logllm.config import config as cfg  # type: ignore
    from src.logllm.utils.database import ElasticsearchDatabase  # type: ignore
    from src.logllm.utils.llm_model import GeminiModel  # type: ignore

    from . import ErrorSummarizerAgent  # Relative import for the agent
    from .states import ErrorSummarizerAgentState  # Import state for typing
except ImportError as e:
    print(f"Error importing for __main__ in error_summarizer: {e}")
    raise


def main():
    print("Running ErrorSummarizerAgent main test function...")

    db = ElasticsearchDatabase()
    if not db.instance:
        print("Failed to connect to Elasticsearch. Aborting agent test.")
        return

    # Ensure you have an API key for GeminiModel
    if not os.environ.get("GENAI_API_KEY"):
        print("GENAI_API_KEY not set. Aborting as LLM calls will fail.")
        return

    # Create a GeminiModel instance (or your preferred LLM model)
    # The agent will create one by default if not passed, but explicit is good for testing
    llm_instance = GeminiModel(model_name=cfg.DEFAULT_LLM_MODEL_FOR_SUMMARY_GENERATION)

    agent = ErrorSummarizerAgent(db=db, llm_model_instance=llm_instance)

    # --- Test Case Parameters ---
    # Replace 'your_test_group' with a group that has parsed logs
    # and contains 'loglevel' and '@timestamp' fields.
    test_group_name = "test_group_error_logs"  # MAKE SURE THIS GROUP AND DATA EXISTS

    # Create dummy data for testing if it doesn't exist
    parsed_log_index = cfg.get_parsed_log_storage_index(test_group_name)
    if not db.instance.indices.exists(index=parsed_log_index):
        print(f"Creating dummy index {parsed_log_index} for testing")
        db.instance.indices.create(
            index=parsed_log_index,
            body={
                "mappings": {
                    "properties": {
                        "@timestamp": {"type": "date"},
                        "loglevel": {"type": "keyword"},
                        "message": {"type": "text", "analyzer": "standard"},
                        "original_line_number": {"type": "integer"},
                        "original_log_file_name": {"type": "keyword"},
                    }
                }
            },
        )
        # Add some sample error logs
        now = datetime.now(timezone.utc)
        logs_to_add = [
            {
                "@timestamp": (now - timedelta(minutes=10)).isoformat(),
                "loglevel": "ERROR",
                "message": "Null pointer exception at com.example.UserService:123",
                "original_line_number": 10,
                "original_log_file_name": "service.log",
            },
            {
                "@timestamp": (now - timedelta(minutes=9)).isoformat(),
                "loglevel": "ERROR",
                "message": "Failed to connect to database db01.",
                "original_line_number": 11,
                "original_log_file_name": "connector.log",
            },
            {
                "@timestamp": (now - timedelta(minutes=8)).isoformat(),
                "loglevel": "WARN",
                "message": "High memory usage detected: 90%",
                "original_line_number": 12,
                "original_log_file_name": "monitor.log",
            },
            {
                "@timestamp": (now - timedelta(minutes=7)).isoformat(),
                "loglevel": "ERROR",
                "message": "Null pointer exception at com.example.OrderService:45",
                "original_line_number": 13,
                "original_log_file_name": "service.log",
            },
            {
                "@timestamp": (now - timedelta(minutes=6)).isoformat(),
                "loglevel": "INFO",
                "message": "User logged in successfully.",
                "original_line_number": 14,
                "original_log_file_name": "auth.log",
            },
            {
                "@timestamp": (now - timedelta(minutes=5)).isoformat(),
                "loglevel": "ERROR",
                "message": "Database connection timeout on db01.",
                "original_line_number": 15,
                "original_log_file_name": "connector.log",
            },
            {
                "@timestamp": (now - timedelta(minutes=4)).isoformat(),
                "loglevel": "ERROR",
                "message": "Null pointer at com.example.UserService:128 - critical path",
                "original_line_number": 16,
                "original_log_file_name": "service.log",
            },
            {
                "@timestamp": (now - timedelta(minutes=3)).isoformat(),
                "loglevel": "WARN",
                "message": "Disk space running low on /var/log",
                "original_line_number": 17,
                "original_log_file_name": "system.log",
            },
        ]
        for i, log_doc in enumerate(logs_to_add):
            db.instance.index(index=parsed_log_index, id=str(i + 1), document=log_doc)
        db.instance.indices.refresh(index=parsed_log_index)
        print(f"Added {len(logs_to_add)} dummy logs to {parsed_log_index}")

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=1)

    start_time_iso = start_time.isoformat()
    end_time_iso = end_time.isoformat()

    error_levels_to_check = ["ERROR", "WARN"]  # Test with WARN too

    print(f"\\n--- Running ErrorSummarizerAgent for group '{test_group_name}' ---")
    print(f"Time window: {start_time_iso} to {end_time_iso}")
    print(f"Error levels: {error_levels_to_check}")

    try:
        final_state: ErrorSummarizerAgentState = agent.run(
            group_name=test_group_name,
            start_time_iso=start_time_iso,
            end_time_iso=end_time_iso,
            error_log_levels=error_levels_to_check,
            max_logs_to_process=100,  # Keep low for testing
            embedding_model_name="models/text-embedding-004",  # Or your preferred model
            # llm_model_for_summary is handled by agent's llm_instance
            clustering_params={
                "eps": 0.3,
                "min_samples": 1,
            },  # Lower min_samples for sparse test data
            sampling_params={
                "max_samples_per_cluster": 3,
                "max_samples_unclustered": 3,
            },
            target_summary_index="test_log_error_summaries_cli",  # Use a test index
        )

        print(f"\\n--- Agent Run Summary (CLI) ---")
        print(f"Overall Agent Status: {final_state.get('agent_status')}")

        if final_state.get("error_messages"):
            print("Agent Errors:")
            for err in final_state.get("error_messages", []):
                print(f"  - {err}")

        print(
            f"\\nRaw error logs fetched: {len(final_state.get('raw_error_logs', []))}"
        )

        if final_state.get("cluster_assignments") is not None:
            from collections import Counter

            print(
                f"Cluster assignments: {Counter(final_state['cluster_assignments']).most_common()}"
            )

        print(f"\\nProcessed Cluster Details & Summaries:")
        for i, cluster_detail in enumerate(
            final_state.get("processed_cluster_details", [])
        ):
            print(f"\\n  Cluster/Group {i+1}: {cluster_detail.get('cluster_label')}")
            print(f"    Total Logs: {cluster_detail.get('total_logs_in_cluster')}")
            print(
                f"    Time Range: {cluster_detail.get('cluster_time_range_start')} to {cluster_detail.get('cluster_time_range_end')}"
            )
            print(f"    Summary Generated: {cluster_detail.get('summary_generated')}")
            if cluster_detail.get("summary_output"):
                summary_data = cluster_detail.get("summary_output", {})
                print(f"      Summary: {summary_data.get('summary')}")
                print(f"      Potential Cause: {summary_data.get('potential_cause')}")
                print(f"      Keywords: {summary_data.get('keywords')}")
                print(
                    f"      Representative Log: {summary_data.get('representative_log_line')}"
                )
            if cluster_detail.get("summary_document_id_es"):
                print(
                    f"    Summary ES ID: {cluster_detail.get('summary_document_id_es')} in index {final_state.get('target_summary_index')}"
                )
            print(
                f"    Sampled Logs Used ({len(cluster_detail.get('sampled_log_messages_used',[]))}):"
            )
            for log_sample in cluster_detail.get("sampled_log_messages_used", [])[
                :2
            ]:  # Print first 2 samples
                print(f'      - \\"{log_sample.strip()}"')

        print(
            f"\\nTotal summaries stored in Elasticsearch: {len(final_state.get('final_summary_ids', []))}"
        )
        for es_id in final_state.get("final_summary_ids", []):
            print(f"  - Summary ES ID: {es_id}")

    except Exception as e:
        print(f"An critical error occurred during the agent run: {e}")
        import traceback

        traceback.print_exc()

    print("\\nErrorSummarizerAgent main test function finished.")


if __name__ == "__main__":
    main()
