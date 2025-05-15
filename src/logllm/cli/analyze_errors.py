# src/logllm/cli/analyze_errors.py (NEW FILE)
import argparse
import json
import sys

try:
    from ..agents.error_analysis_pipeline_agent import (
        ErrorAnalysisPipelineAgent,
        ErrorAnalysisPipelineState,
    )
    from ..config import config as cfg
    from ..data_schemas.error_analysis import ErrorSummarySchema  # For printing
    from ..utils.database import ElasticsearchDatabase
    from ..utils.llm_model import GeminiModel
    from ..utils.logger import Logger
    from ..utils.prompts_manager import PromptsManager
except ImportError as e:
    print(f"Error importing modules for 'analyze-errors' CLI: {e}", file=sys.stderr)
    sys.exit(1)

logger = Logger()


def handle_analyze_errors_run(args):
    logger.info(
        f"Executing analyze-errors run: group='{args.group}', time_window='{args.time_window}', levels='{args.log_levels}', max_initial='{args.max_initial_errors}'"
    )  # Added max_initial_errors to log
    print(f"Starting error analysis for group '{args.group}'...")

    try:
        db = ElasticsearchDatabase()
        if db.instance is None:
            print("Error: Could not connect to Elasticsearch.")
            logger.error("ES connection failed in handle_analyze_errors_run.")
            return

        json_file_path = getattr(args, "json", None) or (
            "prompts/test.json"
            if getattr(args, "test", False)
            else "prompts/prompts.json"
        )
        prompts_manager = PromptsManager(json_file=json_file_path)
        llm_model = GeminiModel()

        pipeline_agent = ErrorAnalysisPipelineAgent(
            db=db, llm_model=llm_model, prompts_manager=prompts_manager
        )

        must_clauses = []
        # Field name for log level - **MAKE THIS CONFIGURABLE OR VERIFY IT**
        # Let's assume it's "level.keyword" based on your Kibana screenshot,
        # but it could also be "log_level.keyword" if your Grok parsing created that.
        # The `es-parse` command's `ScrollGrokParserAgent` creates fields based on the Grok pattern.
        # If your Grok pattern is like `%{LOGLEVEL:level}`, then the field is `level`.
        # If your Grok pattern is like `%{LOGLEVEL:log_level}`, then the field is `log_level`.
        # The `.keyword` is usually added by Elasticsearch's default dynamic mapping for strings.

        # *** Key change area: Determine the correct field name for log level ***
        # For now, let's assume the Grok pattern used by `es-parse` outputted a field named "level".
        # If it outputted "log_level", change this.
        log_level_field_keyword = (
            "level.keyword"  # <<<< CHECK THIS AGAINST YOUR ACTUAL PARSED DATA
        )
        # log_level_field_keyword = "log_level.keyword" # Alternative if your Grok uses 'log_level'

        if args.log_levels:
            levels = [level.strip().lower() for level in args.log_levels.split(",")]
            logger.debug(
                f"Querying for log levels: {levels} on field '{log_level_field_keyword}'"
            )
            must_clauses.append({"terms": {log_level_field_keyword: levels}})
        else:
            # If no log levels are specified, what should happen?
            # Option A: Error out - "Please specify log levels"
            # Option B: Default to common error levels (current behavior via CLI default)
            # Option C: Match all if no levels specified (probably not desired for "error analysis")
            logger.warning(
                "No specific log levels provided for filtering, relying on CLI default or matching all if default is empty."
            )

        time_filter = {"range": {"@timestamp": {"gte": args.time_window, "lte": "now"}}}

        es_query = {
            "query": {
                "bool": {
                    "must": must_clauses,  # This will be empty if args.log_levels is empty AND no default logic
                    "filter": [time_filter],
                }
            },
            "size": args.max_initial_errors,
            # Fetch fields relevant for clustering and summarization.
            # Ensure these fields actually exist in your 'normalized_parsed_log_apache' index.
            "_source": [
                "message",
                "@timestamp",
                "level",
                "class_name",
                "thread_name",
            ],  # Added level, class_name, thread_name
            "sort": [{"@timestamp": "desc"}],  # Optional: sort by time
        }

        # If must_clauses is empty because no log levels were effectively specified,
        # the query will fetch all logs in the time window.
        # This might not be what's intended for an "error analyzer".
        if not must_clauses:
            logger.error(
                "The 'must_clauses' for log level filtering is empty. This will retrieve all logs in the time window. Please specify valid --log-levels."
            )
            # Optionally, you could prevent the query here if it's critical that levels are filtered.
            # For now, it will proceed but log this error.

        logger.debug(f"Constructed ES Query: {json.dumps(es_query, indent=2)}")

        initial_pipeline_state: ErrorAnalysisPipelineState = {
            "group_name": args.group,
            "es_query_for_errors": es_query,
            "clustering_params": {
                "method": args.clustering_method,
                "eps": args.dbscan_eps,
                "min_samples": args.dbscan_min_samples,
            },
            "sampling_params": {
                "max_samples_per_cluster": args.max_samples_per_cluster,
                "max_samples_unclustered": args.max_samples_unclustered,
            },
            # These will be populated by the graph
            "error_log_docs": [],
            "clusters": None,
            "current_cluster_index": 0,
            "current_samples_for_summary": [],
            "generated_summaries": [],
            "status_messages": [],
        }

        final_state = pipeline_agent.run(initial_pipeline_state)

        # ... (rest of the summary printing code remains the same) ...
        print("\n--- Error Analysis Pipeline Summary ---")
        print(f"Group: {args.group}")
        print("Status Messages:")
        for msg in final_state.get("status_messages", []):
            print(f"  - {msg}")

        print(
            f"\nGenerated Summaries ({len(final_state.get('generated_summaries',[]))}):"
        )
        if final_state.get("generated_summaries"):
            for summary_idx, summary_data in enumerate(
                final_state.get("generated_summaries", [])
            ):
                # summary_data is now the ErrorSummarySchema object
                print("-" * 20)
                print(f"  Summary {summary_idx + 1}:")
                print(f"    Category: {summary_data.error_category}")
                print(f"    Description: {summary_data.concise_description}")
                print(
                    f"    Original Count (Cluster/Batch): {summary_data.original_cluster_count}"
                )
        else:
            print("  (No summaries were generated)")

        print("\nAnalysis complete. Summaries stored in Elasticsearch (if any).")

    except Exception as e:
        logger.error(f"Critical error during analyze-errors run: {e}", exc_info=True)
        print(f"An error occurred: {e}")


def handle_analyze_errors_list(args):
    logger.info(
        f"Executing analyze-errors list: group='{args.group}', latest={args.latest}"
    )
    try:
        db = ElasticsearchDatabase()
        if db.instance is None:
            print("Error: Could not connect to Elasticsearch.")
            return

        query_body: Dict[str, Any] = {"sort": [{"analysis_timestamp": "desc"}]}
        if args.group:
            query_body["query"] = {"term": {"group_name.keyword": args.group}}
        else:
            query_body["query"] = {"match_all": {}}

        if args.latest:
            query_body["size"] = args.latest

        results = db.scroll_search(index=cfg.INDEX_ERROR_SUMMARIES, query=query_body)

        if not results:
            print("No error summaries found.")
            return

        print(f"\n--- Stored Error Summaries ({len(results)} entries) ---")
        for hit in results:
            summary_data = hit["_source"]
            try:
                # Validate against schema for consistent printing, or just print fields
                summary = ErrorSummarySchema.model_validate(summary_data)
                print("-" * 30)
                print(
                    f"Group: {summary.group_name} (Analyzed: {summary.analysis_timestamp})"
                )
                print(f"Category: {summary.error_category}")
                print(f"Description: {summary.concise_description}")
                print(f"Potential Causes: {', '.join(summary.potential_root_causes)}")
                print(f"Impact: {summary.estimated_impact}")
                print(f"Keywords: {', '.join(summary.suggested_keywords)}")
                if summary.original_cluster_count is not None:
                    print(
                        f"Original Logs Count (in cluster/batch): {summary.original_cluster_count}"
                    )
                print(f"Input Examples: {summary.num_examples_in_summary_input}")

            except Exception as p_err:
                logger.warning(
                    f"Could not parse summary from ES with Pydantic: {p_err}. Raw data: {summary_data}"
                )
                print(json.dumps(summary_data, indent=2))

    except Exception as e:
        logger.error(f"Error listing summaries: {e}", exc_info=True)
        print(f"An error occurred: {e}")


def register_analyze_errors_parser(subparsers):
    parser = subparsers.add_parser(
        "analyze-errors",
        help="Analyze and summarize error logs from Elasticsearch.",
        description="Filters, clusters (optional), samples, and uses LLM to summarize error logs.",
    )
    action_subparsers = parser.add_subparsers(
        dest="analyze_errors_action", required=True
    )

    # --- 'run' subcommand ---
    run_parser = action_subparsers.add_parser(
        "run", help="Run the error analysis pipeline."
    )
    run_parser.add_argument(
        "-g", "--group", type=str, required=True, help="Log group name to analyze."
    )
    run_parser.add_argument(
        "--time-window",
        type=str,
        default="now-24h",
        help="Time window for fetching errors (e.g., 'now-1h', 'now-7d').",
    )
    run_parser.add_argument(
        "--log-levels",
        type=str,
        default="ERROR,CRITICAL,FATAL",
        help="Comma-separated log levels to filter for.",
    )
    run_parser.add_argument(
        "--max-initial-errors",
        type=int,
        default=5000,
        help="Max error logs to fetch initially for analysis.",
    )

    # Clustering params
    run_parser.add_argument(
        "--clustering-method",
        type=str,
        default="embedding_dbscan",
        choices=["embedding_dbscan", "none"],
        help="Clustering method.",
    )
    run_parser.add_argument(
        "--dbscan-eps",
        type=float,
        default=cfg.DEFAULT_DBSCAN_EPS,
        help="DBSCAN epsilon parameter.",
    )
    run_parser.add_argument(
        "--dbscan-min-samples",
        type=int,
        default=cfg.DEFAULT_DBSCAN_MIN_SAMPLES,
        help="DBSCAN min_samples parameter.",
    )

    # Sampling params
    run_parser.add_argument(
        "--max-samples-per-cluster",
        type=int,
        default=cfg.DEFAULT_MAX_SAMPLES_PER_CLUSTER_FOR_SUMMARY,
        help="Max log samples from a cluster to feed LLM.",
    )
    run_parser.add_argument(
        "--max-samples-unclustered",
        type=int,
        default=cfg.DEFAULT_MAX_SAMPLES_UNCLUSTERED_FOR_SUMMARY,
        help="Max log samples if not clustered to feed LLM.",
    )

    run_parser.set_defaults(func=handle_analyze_errors_run)

    # --- 'list' subcommand ---
    list_parser = action_subparsers.add_parser(
        "list", help="List previously generated error summaries."
    )
    list_parser.add_argument(
        "-g", "--group", type=str, help="Filter summaries by group name."
    )
    list_parser.add_argument(
        "--latest", type=int, help="Show only the N latest summaries."
    )
    list_parser.set_defaults(func=handle_analyze_errors_list)
