# src/logllm/cli/analyze_errors.py
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from typing import List, Optional

try:
    from ..agents.error_summarizer import ErrorSummarizerAgent
    from ..agents.error_summarizer.states import ErrorSummarizerAgentState
    from ..config import config as cfg
    from ..utils.database import ElasticsearchDatabase
    from ..utils.llm_model import GeminiModel
    from ..utils.logger import Logger
except ImportError as e:
    print(f"Error importing modules for 'analyze-errors' CLI: {e}", file=sys.stderr)
    sys.exit(1)

logger = Logger()


def valid_iso_timestamp(s_val):
    try:
        if s_val.endswith("Z"):
            dt = datetime.fromisoformat(s_val[:-1] + "+00:00")
        else:
            dt = datetime.fromisoformat(s_val)
        return s_val
    except ValueError:
        msg = f"Not a valid ISO 8601 timestamp: '{s_val}'. Expected format e.g., YYYY-MM-DDTHH:MM:SSZ or YYYY-MM-DDTHH:MM:SS+00:00"
        raise argparse.ArgumentTypeError(msg)


def _print_run_summary_cli(final_state: ErrorSummarizerAgentState, group_name: str):
    print(f"\n--- Error Summarization for Group '{group_name}' (CLI) ---")
    agent_status = final_state.get("agent_status", "Status Unknown")
    print(f"Overall Agent Status: {agent_status}")

    error_messages = final_state.get("error_messages", [])
    if error_messages:
        print("Agent Errors/Warnings:")
        for err in error_messages:
            print(f"  - {err}")

    raw_logs_count = len(final_state.get("raw_error_logs", []))
    print(f"\nFetched {raw_logs_count} error logs for processing based on criteria.")

    cluster_assignments = final_state.get("cluster_assignments")
    if cluster_assignments is not None:
        from collections import Counter

        print(
            f"Cluster assignments overview: {Counter(cluster_assignments).most_common()}"
        )
    else:
        print("Cluster assignments: Not available (possibly skipped or failed).")

    print(
        f"\nProcessed Cluster Details & Summaries (Target Index: {final_state.get('target_summary_index')}):"
    )
    processed_details = final_state.get("processed_cluster_details", [])
    if not processed_details:
        print("  No clusters were processed or summarized.")

    for i, cluster_detail in enumerate(processed_details):
        cluster_label = cluster_detail.get("cluster_label", f"Unknown Cluster {i+1}")
        print(f"\n  Cluster/Group: {cluster_label}")
        print(
            f"    Total Logs in this specific group/cluster: {cluster_detail.get('total_logs_in_cluster')}"
        )
        print(
            f"    Time Range: {cluster_detail.get('cluster_time_range_start', 'N/A')} to {cluster_detail.get('cluster_time_range_end', 'N/A')}"
        )
        print(
            f"    Summary Generated Successfully: {cluster_detail.get('summary_generated', False)}"
        )

        summary_output_dict = cluster_detail.get("summary_output")
        if summary_output_dict:
            print(f"      LLM Summary: \"{summary_output_dict.get('summary', 'N/A')}\"")
            print(
                f"      Potential Cause: \"{summary_output_dict.get('potential_cause', 'N/A')}\""
            )
            print(f"      Keywords: {summary_output_dict.get('keywords', [])}")
            print(
                f"      Representative Log: \"{summary_output_dict.get('representative_log_line', 'N/A')}\""
            )

        summary_es_id = cluster_detail.get("summary_document_id_es")
        if summary_es_id:
            print(f"    Summary Stored in ES (ID): {summary_es_id}")

        sampled_logs_content = cluster_detail.get("sampled_log_messages_used", [])
        print(
            f"    Number of Sampled Log Messages Used for LLM: {len(sampled_logs_content)}"
        )

    final_summary_ids_count = len(final_state.get("final_summary_ids", []))
    print(
        f"\nTotal summary documents created in Elasticsearch: {final_summary_ids_count}"
    )
    print("--- End of Error Summarization Report (CLI) ---")


def handle_analyze_errors_run_summary(args):
    action_description = "Run Error Log Summarization"
    logger.info(
        f"Executing {action_description}: group='{args.group}', "
        f"start='{args.start_time}', end='{args.end_time}', "
        f"levels='{args.error_levels}', max_logs={args.max_logs}"  # error_levels here is the raw string from args
    )
    print(f"Starting {action_description} for group '{args.group}'...")

    try:
        db_main = ElasticsearchDatabase()
        if not db_main.instance:
            logger.error("CLI: Elasticsearch connection failed. Cannot proceed.")
            print("Error: Could not connect to Elasticsearch.", file=sys.stderr)
            return

        llm_instance_cli = None
        if args.llm_model:
            logger.info(
                f"CLI: Using specified LLM model for summarization: {args.llm_model}"
            )
            llm_instance_cli = GeminiModel(model_name=args.llm_model)

        agent = ErrorSummarizerAgent(db=db_main, llm_model_instance=llm_instance_cli)

        # Prepare error_levels list by converting to lowercase
        error_levels_list = [
            level.strip().lower()
            for level in args.error_levels.split(",")
            if level.strip()
        ]  # CHANGED to .lower()
        if not error_levels_list:
            logger.warning(
                "CLI: No valid error levels provided after parsing. Using default (lowercase)."
            )
            error_levels_list = list(
                cfg.DEFAULT_ERROR_LEVELS
            )  # Defaults are now lowercase

        logger.info(f"Processed error levels for query: {error_levels_list}")

        final_state = agent.run(
            group_name=args.group,
            start_time_iso=args.start_time,
            end_time_iso=args.end_time,
            error_log_levels=error_levels_list,
            max_logs_to_process=args.max_logs,
            embedding_model_name=args.embedding_model,
            llm_model_for_summary=args.llm_model,
            clustering_params={
                "eps": args.dbscan_eps,
                "min_samples": args.dbscan_min_samples,
            },
            sampling_params={
                "max_samples_per_cluster": args.max_samples_per_cluster,
                "max_samples_unclustered": args.max_samples_unclustered,
            },
            target_summary_index=args.output_index,
        )
        _print_run_summary_cli(final_state, args.group)

    except Exception as e:
        logger.error(
            f"CLI: A critical error occurred during {action_description}: {e}",
            exc_info=True,
        )
        print(
            f"\nAn critical error occurred during '{action_description}': {e}",
            file=sys.stderr,
        )


def register_analyze_errors_parser(subparsers):
    analyze_parser_main = subparsers.add_parser(
        "analyze-errors",
        help="Analyze error logs using LLMs: summarize errors for a group within a time window.",
        description="Provides subcommands to analyze error logs stored in Elasticsearch's parsed_log_* indices.",
    )

    ae_subparsers = analyze_parser_main.add_subparsers(
        dest="analyze_errors_action",
        help="Action to perform for error analysis",
        required=True,
    )

    run_summary_parser = ae_subparsers.add_parser(
        "run-summary",
        help="Run error log summarization for a specific group and time window.",
        description="Fetches error logs based on level and time, (optionally clusters them), samples representative logs, and generates LLM-based summaries which are stored in Elasticsearch.",
    )
    run_summary_parser.add_argument(
        "-g",
        "--group",
        type=str,
        required=True,
        help="Specify the single group name to process (e.g., 'apache', 'system_kernel'). This corresponds to a 'parsed_log_<group>' index.",
    )

    default_end_time_dt = datetime.now(timezone.utc)
    default_start_time_dt = default_end_time_dt - timedelta(days=1)
    run_summary_parser.add_argument(
        "--start-time",
        type=valid_iso_timestamp,
        default=default_start_time_dt.isoformat(),
        help=f"Start timestamp for log query in ISO 8601 format (e.g., YYYY-MM-DDTHH:MM:SSZ). Default: 24 hours ago.",
    )
    run_summary_parser.add_argument(
        "--end-time",
        type=valid_iso_timestamp,
        default=default_end_time_dt.isoformat(),
        help=f"End timestamp for log query in ISO 8601 format. Default: now.",
    )
    run_summary_parser.add_argument(
        "--error-levels",
        type=str,
        default=",".join(cfg.DEFAULT_ERROR_LEVELS),
        help=f"Comma-separated list of log levels to consider as errors (e.g., 'error,critical,warn'). Input will be lowercased. Default: {','.join(cfg.DEFAULT_ERROR_LEVELS)}",
    )
    run_summary_parser.add_argument(
        "--max-logs",
        type=int,
        default=cfg.DEFAULT_MAX_LOGS_FOR_SUMMARY,
        help=f"Maximum number of error logs to fetch and process from the time window. Default: {cfg.DEFAULT_MAX_LOGS_FOR_SUMMARY}",
    )

    run_summary_parser.add_argument(
        "--embedding-model",
        type=str,
        default=cfg.DEFAULT_EMBEDDING_MODEL_FOR_SUMMARY,  # defaults to "sentence-transformers/all-MiniLM-L6-v2"
        help=(
            "Name/path of the embedding model. Can be a Google API model (e.g., 'models/text-embedding-004') "
            "or a local Sentence Transformer model (e.g., 'sentence-transformers/all-MiniLM-L6-v2'). "
            f"Default: {cfg.DEFAULT_EMBEDDING_MODEL_FOR_SUMMARY}"
        ),  # UPDATED HELP TEXT
    )
    run_summary_parser.add_argument(
        "--llm-model",
        type=str,
        default=cfg.DEFAULT_LLM_MODEL_FOR_SUMMARY_GENERATION,
        help=f"Name of the LLM model for generating summaries. Default: {cfg.DEFAULT_LLM_MODEL_FOR_SUMMARY_GENERATION}",
    )
    run_summary_parser.add_argument(
        "--dbscan-eps",
        type=float,
        default=cfg.DEFAULT_DBSCAN_EPS_FOR_SUMMARY,
        help=f"DBSCAN epsilon parameter for clustering. Affects how close points need to be. Default: {cfg.DEFAULT_DBSCAN_EPS_FOR_SUMMARY}",
    )
    run_summary_parser.add_argument(
        "--dbscan-min-samples",
        type=int,
        default=cfg.DEFAULT_DBSCAN_MIN_SAMPLES_FOR_SUMMARY,
        help=f"DBSCAN min_samples parameter for clustering. Min points to form a dense region. Default: {cfg.DEFAULT_DBSCAN_MIN_SAMPLES_FOR_SUMMARY}",
    )
    run_summary_parser.add_argument(
        "--max-samples-per-cluster",
        type=int,
        default=cfg.DEFAULT_MAX_SAMPLES_PER_CLUSTER_FOR_SUMMARY,
        help=f"Maximum log samples to take from each identified cluster for LLM summary. Default: {cfg.DEFAULT_MAX_SAMPLES_PER_CLUSTER_FOR_SUMMARY}",
    )
    run_summary_parser.add_argument(
        "--max-samples-unclustered",
        type=int,
        default=cfg.DEFAULT_MAX_SAMPLES_UNCLUSTERED_FOR_SUMMARY,
        help=f"Maximum log samples to take from unclustered (outlier) logs for LLM summary. Default: {cfg.DEFAULT_MAX_SAMPLES_UNCLUSTERED_FOR_SUMMARY}",
    )
    run_summary_parser.add_argument(
        "--output-index",
        type=str,
        default=cfg.INDEX_ERROR_SUMMARIES,
        help=f"Elasticsearch index to store the generated summaries. Default: {cfg.INDEX_ERROR_SUMMARIES}",
    )
    run_summary_parser.set_defaults(func=handle_analyze_errors_run_summary)
