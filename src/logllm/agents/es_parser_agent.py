# src/logllm/agents/es_parser_agent.py
import os
import time
import pandas as pd
from typing import TypedDict, Dict, List, Optional, Tuple, Any, Callable, Literal
from pygrok import Grok
from pydantic import BaseModel, Field
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from langgraph.graph import StateGraph, END
from langgraph.graph.graph import CompiledGraph
from datetime import datetime

# Relative imports (ensure paths are correct)
try:
    from ..utils.llm_model import LLMModel, GeminiModel
    from ..utils.logger import Logger
    from ..utils.prompts_manager import PromptsManager
    from ..utils.database import ElasticsearchDatabase
    from ..config import config as cfg
except ImportError as e:
     print(f"Error during agent imports: {e}")
     import sys
     sys.exit(1)

# --- LLM Schema (remains the same) ---
class GrokPatternSchema(BaseModel):
    grok_pattern: str = Field(description="Output only the Grok pattern string.")

# --- Agent States (Add batch_size and sample_size) ---
class ScrollGrokParserState(TypedDict): # Keep this for the sub-agent's perspective
    # Input Config passed to run()
    source_index: str
    target_index: str           # Index for successfully parsed docs
    failed_index: str           # Index for failed/fallback docs
    grok_pattern: str
    field_to_parse: str
    source_query: Optional[Dict[str, Any]]
    fields_to_copy: Optional[List[str]]
    batch_size: int
    is_fallback_run: bool       # Flag to indicate if this is a fallback run

    # Results accumulated during run()
    processed_count: int
    successfully_indexed_count: int # Docs written to target_index
    failed_indexed_count: int       # Docs written to failed_index
    parse_error_count: int          # Docs that failed grok match
    index_error_count: int          # Bulk indexing errors (combined)
    status: str                     # 'running', 'completed', 'failed'

class SingleGroupParseGraphState(TypedDict):
    # Input configuration
    group_name: str
    source_index: str
    target_index: str
    failed_index: str # <-- Added Failed Index Name
    field_to_parse: str
    fields_to_copy: Optional[List[str]]
    sample_size_generation: int
    sample_size_validation: int
    validation_threshold: float
    batch_size: int
    max_regeneration_attempts: int
    keep_unparsed_index: bool
    provided_grok_pattern: Optional[str]

    # Dynamic state during run
    current_attempt: int
    current_grok_pattern: Optional[str]
    last_failed_pattern: Optional[str]
    sample_lines_for_generation: List[str]
    sample_lines_for_validation: List[str]
    validation_passed: bool
    final_parsing_status: str # e.g., "success", "success_with_errors", "success_fallback", "failed", "failed_fallback"
    # Store summary results directly, not the full state of the sub-agent
    final_parsing_results_summary: Optional[Dict[str, int]] # e.g., {"processed": N, "successful": M, "failed": O, "parse_errors": P, "index_errors": Q}
    error_messages: List[str]

class AllGroupsParserState(TypedDict):
    group_info_index: str
    field_to_parse: str
    fields_to_copy: Optional[List[str]]
    # Note: batch_size and sample_size are passed into run, not stored here
    # Results per group
    group_results: Dict[str, SingleGroupParseGraphState]
    status: str

def _parallel_group_worker_new(
    single_group_config: Dict[str, Any],
    prompts_json_path: str
) -> Tuple[str, SingleGroupParseGraphState]:
    group_name = single_group_config.get("group_name", "UnknownGroup")
    # Each worker needs its own logger instance potentially
    worker_logger = Logger() # Or configure shared logging if needed
    worker_logger.info(f"[Worker-{os.getpid()}] Started Group: {group_name}")

    try:
        # Initialize dependencies within the worker process/thread
        db_worker = ElasticsearchDatabase()
        if db_worker.instance is None: raise ConnectionError("Worker ES connection failed")

        model_worker = GeminiModel() # Assumes API key is in ENV
        prompts_manager_worker = PromptsManager(json_file=prompts_json_path)

        # Instantiate the LangGraph-based agent
        sg_agent_worker = SingleGroupParserAgent(
            model=model_worker,
            db=db_worker,
            prompts_manager=prompts_manager_worker
        )

        # Run the graph with the provided config dictionary
        final_state = sg_agent_worker.run(single_group_config)

        worker_logger.info(f"[Worker-{os.getpid()}] Finished Group: {group_name}, Status: {final_state.get('final_parsing_status', 'unknown')}")
        return group_name, final_state

    except Exception as e:
        worker_logger.error(f"[Worker-{os.getpid()}] CRITICAL Error in group '{group_name}': {e}", exc_info=True)
        # Construct a comprehensive failed state
        failed_state: SingleGroupParseGraphState = {
             "group_name": group_name,
             "source_index": cfg.get_log_storage_index(group_name), # Best guess
             "target_index": cfg.get_parsed_log_storage_index(group_name), # Best guess
             "failed_index": cfg.get_unparsed_log_storage_index(group_name), # Best guess
             "field_to_parse": single_group_config.get('field_to_parse', 'content'),
             "fields_to_copy": single_group_config.get('fields_to_copy'),
             "sample_size_generation": single_group_config.get('sample_size_generation', 20),
             "sample_size_validation": single_group_config.get('sample_size_validation', 10),
             "validation_threshold": single_group_config.get('validation_threshold', 0.5),
             "batch_size": single_group_config.get('batch_size', 5000),
             "max_regeneration_attempts": single_group_config.get('max_regeneration_attempts', 3),
             "current_attempt": 0,
             "current_grok_pattern": None,
             "last_failed_pattern": None,
             "sample_lines_for_generation": [],
             "sample_lines_for_validation": [],
             "validation_passed": False,
             "final_parsing_status": "failed (worker critical error)",
             "final_parsing_results_summary": None,
             "error_messages": [f"Worker critical error: {e}"]
         }
        return group_name, failed_state

# --- ScrollGrokParserAgent ---
class ScrollGrokParserAgent:
    # Internal batch storage
    _current_success_batch_data: List[Tuple[str, Dict[str, Any]]] = [] # (source_id, parsed_doc) for target index
    _current_failed_batch_data: List[Tuple[str, Dict[str, Any], str]] = [] # (source_id, original_source_doc, reason) for failed index

    def __init__(self, db: ElasticsearchDatabase):
        self._db = db
        self._logger = Logger()
        self._grok_instance: Optional[Grok] = None
        self._batch_size_this_run: int = 5000
        # Reset counters within run()

    def _initialize_grok(self, pattern: str) -> bool:
        try:
            self._grok_instance = Grok(pattern)
            self._logger.info("Grok pattern compiled successfully.")
            return True
        except ValueError as e:
            self._logger.error(f"Invalid Grok pattern syntax: {pattern} - Error: {e}", exc_info=True)
            self._grok_instance = None
            return False

    def _process_single_hit(
        self,
        hit: Dict[str, Any],
        state: ScrollGrokParserState # Pass the state for context
    ) -> Literal["success", "parse_failed", "skip"]: # Return status
        """
        Processes a single document hit. Appends data to the appropriate internal batch list.
        Returns status: "success", "parse_failed", "skip".
        """
        source_doc = hit.get("_source", {})
        source_id = hit.get("_id")
        field_to_parse = state['field_to_parse']
        fields_to_copy = state.get('fields_to_copy')
        is_fallback = state['is_fallback_run']

        if not source_id:
            self._logger.warning("Source document missing '_id'. Skipping hit.")
            return "skip"

        original_content = source_doc.get(field_to_parse)
        if not isinstance(original_content, str):
            self._logger.warning(f"Field '{field_to_parse}' not found/string in doc ID {source_id}. Storing as failed.")
            self._current_failed_batch_data.append((source_id, source_doc, "missing_parse_field"))
            return "parse_failed" # Treat as a parse failure

        # If it's a fallback run, don't even try parsing with the fallback pattern,
        # just store the original doc in the failed index.
        if is_fallback:
            self._current_failed_batch_data.append((source_id, source_doc, "fallback_used"))
            return "parse_failed" # Treat as parse failed in terms of target index

        # --- Regular Parsing Attempt ---
        if self._grok_instance is None:
             self._logger.error("Grok instance not initialized during hit processing. This shouldn't happen.")
             # Store as failed if grok isn't ready (unexpected state)
             self._current_failed_batch_data.append((source_id, source_doc, "internal_grok_error"))
             return "parse_failed"

        parsed_fields = self._grok_instance.match(original_content)
        if parsed_fields:
            # Prepare the document for the *target* index
            target_doc = parsed_fields.copy()
            # --- Timestamp handling ---
            if 'timestamp' not in target_doc and '@timestamp' in source_doc:
                 target_doc['@original_timestamp'] = source_doc['@timestamp']
            elif 'timestamp' in target_doc and '@timestamp' not in target_doc:
                 target_doc['@timestamp'] = target_doc['timestamp']
            # --- Copy other fields ---
            if fields_to_copy:
                for field in fields_to_copy:
                    if field in source_doc and field not in target_doc:
                        target_doc[field] = source_doc[field]
            # --- Add to success batch ---
            self._current_success_batch_data.append((source_id, target_doc))
            return "success"
        else:
            # Parse failed, store original doc in *failed* batch
            self._current_failed_batch_data.append((source_id, source_doc, "grok_mismatch"))
            return "parse_failed"

    def _process_batch(self, hits: List[Dict[str, Any]], state: ScrollGrokParserState) -> bool:
        """Processes a batch of hits, routing to success or failed batches."""
        self._logger.debug(f"Processing scroll batch of {len(hits)} hits...")
        batch_parse_failures = 0

        for hit in hits:
             status = self._process_single_hit(hit, state)
             if status == "parse_failed":
                 batch_parse_failures += 1

        self._parse_error_count += batch_parse_failures # Update agent's total parse error count

        # Index the accumulated batches if they are large enough
        if len(self._current_success_batch_data) >= self._batch_size_this_run:
            self._flush_success_batch(state['target_index'])
        if len(self._current_failed_batch_data) >= self._batch_size_this_run:
            self._flush_failed_batch(state['failed_index'])

        return True # Continue scrolling

    def _flush_success_batch(self, target_index: str):
        """Formats update/upsert actions for SUCCESSFUL parses and indexes to target_index."""
        if not self._current_success_batch_data: return

        self._logger.info(f"Flushing SUCCESS batch of {len(self._current_success_batch_data)} documents to target index '{target_index}'...")
        bulk_actions = []
        for source_id, parsed_doc in self._current_success_batch_data:
            bulk_actions.append({
                "_op_type": "update",
                "_index": target_index,
                "_id": source_id,
                "doc": parsed_doc,
                "doc_as_upsert": True
            })

        success_count, errors = self._db.bulk_operation(actions=bulk_actions)
        self._successfully_indexed_count += success_count
        self._index_error_count += len(errors)
        if errors: self._logger.warning(f"{len(errors)} errors occurred during target index bulk update/upsert.")
        self._current_success_batch_data = [] # Clear batch

    def _flush_failed_batch(self, failed_index: str):
        """Formats insert actions for FAILED/FALLBACK parses and indexes to failed_index."""
        if not self._current_failed_batch_data: return

        self._logger.info(f"Flushing FAILED/FALLBACK batch of {len(self._current_failed_batch_data)} documents to failed index '{failed_index}'...")
        bulk_actions = []
        for source_id, original_source, reason in self._current_failed_batch_data:
            failed_doc = {
                "original_source": original_source, # Store the whole original document
                "failure_reason": reason,
                "@timestamp": original_source.get("@timestamp", datetime.now().isoformat()) # Preserve or add timestamp
            }
            bulk_actions.append({
                "_op_type": "index", # Use index operation
                "_index": failed_index,
                "_id": source_id, # Use original ID
                "_source": failed_doc
            })

        # Use bulk_operation, but errors here are still counted towards the total index errors
        success_count, errors = self._db.bulk_operation(actions=bulk_actions)
        self._failed_indexed_count += success_count # Count docs successfully written to failed index
        self._index_error_count += len(errors)
        if errors: self._logger.warning(f"{len(errors)} errors occurred during failed index bulk insert.")
        self._current_failed_batch_data = [] # Clear batch

    def run(self, state: ScrollGrokParserState) -> ScrollGrokParserState:
        """Executes the scrolling, parsing, and indexing logic."""
        target_index = state['target_index']
        failed_index = state['failed_index']
        source_index = state['source_index']
        pattern = state['grok_pattern']
        is_fallback = state['is_fallback_run']

        self._batch_size_this_run = state['batch_size']
        log_prefix = f"Fallback Run ({failed_index})" if is_fallback else f"Parse Run ({target_index})"
        self._logger.info(f"Starting ScrollGrokParserAgent {log_prefix}. Source: '{source_index}', Batch: {self._batch_size_this_run}")

        # --- Reset internal state for this run ---
        self._current_success_batch_data = []
        self._current_failed_batch_data = []
        self._processed_count = 0
        self._successfully_indexed_count = 0
        self._failed_indexed_count = 0
        self._parse_error_count = 0
        self._index_error_count = 0
        # ----------------------------------------

        # Initialize Grok only if it's *not* a fallback run
        if not is_fallback:
            if not self._initialize_grok(pattern):
                 # If Grok fails to compile, we cannot parse successfully.
                 # Treat all docs as parse failures for this run.
                 self._logger.error(f"Grok pattern invalid: {pattern}. Cannot proceed with normal parsing.")
                 # We could technically still scroll and dump everything to failed index,
                 # but let's signal failure more clearly.
                 return {**state, "status": "failed", "parse_error_count": -1} # Indicate Grok init failure

        # Prepare query and fields
        source_query = state.get("source_query") or {"query": {"match_all": {}}}
        fields_needed = set([state['field_to_parse']])
        if state.get('fields_to_copy'): fields_needed.update(state['fields_to_copy'])
        if '@timestamp' not in fields_needed: fields_needed.add('@timestamp') # Ensure timestamp is fetched
        source_fields_list = list(fields_needed)

        # Start scrolling and processing
        final_status = "running"
        try:
            processed_count, _ = self._db.scroll_and_process_batches(
                index=source_index,
                query=source_query,
                batch_size=self._batch_size_this_run,
                process_batch_func=lambda hits: self._process_batch(hits, state), # Pass state to processor
                source_fields=source_fields_list
            )
            self._processed_count = processed_count

            # Flush any remaining documents in both batches
            self._flush_success_batch(target_index)
            self._flush_failed_batch(failed_index)

            final_status = "completed"
            self._logger.info(f"ScrollGrokParserAgent {log_prefix} completed.")

        except Exception as e:
            final_status = "failed"
            self._logger.error(f"Run failed during scroll/processing: {e}", exc_info=True)
            # Attempt to flush remaining data even on error
            try: self._flush_success_batch(target_index)
            except Exception as flush_err: self._logger.error(f"Error flushing final success batch: {flush_err}")
            try: self._flush_failed_batch(failed_index)
            except Exception as flush_err: self._logger.error(f"Error flushing final failed batch: {flush_err}")

        # Populate results into a new state dictionary
        result_state: ScrollGrokParserState = {
            **state, # Copy input config
            "processed_count": self._processed_count,
            "successfully_indexed_count": self._successfully_indexed_count,
            "failed_indexed_count": self._failed_indexed_count,
            "parse_error_count": self._parse_error_count,
            "index_error_count": self._index_error_count,
            "status": final_status
        }

        self._logger.info(f"{log_prefix} Summary: Processed={result_state['processed_count']}, "
                          f"Indexed OK->Target={result_state['successfully_indexed_count']}, "
                          f"Indexed Fail/Fallback->Failed={result_state['failed_indexed_count']}, "
                          f"Parse Errors={result_state['parse_error_count']}, "
                          f"Index Errors={result_state['index_error_count']}")

        return result_state

# --- NEW SingleGroupParserAgent (Refactored with LangGraph) ---
class SingleGroupParserAgent:
    FALLBACK_PATTERN = "%{GREEDYDATA:original_content}" # Keep fallback

    def __init__(self, model: LLMModel, db: ElasticsearchDatabase, prompts_manager: PromptsManager):
        self._model = model
        self._db = db
        self._prompts_manager = prompts_manager
        self._logger = Logger()
        # Instantiate the sub-agent
        self._scroll_parser_agent = ScrollGrokParserAgent(db)
        # Build and compile the graph
        self.graph = self._build_graph()

    # --- Graph Nodes ---

    def _start_node(self, state: SingleGroupParseGraphState) -> SingleGroupParseGraphState | Dict[str, Any]:
        """Initializes indices, clears failed index, fetches samples."""
        group_name = state['group_name']
        keep_unparsed_index = state.get('keep_unparsed_index', False) # Get the flag
        provided_pattern = state.get('provided_grok_pattern')  # Retrieve provided pattern
        self._logger.info(f"[{group_name}] Starting graph run...")

        errors = []
        source_index = ""
        target_index = ""
        failed_index = "" # <--- New
        samples_gen = []
        samples_val = []

        try:
            source_index = cfg.get_log_storage_index(group_name)
            target_index = cfg.get_parsed_log_storage_index(group_name)
            failed_index = cfg.get_unparsed_log_storage_index(group_name) # <--- Get failed index name

            self._logger.info(f"[{group_name}] Indices: Source='{source_index}', Target='{target_index}', Failed='{failed_index}'")

            # --- Clear the FAILED index for this group ---
            try:
                 self._logger.info(f"[{group_name}] Attempting to delete existing failed index: {failed_index}")
                 delete_resp = self._db.instance.indices.delete(index=failed_index, ignore=[400, 404])
                 self._logger.info(f"[{group_name}] Delete response for {failed_index}: {delete_resp}")
            except Exception as del_e:
                 # Log error but continue, maybe index didn't exist or perms issue
                 self._logger.warning(f"[{group_name}] Could not delete failed index {failed_index} (might not exist): {del_e}")
            # ---------------------------------------------

            # --- Conditionally Clear the UNPARSED index ---
            if not keep_unparsed_index:
                try:
                     self._logger.info(f"[{group_name}] Deleting existing unparsed index: {failed_index}")
                     delete_resp = self._db.instance.indices.delete(index=failed_index, ignore=[400, 404])
                     self._logger.info(f"[{group_name}] Delete response for {failed_index}: {delete_resp}")
                except Exception as del_e:
                     self._logger.warning(f"[{group_name}] Could not delete unparsed index {failed_index} (might not exist): {del_e}")
            else:
                 self._logger.info(f"[{group_name}] Skipping deletion of unparsed index: {failed_index} (--keep-unparsed specified)")
            # ---------------------------------------------

            # Fetch samples (generation)
            self._logger.info(f"[{group_name}] Fetching {state['sample_size_generation']} samples for generation from '{source_index}'...")
            samples_gen = self._db.get_sample_lines(
                index=source_index,
                field=state['field_to_parse'],
                sample_size=state['sample_size_generation']
            )
            if not samples_gen:
                self._logger.warning(f"[{group_name}] No samples found for generation.")

            # Fetch samples (validation)
            self._logger.info(f"[{group_name}] Fetching {state['sample_size_validation']} samples for validation from '{source_index}'...")
            samples_val = self._db.get_sample_lines(
                index=source_index,
                field=state['field_to_parse'],
                sample_size=state['sample_size_validation']
            )
            if not samples_val:
                msg = f"[{group_name}] No samples found for validation. Cannot validate pattern."
                self._logger.error(msg)
                errors.append(msg) # This might prevent reaching validation node

        except Exception as e:
            msg = f"[{group_name}] Error during start node: {e}"
            self._logger.error(msg, exc_info=True)
            errors.append(msg)

        # Return updates to the state
        return {
            "source_index": source_index,
            "target_index": target_index,
            "failed_index": failed_index, # <-- Store failed index name
            "sample_lines_for_generation": samples_gen,
            "sample_lines_for_validation": samples_val,
            "error_messages": errors,
            "current_attempt": 1, # Reset attempts
            "current_grok_pattern": provided_pattern, # Use provided pattern if any
            "last_failed_pattern": None,
            "validation_passed": False,
            "final_parsing_status": "pending",
            "final_parsing_results_summary": None # Reset results
        }

    def _generate_grok_node(self, state: SingleGroupParseGraphState) -> SingleGroupParseGraphState | Dict[str, Any]:
        """Generates Grok pattern using LLM, passing context."""
        group_name = state['group_name']
        attempt = state['current_attempt']
        samples = state['sample_lines_for_generation']
        last_failed = state.get('last_failed_pattern')
        errors = list(state.get('error_messages', [])) # Ensure it's a list
        generated_pattern: Optional[str] = None

        self._logger.info(f"[{group_name}] Attempt {attempt}: Generating Grok pattern...")

        if not samples:
            self._logger.warning(f"[{group_name}] No samples for generation attempt {attempt}.")
            return {"current_grok_pattern": None, "error_messages": errors}

        try:
            # Prepare context about previous failure
            failed_pattern_context = ""
            if last_failed:
                # Ensure context is clearly separated and asks for a *different* pattern
                failed_pattern_context = (
                    f"\n\n---\nContext: The previous attempt using the pattern below failed validation. "
                    f"Please analyze the sample logs again and generate a *different* and potentially more accurate Grok pattern.\n"
                    f"Previously Failed Pattern: {last_failed}\n---"
                )

            # --- Get prompt using PromptsManager ---
            # Ensure key 'agents.es_parser_agent.SingleGroupParserAgent._generate_grok_node' exists in prompts.json
            # And that the template expects 'sample_logs_for_generation' and 'last_failed_pattern_context'
            prompt = self._prompts_manager.get_prompt(
                sample_logs_for_generation=str(samples),
                last_failed_pattern_context=failed_pattern_context
            )

            response = self._model.generate(prompt, schema=GrokPatternSchema)

            if response and isinstance(response, GrokPatternSchema) and response.grok_pattern:
                pattern = response.grok_pattern.strip()
                # Prevent LLM from returning the exact same failed pattern
                if pattern == last_failed:
                     msg = f"[{group_name}] LLM returned the same failed pattern on attempt {attempt}: {pattern}. Treating as generation failure."
                     self._logger.warning(msg)
                     errors.append(msg)
                     generated_pattern = None # Force retry or fallback
                elif "%{" in pattern and "}" in pattern:
                    self._logger.info(f"[{group_name}] LLM generated Grok pattern (Attempt {attempt}): {pattern}")
                    generated_pattern = pattern
                else:
                     msg = f"[{group_name}] LLM response on attempt {attempt} not valid Grok: {pattern}"
                     self._logger.warning(msg)
                     errors.append(msg)
            else:
                msg = f"[{group_name}] LLM did not return valid pattern schema on attempt {attempt}. Response: {response}"
                self._logger.warning(msg)
                errors.append(msg)

        except ValueError as ve:
             msg = f"[{group_name}] Prompt error (vars/key) for Grok gen (Attempt {attempt}): {ve}"
             self._logger.error(msg, exc_info=True)
             errors.append(msg)
        except Exception as e:
            msg = f"[{group_name}] LLM call failed during Grok gen (Attempt {attempt}): {e}"
            self._logger.error(msg, exc_info=True)
            errors.append(msg)

        return {"current_grok_pattern": generated_pattern, "error_messages": errors}

    def _validate_pattern_node(self, state: SingleGroupParseGraphState) -> SingleGroupParseGraphState | Dict[str, Any]:
        # (This node remains largely the same, just uses state fields)
        group_name = state['group_name']
        pattern = state.get('current_grok_pattern')
        validation_samples = state.get('sample_lines_for_validation', [])
        threshold = state.get('validation_threshold', 0.5)
        errors = list(state.get('error_messages', []))
        validation_passed = False

        self._logger.info(f"[{group_name}] Validating pattern: {pattern}")

        if not pattern:
            msg = f"[{group_name}] No pattern to validate."
            self._logger.warning(msg); errors.append(msg)
            return {"validation_passed": False, "error_messages": errors}
        if not validation_samples:
            msg = f"[{group_name}] No samples for validation."
            self._logger.warning(msg); errors.append(msg)
            return {"validation_passed": False, "error_messages": errors}

        try:
            grok = Grok(pattern)
            parsed_count = 0; total_validated = 0
            for line in validation_samples:
                line = line.strip();
                if not line: continue
                total_validated += 1
                if grok.match(line): parsed_count += 1

            if total_validated == 0:
                 self._logger.warning(f"[{group_name}] No non-empty validation lines."); validation_passed = False
            else:
                success_rate = parsed_count / total_validated
                self._logger.info(f"[{group_name}] Validation: Parsed {parsed_count}/{total_validated}. Rate: {success_rate:.2f}")
                if success_rate >= threshold:
                    self._logger.info(f"[{group_name}] Validation PASSED (>= {threshold:.2f}).")
                    validation_passed = True
                else:
                    self._logger.warning(f"[{group_name}] Validation FAILED (< {threshold:.2f}).")
                    validation_passed = False
        except ValueError as e:
            msg = f"[{group_name}] Invalid Grok syntax during validation: {pattern} - {e}"
            self._logger.error(msg); errors.append(msg); validation_passed = False
        except Exception as e:
            msg = f"[{group_name}] Error during validation: {e}"
            self._logger.error(msg, exc_info=True); errors.append(msg); validation_passed = False

        return {"validation_passed": validation_passed, "error_messages": errors}

    def _parse_all_node(self, state: SingleGroupParseGraphState) -> SingleGroupParseGraphState | Dict[str, Any]:
        """Parses all documents using the validated pattern, writing to target_index."""
        group_name = state['group_name']
        pattern = state['current_grok_pattern']
        target_index = state['target_index']
        failed_index = state['failed_index'] # Also need failed index here
        self._logger.info(f"[{group_name}] Validation passed. Parsing all documents -> Target: {target_index}, Failed/Skipped -> {failed_index}")

        scroll_config: ScrollGrokParserState = {
            "source_index": state['source_index'],
            "target_index": target_index, # Write successes here
            "failed_index": failed_index, # Write failures here
            "grok_pattern": pattern,
            "field_to_parse": state['field_to_parse'],
            "fields_to_copy": state.get('fields_to_copy'),
            "batch_size": state['batch_size'],
            "source_query": {"query": {"match_all": {}}},
            "is_fallback_run": False # This is NOT a fallback run
            # Results fields will be added by the sub-agent run
        }

        try:
             # Run the scroll parser
             final_sub_state = self._scroll_parser_agent.run(scroll_config)
             final_status = "failed"
             if final_sub_state.get("status") == "completed":
                 # Check if *any* errors occurred (parse or index)
                 if (final_sub_state.get("parse_error_count", 0) > 0 or
                     final_sub_state.get("index_error_count", 0) > 0 or
                     final_sub_state.get("failed_indexed_count", 0) > 0): # Count docs sent to failed index as 'errors' in this context
                      final_status = "success_with_errors"
                      self._logger.warning(f"[{group_name}] Parse all completed with some errors/failures.")
                 else:
                      final_status = "success"
                      self._logger.info(f"[{group_name}] Parse all completed successfully.")
             else:
                 self._logger.error(f"[{group_name}] Parse all failed. Sub-agent status: {final_sub_state.get('status')}")

             # Store a summary of results, not the full sub-state
             results_summary = {
                 "processed": final_sub_state.get("processed_count", 0),
                 "successful": final_sub_state.get("successfully_indexed_count", 0),
                 "failed": final_sub_state.get("failed_indexed_count", 0),
                 "parse_errors": final_sub_state.get("parse_error_count", 0), # Grok mismatches within this run
                 "index_errors": final_sub_state.get("index_error_count", 0) # Bulk indexing errors
             }
             return {"final_parsing_status": final_status, "final_parsing_results_summary": results_summary}
        except Exception as e:
            msg = f"[{group_name}] Critical error invoking ScrollGrokParserAgent: {e}"
            self._logger.error(msg, exc_info=True)
            return {
                "final_parsing_status": "failed",
                "final_parsing_results_summary": None,
                "error_messages": state.get("error_messages", []) + [msg]
            }

    def _fallback_node(self, state: SingleGroupParseGraphState) -> SingleGroupParseGraphState | Dict[str, Any]:
        """Executes fallback: runs ScrollGrokParserAgent configured to write ONLY to failed_index."""
        group_name = state['group_name']
        failed_index = state['failed_index']
        self._logger.warning(f"[{group_name}] Executing FALLBACK. ALL documents will be stored in: {failed_index}")

        # Prepare config for ScrollGrokParserAgent for FALLBACK
        scroll_config: ScrollGrokParserState = {
            "source_index": state['source_index'],
            # NOTE: Target index is irrelevant here, could be set to "" or failed_index,
            # but the is_fallback_run flag controls the behavior. Let's pass failed_index
            # for clarity, although ScrollGrokParser won't use it for success batch.
            "target_index": failed_index,
            "failed_index": failed_index, # Crucial: Where failures/fallback docs go
            "grok_pattern": self.FALLBACK_PATTERN, # Pass pattern for logging, not used for matching
            "field_to_parse": state['field_to_parse'],
            "fields_to_copy": state.get('fields_to_copy'),
            "batch_size": state['batch_size'],
            "source_query": {"query": {"match_all": {}}},
            "is_fallback_run": True # <-- IMPORTANT FLAG
        }

        try:
             # Run the scroll parser in fallback mode
             final_sub_state = self._scroll_parser_agent.run(scroll_config)
             final_status = "failed_fallback" # Assume failure unless explicitly completed
             if final_sub_state.get("status") == "completed":
                 # Even if completed, the status is 'success_fallback' because we didn't use a real pattern
                 final_status = "success_fallback"
                 self._logger.info(f"[{group_name}] Fallback processing completed.")
             else:
                 self._logger.error(f"[{group_name}] Fallback processing FAILED. Sub-agent status: {final_sub_state.get('status')}")

             # Store summary - note: successfully_indexed_count should be 0 in fallback
             results_summary = {
                 "processed": final_sub_state.get("processed_count", 0),
                 "successful": final_sub_state.get("successfully_indexed_count", 0), # Should be 0
                 "failed": final_sub_state.get("failed_indexed_count", 0), # All processed docs end up here
                 "parse_errors": final_sub_state.get("parse_error_count", 0), # Should be equal to processed
                 "index_errors": final_sub_state.get("index_error_count", 0)
             }
             return {"final_parsing_status": final_status, "final_parsing_results_summary": results_summary}
        except Exception as e:
            msg = f"[{group_name}] Critical error invoking ScrollGrokParserAgent during fallback: {e}"
            self._logger.error(msg, exc_info=True)
            return {
                "final_parsing_status": "failed_fallback",
                "final_parsing_results_summary": None,
                "error_messages": state.get("error_messages", []) + [msg]
            }

    def _prepare_for_retry_node(self, state: SingleGroupParseGraphState) -> Dict[str, Any]:
        """Increments attempt count and stores the failed pattern."""
        group_name = state['group_name']
        current_attempt = state.get('current_attempt', 1)
        failed_pattern = state.get('current_grok_pattern')
        self._logger.info(f"[{group_name}] Preparing for retry (Attempt {current_attempt+1}). Storing failed pattern: {failed_pattern}")
        return {
            "current_attempt": current_attempt + 1,
            "last_failed_pattern": failed_pattern, # Store the pattern that just failed
            "current_grok_pattern": None,           # Clear current pattern for regeneration
            "validation_passed": False              # Reset validation status
        }

    def _store_results_node(self, state: SingleGroupParseGraphState) -> Dict[str, Any]:
        """Stores the final results of the parsing attempt in Elasticsearch."""
        group_name = state['group_name']
        status = state.get('final_parsing_status', 'unknown')
        summary = state.get('final_parsing_results_summary')
        errors = list(state.get('error_messages', [])) # Start with existing errors

        self._logger.info(f"[{group_name}] Storing parsing results to history index. Status: {status}")

        # Determine the pattern used based on status
        pattern_used = state.get('current_grok_pattern')
        if status == "success_fallback":
            pattern_used = self.FALLBACK_PATTERN
        elif "failed" in status and not pattern_used: # If failed early, pattern might be None
             pattern_used = state.get('last_failed_pattern') or "N/A (Failed before pattern selection)"

        # Prepare document for ES
        result_doc = {
            "group_name": group_name,
            "grok_pattern_used": pattern_used,
            "parsing_status": status,
            "timestamp": datetime.now().isoformat(),
            # Extract counts from summary, defaulting to 0 if summary is None
            "processed_count": summary.get("processed", 0) if summary else 0,
            "successful_count": summary.get("successful", 0) if summary else 0,
            "failed_count": summary.get("failed", 0) if summary else 0, # Docs sent to failed index
            "parse_error_count": summary.get("parse_errors", 0) if summary else 0, # Grok mismatches
            "index_error_count": summary.get("index_errors", 0) if summary else 0, # Bulk errors
            "agent_error_count": len(state.get('error_messages', [])) # Count agent-level errors
        }

        try:
            self._db.insert(data=result_doc, index=cfg.INDEX_GROK_RESULTS_HISTORY)
            self._logger.info(f"[{group_name}] Successfully stored results in '{cfg.INDEX_GROK_RESULTS_HISTORY}'.")
        except Exception as e:
            msg = f"[{group_name}] Failed to store results in history index: {e}"
            self._logger.error(msg, exc_info=True)
            errors.append(msg) # Add storage error to the list

        # This node doesn't change the main flow, just reports. Return potentially updated errors.
        return {"error_messages": errors}

    # --- Conditional Edges (Updated) ---

    def _decide_pattern_source(self, state: SingleGroupParseGraphState) -> str:
        """Decides whether to generate a pattern or use the provided one."""
        group_name = state['group_name']
        if state.get('current_grok_pattern'):
            self._logger.debug(f"[{group_name}] Pattern provided or already set, moving to validation.")
            return "validate_pattern"
        else:
            self._logger.debug(f"[{group_name}] No pattern provided, moving to generation.")
            return "generate_grok"

    def _decide_after_generate(self, state: SingleGroupParseGraphState) -> str:
        """Decides whether to validate or fallback after pattern generation."""
        group_name = state['group_name']
        # Check if *any* errors occurred during start or generation
        if state.get("error_messages") and any("No samples found for validation" in msg for msg in state["error_messages"]):
             self._logger.error(f"[{group_name}] Cannot validate (no validation samples), moving to fallback.")
             return "fallback"
        if state.get('current_grok_pattern'):
            self._logger.debug(f"[{group_name}] Pattern generated, moving to validation.")
            return "validate_pattern"
        else:
            # If generation failed, check if retries remain for generation itself
            current_attempt = state.get('current_attempt', 1)
            max_attempts = state.get('max_regeneration_attempts', 3)
            if current_attempt < max_attempts:
                self._logger.warning(f"[{group_name}] Pattern generation failed (Attempt {current_attempt}/{max_attempts}), preparing for retry.")
                # Need to go through retry prep to increment attempt count
                return "prepare_for_retry"
            else:
                self._logger.error(f"[{group_name}] Pattern generation failed after max attempts ({max_attempts}), moving to fallback.")
                return "fallback"

    def _decide_after_validation(self, state: SingleGroupParseGraphState) -> str:
        """Decides whether to parse all, retry, or fallback after validation."""
        group_name = state['group_name']
        if state.get('validation_passed'):
            self._logger.debug(f"[{group_name}] Validation passed, moving to parse_all.")
            return "parse_all"
        else:
            # Validation failed, check if retries are exhausted
            current_attempt = state.get('current_attempt', 1)
            max_attempts = state.get('max_regeneration_attempts', 3)
            if current_attempt < max_attempts:
                self._logger.warning(f"[{group_name}] Validation failed (Attempt {current_attempt}/{max_attempts}), preparing for retry.")
                return "prepare_for_retry"
            else:
                self._logger.error(f"[{group_name}] Validation failed after max attempts ({max_attempts}), moving to fallback.")
                return "fallback"

    # --- Build Graph (No changes needed in structure, nodes handle logic) ---
    def _build_graph(self) -> CompiledGraph:
        workflow = StateGraph(SingleGroupParseGraphState)

        workflow.add_node("start", self._start_node)
        workflow.add_node("generate_grok", self._generate_grok_node)
        workflow.add_node("validate_pattern", self._validate_pattern_node)
        workflow.add_node("prepare_for_retry", self._prepare_for_retry_node)
        workflow.add_node("parse_all", self._parse_all_node)
        workflow.add_node("fallback", self._fallback_node)
        workflow.add_node("store_results", self._store_results_node) # <-- Add the new node

        workflow.set_entry_point("start")

        workflow.add_conditional_edges(
            "start",
            self._decide_pattern_source, # Use the new condition function
            {
                "generate_grok": "generate_grok",       # Go generate if no pattern
                "validate_pattern": "validate_pattern"  # Skip generation if pattern exists
            }
        )

        workflow.add_edge("start", "generate_grok")

        workflow.add_conditional_edges(
                "generate_grok",
                self._decide_after_generate,
                {
                    "validate_pattern": "validate_pattern",
                    "prepare_for_retry": "prepare_for_retry",
                    "fallback": "fallback"
                }
        )

        workflow.add_conditional_edges(
                "validate_pattern",
                self._decide_after_validation,
                {
                    "parse_all": "parse_all",
                    "prepare_for_retry": "prepare_for_retry",
                    "fallback": "fallback"
                }
        )

        workflow.add_edge("prepare_for_retry", "generate_grok")

        # --- Update Edges to point to store_results ---
        workflow.add_edge("parse_all", "store_results")
        workflow.add_edge("fallback", "store_results")
        # ---------------------------------------------

        # --- Add final edge from store_results to END ---
        workflow.add_edge("store_results", END)
        # --------------------------------------------

        return workflow.compile()


    # --- Run Method (Updated initial state setup) ---
    def run(self, initial_config: Dict[str, Any]) -> SingleGroupParseGraphState | Dict[str, Any]:
        group_name = initial_config['group_name']
        self._logger.info(f"[{group_name}] Initializing SingleGroupParserAgent graph run...")

        # Graph input MUST match the State TypedDict exactly
        graph_input: SingleGroupParseGraphState | Dict[str, Any] = {
            "group_name": group_name,
            "source_index": "", # Determined by start node
            "target_index": "", # Determined by start node
            "failed_index": "", # Determined by start node
            "field_to_parse": initial_config['field_to_parse'],
            "fields_to_copy": initial_config.get('fields_to_copy'),
            "sample_size_generation": initial_config['sample_size_generation'],
            "sample_size_validation": initial_config['sample_size_validation'],
            "validation_threshold": initial_config['validation_threshold'],
            "batch_size": initial_config['batch_size'],
            "max_regeneration_attempts": initial_config['max_regeneration_attempts'],
            # --- Defaults for dynamic state (will be overwritten by start_node) ---
            "current_attempt": 0, "current_grok_pattern": None, "last_failed_pattern": None,
            "sample_lines_for_generation": [], "sample_lines_for_validation": [],
            "validation_passed": False, "final_parsing_status": "pending",
            "final_parsing_results_summary": None, "error_messages": []
        }

        # Execute the graph
        final_state = self.graph.invoke(graph_input)

        self._logger.info(f"[{group_name}] Finished SingleGroupParserAgent graph run. Final Status: {final_state.get('final_parsing_status')}")
        return final_state # Return the full final state TypedDict


# --- AllGroupsParserAgent ---
class AllGroupsParserAgent:
    def __init__(self, model: LLMModel, db: ElasticsearchDatabase, prompts_manager: PromptsManager):
        # No need to instantiate SingleGroupParserAgent here anymore, worker does it
        self._model = model # Keep for potential future use? Or remove if worker handles all
        self._db = db
        self._prompts_manager = prompts_manager # Needed to pass json path to worker
        self._logger = Logger()

    def _get_all_groups(self, group_info_index: str) -> List[Dict[str, Any]]:
        # (No changes needed here)
        self._logger.info(f"Fetching all group definitions from index '{group_info_index}'...")
        try:
            query = {"query": {"match_all": {}}}
            groups_data = self._db.scroll_search(query=query, index=group_info_index)
            if not groups_data: return []
            valid_groups = [{"group_name": hit["_source"]["group"]} for hit in groups_data if hit.get("_source", {}).get("group")]
            self._logger.info(f"Fetched {len(valid_groups)} valid group definitions.")
            return valid_groups
        except Exception as e:
            self._logger.error(f"Failed to fetch groups from index '{group_info_index}': {e}", exc_info=True)
            return []

    def run(
        self,
        initial_state: AllGroupsParserState,
        num_threads: int = 1,
        batch_size: int = 500,
        sample_size: int = 10, # Sample for generation
        validation_sample_size: int = 10,
        validation_threshold: float = 0.51,
        max_regeneration_attempts: int = 5,# Default 3 attempts = 2 retries
        keep_unparsed_index: bool = False # <-- Accept flag
    ) -> AllGroupsParserState:
        self._logger.info(f"Starting AllGroupsParserAgent run. Workers: {num_threads}, Batch: {batch_size}, GenSample: {sample_size}, ValSample: {validation_sample_size}, MaxAttempts: {max_regeneration_attempts}")
        result_state = initial_state.copy()
        result_state["status"] = "running"
        result_state["group_results"] = {} # Ensure it's initialized

        groups_to_process = self._get_all_groups(initial_state['group_info_index'])
        if not groups_to_process:
            result_state["status"] = "completed (no groups)"; return result_state

        # --- Prepare Base Configuration Dictionary for Workers ---
        # This dict will be passed to each worker, containing all necessary params
        # for the SingleGroupParserAgent run
        single_group_base_config = {
            "field_to_parse": initial_state['field_to_parse'],
            "fields_to_copy": initial_state.get('fields_to_copy'),
            "batch_size": batch_size,
            "sample_size_generation": sample_size,
            "sample_size_validation": validation_sample_size,
            "validation_threshold": validation_threshold,
            "max_regeneration_attempts": max_regeneration_attempts,
            "keep_unparsed_index": keep_unparsed_index # <-- Pass flag here
            # group_name will be added per task
        }

        effective_num_workers = max(1, num_threads)
        # Using ThreadPoolExecutor for I/O-bound tasks (like ES calls, LLM calls within graph)
        # If CPU-bound work becomes dominant (e.g., very complex local processing),
        # consider ProcessPoolExecutor, but ensure state/objects are pickleable.
        Executor = ThreadPoolExecutor

        with Executor(max_workers=effective_num_workers) as executor:
            future_to_group = {}
            for group_info in groups_to_process:
                group_name = group_info["group_name"]
                # Create the specific config for this group
                current_config = {**single_group_base_config, "group_name": group_name}
                # Submit the worker task
                future = executor.submit(
                    _parallel_group_worker_new, # Use the updated worker
                    current_config,             # Pass the full config dict
                    self._prompts_manager.json_file # Pass prompts path
                )
                future_to_group[future] = group_name

            for future in as_completed(future_to_group):
                group_name_future = future_to_group[future]
                try:
                    # Worker returns (group_name, final_state_dict)
                    _, final_state_result = future.result()
                    result_state["group_results"][group_name_future] = final_state_result
                    status_report = final_state_result.get('final_parsing_status', 'unknown')
                    self._logger.info(f"Received result for group: {group_name_future}. Status: {status_report}")
                except Exception as e:
                     self._logger.error(f"Error retrieving result for group '{group_name_future}': {e}", exc_info=True)
                     # Construct and store a basic failed state if future fails badly
                     failed_state_info: SingleGroupParseGraphState = {
                         **single_group_base_config, # Base config
                         "group_name": group_name_future,
                         "source_index": "", "target_index": "", "failed_index": "", "current_attempt": 0,
                         "current_grok_pattern": None, "last_failed_pattern": None,
                         "sample_lines_for_generation": [], "sample_lines_for_validation": [],
                         "validation_passed": False,
                         "final_parsing_status": "failed (orchestrator error)",
                         "final_parsing_results_summary": None,
                         "error_messages": [f"Orchestrator failed to get result: {e}"]
                     }
                     result_state["group_results"][group_name_future] = failed_state_info

        result_state["status"] = "completed"
        self._logger.info("AllGroupsParserAgent run finished.")
        return result_state
