# src/logllm/agents/es_parser_agent.py
import os
import time
import pandas as pd
from typing import TypedDict, Dict, List, Optional, Tuple, Any, Callable
from pygrok import Grok
from pydantic import BaseModel, Field
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from langgraph.graph import StateGraph, END
from langgraph.graph.graph import CompiledGraph

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
class ScrollGrokParserState(TypedDict):
    source_index: str
    target_index: str
    grok_pattern: str
    field_to_parse: str
    source_query: Optional[Dict[str, Any]]
    fields_to_copy: Optional[List[str]]
    batch_size: int # <--- Added Batch Size
    # Results
    processed_count: int
    indexed_count: int
    error_count: int
    status: str

class SingleGroupParseGraphState(TypedDict):
    # Input configuration
    group_name: str
    source_index: str
    target_index: str
    field_to_parse: str
    fields_to_copy: Optional[List[str]]
    sample_size_generation: int # How many samples for LLM generation
    sample_size_validation: int # How many samples for pattern validation
    validation_threshold: float # Min success rate (0.0-1.0) for validation pass
    batch_size: int
    max_regeneration_attempts: int

    # Dynamic state during run
    current_attempt: int
    current_grok_pattern: Optional[str]
    last_failed_pattern: Optional[str] # Store the previously failed pattern
    sample_lines_for_generation: List[str]
    sample_lines_for_validation: List[str]
    validation_passed: bool
    final_parsing_status: str # e.g., "success", "success_fallback", "failed"
    final_parsing_results: Optional[Dict[str, Any]] # Results from ScrollGrokParserAgent
    error_messages: List[str] # Accumulate errors

class AllGroupsParserState(TypedDict):
    group_info_index: str
    field_to_parse: str
    fields_to_copy: Optional[List[str]]
    # Note: batch_size and sample_size are passed into run, not stored here
    # Results per group
    group_results: Dict[str, SingleGroupParseGraphState]
    status: str

def _parallel_group_worker_new(
    single_group_config: Dict[str, Any], # Pass the combined config dict
    prompts_json_path: str
    # Add other args needed for dependency init if required (e.g., db_url, model_name)
) -> Tuple[str, SingleGroupParseGraphState]: # <-- UPDATED RETURN TYPE HINT
    """
    Worker function for parallel execution. Initializes its own dependencies
    and runs the SingleGroupParserAgent (which uses LangGraph).
    Returns the group name and the final state dictionary from the graph run.
    """
    group_name = single_group_config.get("group_name", "UnknownGroup")
    worker_logger = Logger() # Independent logger for the worker
    worker_logger.info(f"[Worker-{os.getpid()}] Processing Group: {group_name}")

    try:
        # Initialize dependencies within the worker
        # Ensure these classes can be initialized using environment variables or defaults
        # Needs access to cfg constants like ELASTIC_SEARCH_URL, GEMINI_LLM_MODEL
        db_worker = ElasticsearchDatabase()
        if db_worker.instance is None:
            raise ConnectionError("Worker failed to connect to Elasticsearch.")

        # Needs access to API keys (ensure environment variables are inherited by workers)
        model_worker = GeminiModel() # Consider passing model name via config if needed
        prompts_manager_worker = PromptsManager(json_file=prompts_json_path)

        # Instantiate the LangGraph-based agent for this worker
        sg_agent_worker = SingleGroupParserAgent(
            model=model_worker,
            db=db_worker,
            prompts_manager=prompts_manager_worker
        )

        # Run the agent with the provided config dictionary
        # The agent's run method executes the internal LangGraph
        final_state: SingleGroupParseGraphState = sg_agent_worker.run(single_group_config)

        worker_logger.info(f"[Worker-{os.getpid()}] Finished Group: {group_name}, Final Status: {final_state.get('final_parsing_status', 'unknown')}")
        # Return the group name and the entire final state dictionary
        return group_name, final_state

    except Exception as e:
        worker_logger.error(f"[Worker-{os.getpid()}] CRITICAL Error processing group '{group_name}': {e}", exc_info=True)

        # Construct a failed state dictionary matching SingleGroupParseGraphState structure
        # Ensure all required keys from the TypedDict are present
        failed_state: SingleGroupParseGraphState = {
            # --- Copy required fields from input config ---
            "group_name": group_name,
            "field_to_parse": single_group_config.get('field_to_parse', 'content'),
            "fields_to_copy": single_group_config.get('fields_to_copy'),
            "sample_size_generation": single_group_config.get('sample_size_generation', 10),
            "sample_size_validation": single_group_config.get('sample_size_validation', 10),
            "validation_threshold": single_group_config.get('validation_threshold', 0.5),
            "batch_size": single_group_config.get('batch_size', 5000),
            "max_regeneration_attempts": single_group_config.get('max_regeneration_attempts', 3),
            # --- Set default/failure values for dynamic state ---
            "source_index": "", # Indicate failure to determine
            "target_index": "",
            "current_attempt": 0, # Indicate run didn't proceed normally
            "current_grok_pattern": None,
            "last_failed_pattern": None,
            "sample_lines_for_generation": [],
            "sample_lines_for_validation": [],
            "validation_passed": False,
            # --- Set final status and results to reflect failure ---
            "final_parsing_status": "failed (worker critical error)",
            "final_parsing_results": None, # No results from scroll parser
            "error_messages": [f"Worker critical error: {e}"]
        }
        return group_name, failed_state

# --- ScrollGrokParserAgent ---
class ScrollGrokParserAgent:
    # Removed hardcoded BATCH_SIZE
    # BATCH_SIZE = 500
    _current_batch_data: List[Tuple[str, Dict[str, Any]]] = []

    def __init__(self, db: ElasticsearchDatabase):
        self._db = db
        self._logger = Logger()
        self._grok_instance: Optional[Grok] = None
        self._current_batch: List[Dict[str, Any]] = []
        self._errors_in_batch: List[Dict[str, Any]] = []
        self._total_processed = 0
        self._total_indexed_successfully = 0
        self._total_parse_failures = 0
        self._total_index_failures = 0
        self._batch_size_this_run: int = 5000 # Default, will be set in run()

    # _initialize_grok (remains the same)
    def _initialize_grok(self, pattern: str) -> bool:
        try:
            self._grok_instance = Grok(pattern)
            self._logger.info("Grok pattern compiled successfully.")
            return True
        except ValueError as e:
            self._logger.error(f"Invalid Grok pattern syntax: {pattern} - Error: {e}", exc_info=True)
            self._grok_instance = None
            return False

    # _process_single_hit (remains the same)
    def _process_single_hit(
        self,
        hit: Dict[str, Any],
        field_to_parse: str,
        fields_to_copy: Optional[List[str]]
    ) -> Optional[Tuple[str, Dict[str, Any]]]: # Return tuple (id, doc)
        """Parses a single document hit and prepares it for indexing, including its original ID."""
        if self._grok_instance is None: return None # Grok not ready

        source_doc = hit.get("_source", {})
        source_id = hit.get("_id") # <-- Get the source document ID

        if not source_id:
            self._logger.warning(f"Source document missing '_id'. Skipping hit.")
            # This shouldn't happen with standard ES results, but good to check
            return None

        original_content = source_doc.get(field_to_parse)
        if not isinstance(original_content, str):
            self._logger.warning(f"Field '{field_to_parse}' not found/string in doc ID {source_id}. Skipping.")
            self._total_parse_failures += 1
            return None

        parsed_fields = self._grok_instance.match(original_content)
        if parsed_fields:
            target_doc = parsed_fields.copy()
            # ... (timestamp handling, copy fields logic - remains the same) ...
            if 'timestamp' not in target_doc and '@timestamp' in source_doc:
                 target_doc['@original_timestamp'] = source_doc['@timestamp']
            elif 'timestamp' in target_doc and '@timestamp' not in target_doc:
                 target_doc['@timestamp'] = target_doc['timestamp']
            if fields_to_copy:
                for field in fields_to_copy:
                    if field in source_doc and field not in target_doc:
                        target_doc[field] = source_doc[field]

            # Return the original ID along with the parsed doc
            return source_id, target_doc
        else:
            self._total_parse_failures += 1
            return None

    # Modified _process_batch to store (id, doc) tuples
    def _process_batch(self, hits: List[Dict[str, Any]], state: ScrollGrokParserState) -> bool:
        """Processes a batch of hits, storing (source_id, parsed_doc) pairs."""
        self._logger.debug(f"Processing batch of {len(hits)} hits...")
        field_to_parse = state['field_to_parse']
        fields_to_copy = state.get('fields_to_copy')

        for hit in hits:
             processed_data = self._process_single_hit(hit, field_to_parse, fields_to_copy)
             if processed_data: # processed_data is now (source_id, parsed_doc)
                  self._current_batch_data.append(processed_data)

        # Index the accumulated batch if it's large enough
        if len(self._current_batch_data) >= self._batch_size_this_run:
            self._flush_batch(state['target_index'])

        return True # Continue scrolling

    # Modified _flush_batch to format update/upsert actions and use bulk_operation
    def _flush_batch(self, target_index: str):
        """Formats update/upsert actions and indexes the current batch."""
        if not self._current_batch_data:
            return

        self._logger.info(f"Preparing bulk update/upsert batch of {len(self._current_batch_data)} documents for '{target_index}'...")

        bulk_actions = []
        for source_id, parsed_doc in self._current_batch_data:
            # Action dictionary for the 'update' operation
            action = {
                "update": {
                    "_index": target_index,
                    "_id": source_id # Use the source document's ID
                }
            }
            # Data dictionary for the update, specifying the doc and enabling upsert
            data = {
                "doc": parsed_doc,
                "doc_as_upsert": True
            }
            # Append both the action and the data line to the list
            # NOTE: helpers.bulk can sometimes handle this structure automatically,
            # but explicitly creating the action/data pairs is safer across versions.
            # Let's try the simpler format first, which helpers.bulk often accepts:
            simplified_action = {
                "_op_type": "update", # Explicitly setting op_type
                "_index": target_index,
                "_id": source_id,
                "doc": parsed_doc,
                "doc_as_upsert": True
            }
            bulk_actions.append(simplified_action)


        # Use the modified bulk_operation method
        success_count, errors = self._db.bulk_operation(actions=bulk_actions)

        self._total_indexed_successfully += success_count # Count includes both updates and inserts
        self._total_index_failures += len(errors)
        if errors:
             self._errors_in_batch.extend(errors)
             self._logger.warning(f"{len(errors)} errors occurred during bulk update/upsert.")

        # Clear the processed data batch
        self._current_batch_data = []

    # run method (Reset the correct batch list)
    def run(self, initial_state: ScrollGrokParserState) -> ScrollGrokParserState:
        self._batch_size_this_run = initial_state['batch_size']
        self._logger.info(f"Starting ScrollGrokParserAgent run. Source: '{initial_state['source_index']}', Target: '{initial_state['target_index']}', Batch Size: {self._batch_size_this_run}")
        result_state = initial_state.copy()
        result_state["status"] = "running"

        # Reset internal counters and the correct batch list
        self._current_batch_data = [] # <--- Reset this list
        self._errors_in_batch = []
        self._total_processed = 0
        self._total_indexed_successfully = 0
        self._total_parse_failures = 0
        self._total_index_failures = 0
        # ... (rest of the run method remains the same: initialize grok, scroll, flush final batch, populate results) ...
        if not self._initialize_grok(initial_state['grok_pattern']):
            result_state["status"] = "failed"; result_state["error_count"] = 1
            return result_state

        source_query = initial_state.get("source_query") or {"query": {"match_all": {}}}
        fields_needed = set([initial_state['field_to_parse']])
        if initial_state.get('fields_to_copy'): fields_needed.update(initial_state['fields_to_copy'])
        if '@timestamp' not in fields_needed: fields_needed.add('@timestamp')
        source_fields_list = list(fields_needed)

        try:
            def batch_processor(hits: List[Dict[str, Any]]) -> bool:
                return self._process_batch(hits, result_state)

            processed_count, _ = self._db.scroll_and_process_batches(
                index=initial_state['source_index'],
                query=source_query,
                batch_size=initial_state['batch_size'],
                process_batch_func=batch_processor,
                source_fields=source_fields_list
            )
            self._total_processed = processed_count
            self._flush_batch(initial_state['target_index']) # Flush remaining
            result_state["status"] = "completed"
            self._logger.info("ScrollGrokParserAgent run completed.")

        except Exception as e:
            result_state["status"] = "failed"
            self._logger.error(f"Run failed during scroll/processing: {e}", exc_info=True)
            try: self._flush_batch(initial_state['target_index'])
            except Exception as flush_err: self._logger.error(f"Error flushing final batch: {flush_err}")

        result_state["processed_count"] = self._total_processed
        result_state["indexed_count"] = self._total_indexed_successfully
        result_state["error_count"] = self._total_parse_failures + self._total_index_failures
        self._logger.info(f"Run Summary: Processed={self._total_processed}, Indexed OK={self._total_indexed_successfully}, Parse Failures={self._total_parse_failures}, Index Failures={self._total_index_failures}")
        return result_state


# --- NEW SingleGroupParserAgent (Refactored with LangGraph) ---
class SingleGroupParserAgent:
    # Constants
    FALLBACK_PATTERN = "%{GREEDYDATA:original_content}" # Use specific field name

    def __init__(self, model: LLMModel, db: ElasticsearchDatabase, prompts_manager: PromptsManager):
        self._model = model
        self._db = db
        self._prompts_manager = prompts_manager
        self._logger = Logger()
        # Keep instance of the scroll parser
        self._scroll_parser_agent = ScrollGrokParserAgent(db)
        # Compile graph on init
        self.graph = self._build_graph()

    # --- Graph Nodes ---

    def _start_node(self, state: SingleGroupParseGraphState) -> SingleGroupParseGraphState | Dict[str, Any]:
        """Initializes indices, fetches samples."""
        self._logger.info(f"[{state['group_name']}] Starting graph run...")
        errors = []
        source_index = ""
        target_index = ""
        samples_gen = []
        samples_val = []

        try:
            source_index = cfg.get_log_storage_index(state['group_name'])
            target_index = cfg.get_parsed_log_storage_index(state['group_name'])
            self._logger.info(f"[{state['group_name']}] Indices: Source='{source_index}', Target='{target_index}'")

            # Fetch samples for generation
            self._logger.info(f"[{state['group_name']}] Fetching {state['sample_size_generation']} samples for generation...")
            samples_gen = self._db.get_sample_lines(
                index=source_index, field=state['field_to_parse'], sample_size=state['sample_size_generation']
            )
            if not samples_gen:
                self._logger.warning(f"[{state['group_name']}] No samples found for generation.")
                # Don't necessarily fail here, generation might still work generically or pattern is provided

            # Fetch samples for validation (can be the same or different set)
            # For simplicity, let's fetch again. Could reuse if sample sizes are same.
            self._logger.info(f"[{state['group_name']}] Fetching {state['sample_size_validation']} samples for validation...")
            samples_val = self._db.get_sample_lines(
                index=source_index, field=state['field_to_parse'], sample_size=state['sample_size_validation']
            )
            if not samples_val:
                # If validation samples are missing, validation cannot proceed.
                msg = f"[{state['group_name']}] No samples found for validation. Cannot validate pattern."
                self._logger.error(msg)
                errors.append(msg)
                # This is likely a fatal error for the validation path
                # We might need a direct edge to fallback/fail from here later

        except Exception as e:
            msg = f"[{state['group_name']}] Error during start node: {e}"
            self._logger.error(msg, exc_info=True)
            errors.append(msg)

        return {
            "source_index": source_index,
            "target_index": target_index,
            "sample_lines_for_generation": samples_gen,
            "sample_lines_for_validation": samples_val,
            "error_messages": errors,
             # Reset dynamic state parts for this run
            "current_attempt": 1,
            "current_grok_pattern": None,
            "last_failed_pattern": None,
            "validation_passed": False,
            "final_parsing_status": "pending",
            "final_parsing_results": None
        }

    def _generate_grok_node(self, state: SingleGroupParseGraphState) -> SingleGroupParseGraphState | Dict[str, Any]:
        """Generates Grok pattern using LLM."""
        group_name = state['group_name']
        attempt = state['current_attempt']
        self._logger.info(f"[{group_name}] Attempt {attempt}: Generating Grok pattern...")
        samples = state['sample_lines_for_generation']
        last_failed = state.get('last_failed_pattern') # Get potentially stored failed pattern
        errors = state.get('error_messages', [])
        generated_pattern: Optional[str] = None

        if not samples:
            msg = f"[{group_name}] No samples available for generation on attempt {attempt}."
            self._logger.warning(msg)
            # errors.append(msg) # Maybe not an error, just can't generate
            return {"current_grok_pattern": None, "error_messages": errors}

        try:
            # Prepare context about previous failure, if any
            failed_pattern_context = ""
            if last_failed:
                failed_pattern_context = f"\nIMPORTANT: The previous attempt using the pattern '{last_failed}' failed to parse logs correctly. Please generate a DIFFERENT and potentially better pattern.\n"

            # --- Use PromptsManager ---
            # Ensure this key matches your prompts.json structure
            prompt = self._prompts_manager.get_prompt(
                sample_logs_for_generation=str(samples), # Pass correct variable
                last_failed_pattern_context=failed_pattern_context # Pass context
            )

            response = self._model.generate(prompt, schema=GrokPatternSchema)

            if response and isinstance(response, GrokPatternSchema) and response.grok_pattern:
                pattern = response.grok_pattern.strip()
                if "%{" in pattern and "}" in pattern:
                    self._logger.info(f"[{group_name}] LLM generated Grok pattern (Attempt {attempt}): {pattern}")
                    generated_pattern = pattern
                else:
                     msg = f"[{group_name}] LLM response on attempt {attempt} doesn't look like a valid Grok pattern: {pattern}"
                     self._logger.warning(msg)
                     errors.append(msg)
            else:
                msg = f"[{group_name}] LLM did not return a valid pattern on attempt {attempt}. Response: {response}"
                self._logger.warning(msg)
                errors.append(msg)

        except ValueError as ve: # Prompt formatting/variable errors
             msg = f"[{group_name}] Error formatting prompt for Grok generation (Attempt {attempt}): {ve}"
             self._logger.error(msg, exc_info=True)
             errors.append(msg)
        except Exception as e:
            msg = f"[{group_name}] LLM call failed during Grok generation (Attempt {attempt}): {e}"
            self._logger.error(msg, exc_info=True)
            errors.append(msg)

        return {"current_grok_pattern": generated_pattern, "error_messages": errors}

    def _validate_pattern_node(self, state: SingleGroupParseGraphState) -> SingleGroupParseGraphState | Dict[str, Any]:
        """Validates the current Grok pattern on a sample."""
        group_name = state['group_name']
        pattern = state.get('current_grok_pattern')
        validation_samples = state.get('sample_lines_for_validation', [])
        threshold = state.get('validation_threshold', 0.5) # Default 50% success rate
        errors = state.get('error_messages', [])
        validation_passed = False

        self._logger.info(f"[{group_name}] Validating pattern: {pattern}")

        if not pattern:
            msg = f"[{group_name}] No pattern provided to validation node."
            self._logger.warning(msg)
            errors.append(msg)
            return {"validation_passed": False, "error_messages": errors}

        if not validation_samples:
            msg = f"[{group_name}] No samples available for validation."
            self._logger.warning(msg)
            errors.append(msg)
            # Can't validate, treat as failure? Or skip validation? Let's fail validation.
            return {"validation_passed": False, "error_messages": errors}

        try:
            grok = Grok(pattern)
            parsed_count = 0
            total_validated = 0
            for line in validation_samples:
                line = line.strip()
                if not line: continue
                total_validated += 1
                if grok.match(line):
                    parsed_count += 1

            if total_validated == 0:
                 self._logger.warning(f"[{group_name}] No non-empty lines in validation sample.")
                 # Treat as validation failure if no lines could be checked
                 validation_passed = False
            else:
                success_rate = parsed_count / total_validated
                self._logger.info(f"[{group_name}] Validation Result: Parsed {parsed_count}/{total_validated} samples. Success Rate: {success_rate:.2f}")
                if success_rate >= threshold:
                    self._logger.info(f"[{group_name}] Validation PASSED (>= {threshold:.2f}).")
                    validation_passed = True
                else:
                    self._logger.warning(f"[{group_name}] Validation FAILED (< {threshold:.2f}).")
                    validation_passed = False

        except ValueError as e: # Invalid Grok pattern syntax
            msg = f"[{group_name}] Invalid Grok pattern syntax during validation: {pattern} - Error: {e}"
            self._logger.error(msg, exc_info=True)
            errors.append(msg)
            validation_passed = False
        except Exception as e:
            msg = f"[{group_name}] Error during pattern validation: {e}"
            self._logger.error(msg, exc_info=True)
            errors.append(msg)
            validation_passed = False

        return {"validation_passed": validation_passed, "error_messages": errors}


    def _parse_all_node(self, state: SingleGroupParseGraphState) -> SingleGroupParseGraphState | Dict[str, Any]:
        """Parses the entire group using the validated pattern."""
        group_name = state['group_name']
        pattern = state['current_grok_pattern'] # Assumes validation passed
        self._logger.info(f"[{group_name}] Validation passed. Proceeding to parse all documents with pattern: {pattern}")

        # Prepare config for ScrollGrokParserAgent
        scroll_config = {
            "source_index": state['source_index'],
            "target_index": state['target_index'],
            "grok_pattern": pattern,
            "field_to_parse": state['field_to_parse'],
            "fields_to_copy": state.get('fields_to_copy'),
            "batch_size": state['batch_size'],
            "source_query": {"query": {"match_all": {}}} # Or use a more specific query if needed
        }

        try:
             # Run the scroll parser
             parsing_results = self._scroll_parser_agent.run(scroll_config)

             # Determine final status based on scroll parser results
             final_status = "failed" # Default
             if parsing_results.get("status") == "completed":
                 # Check if errors occurred during the completed run
                 if parsing_results.get("parse_error_count", 0) > 0 or parsing_results.get("index_error_count", 0) > 0:
                      final_status = "success_with_errors"
                      self._logger.warning(f"[{group_name}] Parse all completed but with errors.")
                 else:
                      final_status = "success"
                      self._logger.info(f"[{group_name}] Parse all completed successfully.")
             else:
                 # If scroll parser status is not 'completed', it failed
                 self._logger.error(f"[{group_name}] Parse all failed. Scroll parser status: {parsing_results.get('status')}")

             return {
                 "final_parsing_status": final_status,
                 "final_parsing_results": parsing_results
             }
        except Exception as e:
            msg = f"[{group_name}] Critical error invoking ScrollGrokParserAgent: {e}"
            self._logger.error(msg, exc_info=True)
            return {
                "final_parsing_status": "failed",
                "final_parsing_results": {"status": "failed", "error_details": [msg]},
                "error_messages": state.get("error_messages", []) + [msg]
            }

    def _fallback_node(self, state: SingleGroupParseGraphState) -> SingleGroupParseGraphState | Dict[str, Any]:
        """Parses the entire group using the fallback pattern."""
        group_name = state['group_name']
        self._logger.warning(f"[{group_name}] Executing FALLBACK parsing with pattern: {self.FALLBACK_PATTERN}")

        # Prepare config for ScrollGrokParserAgent
        scroll_config = {
            "source_index": state['source_index'],
            "target_index": state['target_index'],
            "grok_pattern": self.FALLBACK_PATTERN, # Use the fallback
            "field_to_parse": state['field_to_parse'], # Still need original field
            "fields_to_copy": state.get('fields_to_copy'),
            "batch_size": state['batch_size'],
            "source_query": {"query": {"match_all": {}}}
        }

        try:
             # Run the scroll parser
             parsing_results = self._scroll_parser_agent.run(scroll_config)
             final_status = "failed_fallback" # Default
             if parsing_results.get("status") == "completed":
                 final_status = "success_fallback" # Mark success specifically as fallback
                 self._logger.info(f"[{group_name}] Fallback parsing completed.")
             else:
                 self._logger.error(f"[{group_name}] Fallback parsing FAILED. Scroll parser status: {parsing_results.get('status')}")

             return {
                 "final_parsing_status": final_status,
                 "final_parsing_results": parsing_results
             }
        except Exception as e:
            msg = f"[{group_name}] Critical error invoking ScrollGrokParserAgent during fallback: {e}"
            self._logger.error(msg, exc_info=True)
            return {
                "final_parsing_status": "failed_fallback",
                "final_parsing_results": {"status": "failed", "error_details": [msg]},
                "error_messages": state.get("error_messages", []) + [msg]
            }

    def _prepare_for_retry_node(self, state: SingleGroupParseGraphState) -> SingleGroupParseGraphState | Dict[str, Any]:
        """Increments attempt count and stores the failed pattern."""
        group_name = state['group_name']
        current_attempt = state.get('current_attempt', 1)
        failed_pattern = state.get('current_grok_pattern')
        self._logger.info(f"[{group_name}] Preparing for retry. Storing failed pattern: {failed_pattern}")
        return {
            "current_attempt": current_attempt + 1,
            "last_failed_pattern": failed_pattern,
            "current_grok_pattern": None # Clear current pattern for regeneration
        }

    # --- Conditional Edges ---

    def _decide_after_generate(self, state: SingleGroupParseGraphState) -> str:
        """Decides whether to validate or fallback after pattern generation."""
        group_name = state['group_name']
        if state.get('current_grok_pattern'):
            self._logger.debug(f"[{group_name}] Pattern generated, moving to validation.")
            return "validate_pattern"
        else:
            # If generation failed even on first attempt, go to fallback
            # (Could add more nuanced logic here if needed)
            self._logger.warning(f"[{group_name}] Pattern generation failed, moving to fallback.")
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

    # --- Build Graph ---
    def _build_graph(self) -> CompiledGraph:
        """Builds the LangGraph StateGraph."""
        workflow = StateGraph(SingleGroupParseGraphState)

        # Add nodes
        workflow.add_node("start", self._start_node)
        workflow.add_node("generate_grok", self._generate_grok_node)
        workflow.add_node("validate_pattern", self._validate_pattern_node)
        workflow.add_node("prepare_for_retry", self._prepare_for_retry_node)
        workflow.add_node("parse_all", self._parse_all_node)
        workflow.add_node("fallback", self._fallback_node)

        # Set entry point
        workflow.set_entry_point("start")

        # Add edges
        workflow.add_edge("start", "generate_grok")

        # Conditional edge after generation
        workflow.add_conditional_edges(
            "generate_grok",
            self._decide_after_generate,
            {
                "validate_pattern": "validate_pattern",
                "fallback": "fallback",
            }
        )

        # Conditional edge after validation
        workflow.add_conditional_edges(
            "validate_pattern",
            self._decide_after_validation,
            {
                "parse_all": "parse_all",
                "prepare_for_retry": "prepare_for_retry",
                "fallback": "fallback", # Directly fallback if max retries hit here
            }
        )

        # Edge after preparing for retry
        workflow.add_edge("prepare_for_retry", "generate_grok") # Loop back to generate

        # Edges to end
        workflow.add_edge("parse_all", END)
        workflow.add_edge("fallback", END)

        # Compile the graph
        return workflow.compile()

    # --- Run Method ---
    def run(self, initial_config: Dict[str, Any]) -> SingleGroupParseGraphState | Dict[str, Any]:
        """Runs the Grok parsing graph for a single group."""
        group_name = initial_config['group_name']
        self._logger.info(f"[{group_name}] Initializing SingleGroupParserAgent run...")

        # Prepare the initial state for the graph
        graph_input: SingleGroupParseGraphState = {
            "group_name": group_name,
            "field_to_parse": initial_config['field_to_parse'],
            "fields_to_copy": initial_config.get('fields_to_copy'),
            "sample_size_generation": initial_config.get('sample_size', 10), # Use sample_size from config
            "sample_size_validation": initial_config.get('validation_sample_size', 10), # Default validation size
            "validation_threshold": initial_config.get('validation_threshold', 0.5), # Default threshold
            "batch_size": initial_config['batch_size'],
            "max_regeneration_attempts": initial_config.get('max_regeneration_attempts', 5), # Default attempts
            # --- Defaults for dynamic state ---
            "source_index": "", "target_index": "", "current_attempt": 0,
            "current_grok_pattern": None, "last_failed_pattern": None,
            "sample_lines_for_generation": [], "sample_lines_for_validation": [],
            "validation_passed": False, "final_parsing_status": "pending",
            "final_parsing_results": None, "error_messages": []
        }

        # Execute the graph
        final_state = self.graph.invoke(graph_input)

        self._logger.info(f"[{group_name}] Finished SingleGroupParserAgent run. Final Status: {final_state.get('final_parsing_status')}")
        # Return the full final state
        return final_state



# --- AllGroupsParserAgent ---
class AllGroupsParserAgent:
    def __init__(self, model: LLMModel, db: ElasticsearchDatabase, prompts_manager: PromptsManager):
        self._model = model
        self._db = db
        self._prompts_manager = prompts_manager
        self._logger = Logger()
        self._single_group_agent = SingleGroupParserAgent(model, db, prompts_manager)

    # _get_all_groups (remains the same)
    def _get_all_groups(self, group_info_index: str) -> List[Dict[str, Any]]:
        self._logger.info(f"Fetching all group definitions from index '{group_info_index}'...")
        try:
            query = {"query": {"match_all": {}}}
            groups_data = self._db.scroll_search(query=query, index=group_info_index)
            if not groups_data: return []
            valid_groups = []
            for hit in groups_data:
                 source = hit.get("_source", {})
                 group_name = source.get("group")
                 if group_name: valid_groups.append({"group_name": group_name})
            self._logger.info(f"Fetched {len(valid_groups)} valid group definitions.")
            return valid_groups
        except Exception as e:
            self._logger.error(f"Failed to fetch groups from index '{group_info_index}': {e}")
            return []

    # run (Accepts batch_size and sample_size, passes them down)
    def run(
        self,
        initial_state: AllGroupsParserState,
        num_threads: int = 1,
        batch_size: int = 5000,
        sample_size: int = 20,
        validation_sample_size: int = 10,
        validation_threshold: float = 0.5,
        max_regeneration_attempts: int = 3
    ) -> AllGroupsParserState: # Return type matches updated state
        self._logger.info(f"Starting AllGroupsParserAgent run. Workers: {num_threads}, Batch: {batch_size}, GenSample: {sample_size}, ValSample: {validation_sample_size}")
        result_state = initial_state.copy()
        result_state["status"] = "running"
        result_state["group_results"] = {} # Initialize with correct type expected

        groups_to_process = self._get_all_groups(initial_state['group_info_index'])
        if not groups_to_process:
            result_state["status"] = "completed (no groups)"; return result_state

        # --- Prepare Base Configuration Dictionary ---
        single_group_base_config = {
            "field_to_parse": initial_state['field_to_parse'],
            "fields_to_copy": initial_state.get('fields_to_copy'),
            "batch_size": batch_size,
            "sample_size_generation": sample_size, # Map CLI/run arg to state key
            "sample_size_validation": validation_sample_size,
            "validation_threshold": validation_threshold,
            "max_regeneration_attempts": max_regeneration_attempts
        }

        effective_num_workers = max(1, num_threads)

        if effective_num_workers <= 1:
            # --- Sequential Execution ---
            self._logger.info("Running group parsing sequentially.")
            sg_agent = SingleGroupParserAgent(self._model, self._db, self._prompts_manager)
            for group_info in groups_to_process:
                group_name = group_info["group_name"]
                self._logger.info(f"--- Processing Group (Seq): {group_name} ---")
                current_config = {**single_group_base_config, "group_name": group_name}
                try:
                    final_group_state: SingleGroupParseGraphState = sg_agent.run(current_config)
                    result_state["group_results"][group_name] = final_group_state
                except Exception as e:
                    self._logger.error(f"Error processing group '{group_name}' sequentially: {e}", exc_info=True)
                    # Construct and store a failed state
                    failed_state_info: SingleGroupParseGraphState = {
                         **current_config,
                         "source_index": "", "target_index": "", "current_attempt": 0,
                         "current_grok_pattern": None, "last_failed_pattern": None,
                         "sample_lines_for_generation": [], "sample_lines_for_validation": [],
                         "validation_passed": False,
                         "final_parsing_status": "failed (agent error)",
                         "final_parsing_results": None,
                         "error_messages": [f"Agent execution failed: {e}"]
                     }
                    result_state["group_results"][group_name] = failed_state_info
        else:
            # --- Parallel Execution ---
            self._logger.info(f"Running group parsing in parallel with {effective_num_workers} threads.")
            prompts_json_path = self._prompts_manager.json_file

            with ThreadPoolExecutor(max_workers=effective_num_workers) as executor:
                future_to_group = {}
                for group_info in groups_to_process:
                    group_name = group_info["group_name"]
                    current_config = {**single_group_base_config, "group_name": group_name}
                    # Submit the updated worker
                    future = executor.submit(
                        _parallel_group_worker_new, # Use the updated worker
                        current_config,             # Pass the config dict
                        prompts_json_path
                    )
                    future_to_group[future] = group_name

                for future in as_completed(future_to_group):
                    group_name_future = future_to_group[future]
                    try:
                        # Worker now returns the full final state dict
                        group_name_result, final_state_result = future.result() # Unpack tuple
                        status_report = final_state_result.get('final_parsing_status', 'unknown')
                        self._logger.info(f"Received result for group: {group_name_result}. Status: {status_report}")
                        result_state["group_results"][group_name_result] = final_state_result
                    except Exception as e:
                         self._logger.error(f"Error retrieving result for group '{group_name_future}': {e}", exc_info=True)
                         # Construct and store a failed state
                         failed_state_info: SingleGroupParseGraphState = {
                            **single_group_base_config, # Base config
                            "group_name": group_name_future,
                            "source_index": "", "target_index": "", "current_attempt": 0,
                            "current_grok_pattern": None, "last_failed_pattern": None,
                            "sample_lines_for_generation": [], "sample_lines_for_validation": [],
                            "validation_passed": False,
                            "final_parsing_status": "failed (worker error)",
                            "final_parsing_results": None,
                            "error_messages": [f"Worker execution failed: {e}"]
                         }
                         result_state["group_results"][group_name_future] = failed_state_info

        result_state["status"] = "completed"
        self._logger.info("AllGroupsParserAgent run finished.")
        return result_state
