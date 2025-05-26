# src/logllm/agents/timestamp_normalizer/__main__.py
import os
import sys

# Adjust path for imports
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
)

try:
    from src.logllm.utils.database import ElasticsearchDatabase  # type: ignore
    from . import TimestampNormalizerAgent  # Relative import for the agent
    from .states import TimestampNormalizerOrchestratorState  # Import state for typing
except ImportError as e:
    print(f"Error importing for __main__ in timestamp_normalizer: {e}")
    raise


def main():
    print("Running TimestampNormalizerAgent main test function...")

    db = ElasticsearchDatabase()
    if db.instance is None:
        print("Failed to connect to Elasticsearch. Aborting agent test.")
        return

    agent = TimestampNormalizerAgent(db=db)

    # --- Test Case 1: Normalize timestamps for a specific group ---
    print("\n--- Test Case 1: Normalize timestamps for 'test_group_1' ---")
    # Ensure 'test_group_1' and its parsed_log_test_group_1 index exist with some data
    # and some documents have a 'timestamp' field to normalize.
    # Example:
    # db.instance.index(index="parsed_log_test_group_1", document={"id": "1", "message": "Log line 1", "timestamp": "2023-10-26 10:00:00"})
    # db.instance.index(index="parsed_log_test_group_1", document={"id": "2", "message": "Log line 2", "timestamp": 1698314400}) # epoch
    # db.instance.index(index="group_infos", document={"group": "test_group_1", "files": ["file1.log"]}) # Ensure group exists in group_infos for "ALL" case later
    # db.instance.indices.refresh(index="parsed_log_test_group_1")
    # db.instance.indices.refresh(index="group_infos")

    try:
        # Create dummy data if it doesn't exist for testing
        if not db.instance.indices.exists(index="group_infos"):
            db.instance.indices.create(index="group_infos")
        db.instance.index(
            index="group_infos",
            id="tg1",
            document={"group": "test_group_1", "files": ["dummy.log"]},
        )
        db.instance.index(
            index="group_infos",
            id="tg2",
            document={"group": "test_group_2", "files": ["dummy2.log"]},
        )
        db.instance.indices.refresh(index="group_infos")

        if not db.instance.indices.exists(index="parsed_log_test_group_1"):
            db.instance.indices.create(index="parsed_log_test_group_1")
        db.instance.index(
            index="parsed_log_test_group_1",
            id="1",
            document={"message": "Event A", "timestamp": "2024-01-15T10:30:00Z"},
        )
        db.instance.index(
            index="parsed_log_test_group_1",
            id="2",
            document={"message": "Event B", "timestamp": 1705318800},
        )  # 2024-01-15 11:40:00 UTC
        db.instance.index(
            index="parsed_log_test_group_1",
            id="3",
            document={"message": "Event C", "some_other_field": "value"},
        )  # No timestamp
        db.instance.index(
            index="parsed_log_test_group_1",
            id="4",
            document={"message": "Event D", "timestamp": "invalid-date-string"},
        )

        if not db.instance.indices.exists(index="parsed_log_test_group_2"):
            db.instance.indices.create(index="parsed_log_test_group_2")
        db.instance.index(
            index="parsed_log_test_group_2",
            id="10",
            document={"message": "Event X", "timestamp": "2024-01-16 09:00:00 PST"},
        )
        db.instance.indices.refresh(index="parsed_log_test_group_1")
        db.instance.indices.refresh(index="parsed_log_test_group_2")

        print("Normalizing 'test_group_1'...")
        final_state_norm_tg1: TimestampNormalizerOrchestratorState = agent.run(
            action="normalize",
            target_groups=["test_group_1"],
            limit_per_group=5,  # Test limit
            batch_size=2,
        )
        print(f"Orchestrator status: {final_state_norm_tg1.get('orchestrator_status')}")
        print(
            f"Results for test_group_1: {final_state_norm_tg1.get('overall_group_results', {}).get('test_group_1')}"
        )

        # Verify in ES (optional manual check or add ES query here)
        # res = db.instance.get(index="parsed_log_test_group_1", id="1")
        # print(f"Doc 1 after norm: {res['_source']}")

    except Exception as e:
        print(f"Error during Test Case 1 (Normalize Specific Group): {e}")
        import traceback

        traceback.print_exc()

    # --- Test Case 2: Normalize timestamps for ALL groups ---
    print("\n--- Test Case 2: Normalize timestamps for ALL groups ---")
    try:
        final_state_norm_all: TimestampNormalizerOrchestratorState = agent.run(
            action="normalize", target_groups=None, batch_size=5  # Process all
        )
        print(f"Orchestrator status: {final_state_norm_all.get('orchestrator_status')}")
        for group, result in final_state_norm_all.get(
            "overall_group_results", {}
        ).items():
            print(f"  Group '{group}': {result}")
    except Exception as e:
        print(f"Error during Test Case 2 (Normalize All Groups): {e}")
        import traceback

        traceback.print_exc()

    # --- Test Case 3: Remove @timestamp field for a specific group ---
    print("\n--- Test Case 3: Remove '@timestamp' field for 'test_group_1' ---")
    try:
        final_state_remove_tg1: TimestampNormalizerOrchestratorState = agent.run(
            action="remove_field", target_groups=["test_group_1"], batch_size=2
        )
        print(
            f"Orchestrator status: {final_state_remove_tg1.get('orchestrator_status')}"
        )
        print(
            f"Results for test_group_1 (removal): {final_state_remove_tg1.get('overall_group_results', {}).get('test_group_1')}"
        )
        # Verify in ES (optional manual check)
        # res = db.instance.get(index="parsed_log_test_group_1", id="1")
        # print(f"Doc 1 after removal: {res['_source']}")

    except Exception as e:
        print(f"Error during Test Case 3 (Remove Field Specific Group): {e}")
        import traceback

        traceback.print_exc()

    # --- Test Case 4: Remove @timestamp field for ALL groups ---
    print("\n--- Test Case 4: Remove '@timestamp' field for ALL groups ---")
    try:
        final_state_remove_all: TimestampNormalizerOrchestratorState = agent.run(
            action="remove_field", target_groups=None, batch_size=5  # Process all
        )
        print(
            f"Orchestrator status: {final_state_remove_all.get('orchestrator_status')}"
        )
        for group, result in final_state_remove_all.get(
            "overall_group_results", {}
        ).items():
            print(f"  Group '{group}' (removal): {result}")
    except Exception as e:
        print(f"Error during Test Case 4 (Remove Field All Groups): {e}")
        import traceback

        traceback.print_exc()

    print("\nTimestampNormalizerAgent main test function finished.")


if __name__ == "__main__":
    main()
