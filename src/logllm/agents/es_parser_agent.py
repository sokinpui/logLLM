# src/logllm/agents/es_parser_agent.py
import os
import time
import pandas as pd
from typing import TypedDict, Dict, List, Optional, Tuple, Any, Callable
from pygrok import Grok
from pydantic import BaseModel, Field
import concurrent.futures

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

class SingleGroupParserState(TypedDict):
    group_name: str
    group_id_field: Optional[str]
    group_id_value: Optional[Any]
    source_index: str
    target_index: str
    field_to_parse: str
    fields_to_copy: Optional[List[str]]
    batch_size: int # <--- Added Batch Size (to pass down)
    sample_size: int # <--- Added Sample Size
    # State/Results
    generated_grok_pattern: Optional[str]
    parsing_status: str
    parsing_result: Optional[ScrollGrokParserState]

class AllGroupsParserState(TypedDict):
    group_info_index: str
    field_to_parse: str
    fields_to_copy: Optional[List[str]]
    # Note: batch_size and sample_size are passed into run, not stored here
    # Results per group
    group_results: Dict[str, SingleGroupParserState]
    status: str

def _parallel_group_worker(
    group_info: Dict[str, Any],
    field_to_parse: str,
    fields_to_copy: Optional[List[str]],
    batch_size: int,
    sample_size: int,
    prompts_json_path: str # Need path to initialize PromptsManager in worker
    # Add other necessary config if needed (e.g., model name, db url)
) -> Tuple[str, SingleGroupParserState]:
    """
    Worker function executed by each process to parse a single group.
    Initializes its own dependencies.
    """
    group_name = group_info.get("group_name", "UnknownGroup")
    # Initialize dependencies within the worker process
    # This ensures objects are created in the child process, avoiding pickle issues
    worker_logger = Logger() # Or configure logging specific to workers if needed
    worker_logger.info(f"[Worker-{os.getpid()}] Processing Group: {group_name}")

    try:
        # It's generally safer to re-initialize potentially non-pickleable/stateful objects
        db_worker = ElasticsearchDatabase()
        if db_worker.instance is None:
            raise ConnectionError("Worker failed to connect to Elasticsearch.")

        # Model initialization needs API keys (ensure env vars are inherited)
        model_worker = GeminiModel() # Or pass model name if configurable

        # PromptsManager needs the path to the JSON file
        prompts_manager_worker = PromptsManager(json_file=prompts_json_path)

        # Initialize the agent that handles the single group logic
        sg_agent_worker = SingleGroupParserAgent(
            model=model_worker,
            db=db_worker,
            prompts_manager=prompts_manager_worker
        )

        # Prepare the initial state for the single group agent
        single_group_state: SingleGroupParserState = {
            "group_name": group_name,
            "field_to_parse": field_to_parse,
            "fields_to_copy": fields_to_copy,
            "batch_size": batch_size,
            "sample_size": sample_size,
            # Set defaults or derive from group_info if needed
            "group_id_field": None,
            "group_id_value": None,
            "source_index": "", # Will be set by agent run
            "target_index": "", # Will be set by agent run
            "generated_grok_pattern": None,
            "parsing_status": "pending",
            "parsing_result": None
        }

        # Run the single group parsing logic
        final_state = sg_agent_worker.run(single_group_state)
        worker_logger.info(f"[Worker-{os.getpid()}] Finished Group: {group_name}, Status: {final_state['parsing_status']}")
        return group_name, final_state

    except Exception as e:
        worker_logger.error(f"[Worker-{os.getpid()}] Error processing group '{group_name}': {e}", exc_info=True)
        # Return a failed state if an unexpected error occurs during worker execution
        failed_state: SingleGroupParserState = {
             "group_name": group_name, "parsing_status": "failed",
             "field_to_parse": field_to_parse, "fields_to_copy": fields_to_copy,
             "batch_size": batch_size, "sample_size": sample_size,
             "source_index": "", "target_index": "", "generated_grok_pattern": None,
             "parsing_result": None # Indicate failure
        }
        return group_name, failed_state

# --- ScrollGrokParserAgent ---
class ScrollGrokParserAgent:
    # Removed hardcoded BATCH_SIZE
    # BATCH_SIZE = 500

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
    ) -> Optional[Dict[str, Any]]:
        if self._grok_instance is None: return None
        source_doc = hit.get("_source", {})
        original_content = source_doc.get(field_to_parse)
        if not isinstance(original_content, str):
            self._logger.warning(f"Field '{field_to_parse}' not found/string in doc ID {hit.get('_id')}. Skipping.")
            self._total_parse_failures += 1
            return None
        parsed_fields = self._grok_instance.match(original_content)
        if parsed_fields:
            target_doc = parsed_fields.copy()
            # Handle timestamp logic (optional)
            if 'timestamp' not in target_doc and '@timestamp' in source_doc:
                 target_doc['@original_timestamp'] = source_doc['@timestamp']
            elif 'timestamp' in target_doc and '@timestamp' not in target_doc:
                 target_doc['@timestamp'] = target_doc['timestamp']
            # Copy fields
            if fields_to_copy:
                for field in fields_to_copy:
                    if field in source_doc and field not in target_doc:
                        target_doc[field] = source_doc[field]
            return target_doc
        else:
            self._total_parse_failures += 1
            return None

    # _process_batch (Uses self._batch_size_this_run)
    def _process_batch(self, hits: List[Dict[str, Any]], state: ScrollGrokParserState) -> bool:
        self._logger.debug(f"Processing batch of {len(hits)} hits...")
        field_to_parse = state['field_to_parse']
        fields_to_copy = state.get('fields_to_copy')

        for hit in hits:
             parsed_doc = self._process_single_hit(hit, field_to_parse, fields_to_copy)
             if parsed_doc:
                  self._current_batch.append(parsed_doc)

        # Index the accumulated batch if it's large enough (use instance var)
        if len(self._current_batch) >= self._batch_size_this_run:
            self._flush_batch(state['target_index'])

        return True # Continue scrolling

    # _flush_batch (remains the same)
    def _flush_batch(self, target_index: str):
        if not self._current_batch: return
        self._logger.info(f"Indexing batch of {len(self._current_batch)} parsed documents to '{target_index}'...")
        success_count, errors = self._db.bulk_index(self._current_batch, target_index)
        self._total_indexed_successfully += success_count
        self._total_index_failures += len(errors)
        if errors:
             self._errors_in_batch.extend(errors)
             self._logger.warning(f"{len(errors)} errors during bulk indexing.")
        self._current_batch = []

    # run (Sets self._batch_size_this_run and uses state['batch_size'] for DB call)
    def run(self, initial_state: ScrollGrokParserState) -> ScrollGrokParserState:
        self._batch_size_this_run = initial_state['batch_size'] # <--- Set instance batch size
        self._logger.info(f"Starting ScrollGrokParserAgent run. Source: '{initial_state['source_index']}', Target: '{initial_state['target_index']}', Batch Size: {self._batch_size_this_run}")
        result_state = initial_state.copy()
        result_state["status"] = "running"
        # ... (Reset internal counters) ...
        self._current_batch = []
        self._errors_in_batch = []
        self._total_processed = 0
        self._total_indexed_successfully = 0
        self._total_parse_failures = 0
        self._total_index_failures = 0


        if not self._initialize_grok(initial_state['grok_pattern']):
            result_state["status"] = "failed"; result_state["error_count"] = 1
            return result_state

        source_query = initial_state.get("source_query") or {"query": {"match_all": {}}} # Ensure query is wrapped correctly
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
                batch_size=initial_state['batch_size'], # <--- Pass batch size to DB method
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


# --- SingleGroupParserAgent ---
class SingleGroupParserAgent:
    # Removed hardcoded SAMPLE_SIZE
    # SAMPLE_SIZE = 20

    def __init__(self, model: LLMModel, db: ElasticsearchDatabase, prompts_manager: PromptsManager):
        self._model = model
        self._db = db
        self._prompts_manager = prompts_manager
        self._logger = Logger()
        self._scroll_parser_agent = ScrollGrokParserAgent(db)

    # _get_sample_lines (Accepts sample_size)
    def _get_sample_lines(self, source_index: str, field_to_parse: str, sample_size: int) -> List[str]: # <--- Added sample_size arg
        self._logger.info(f"Fetching {sample_size} sample lines for field '{field_to_parse}' from index '{source_index}'...")
        samples = self._db.get_sample_lines(
            index=source_index,
            field=field_to_parse,
            sample_size=sample_size # <--- Use provided sample size
        )
        if not samples: self._logger.warning(f"Could not retrieve samples from index '{source_index}'.")
        return samples

    # _generate_grok_pattern (remains the same)
    def _generate_grok_pattern(self, sample_logs: List[str]) -> Optional[str]:
        if not sample_logs: return None
        try:
            prompt_key = "logllm.agents.parser_agent.SimpleGrokLogParserAgent._generate_grok_pattern"
            prompt = self._prompts_manager.get_prompt(metadata=prompt_key, sample_logs=str(sample_logs))
            self._logger.info("Requesting Grok pattern from LLM...")
            response = self._model.generate(prompt, schema=GrokPatternSchema)
            if response and isinstance(response, GrokPatternSchema) and response.grok_pattern:
                pattern = response.grok_pattern.strip()
                if "%{" in pattern and "}" in pattern:
                    self._logger.info(f"LLM generated Grok pattern: {pattern}")
                    return pattern
            self._logger.warning(f"LLM did not return valid Grok pattern. Response: {response}")
            return None
        except Exception as e:
            self._logger.error(f"Error during Grok pattern generation: {e}", exc_info=True)
            return None

    # run (Uses sample_size from state, passes batch_size down)
    def run(self, initial_state: SingleGroupParserState) -> SingleGroupParserState:
        group_name = initial_state['group_name']
        sample_size = initial_state['sample_size'] # <--- Get sample size
        batch_size = initial_state['batch_size']   # <--- Get batch size
        self._logger.info(f"Starting SingleGroupParserAgent run for group: '{group_name}', SampleSize: {sample_size}, BatchSize: {batch_size}")
        result_state = initial_state.copy()
        # ... (rest of initialization) ...
        result_state["parsing_status"] = "running"
        result_state["generated_grok_pattern"] = None
        result_state["parsing_result"] = None

        try:
             source_index = cfg.get_log_storage_index(group_name)
             target_index = cfg.get_parsed_log_storage_index(group_name)
             result_state["source_index"] = source_index
             result_state["target_index"] = target_index
        except Exception as e:
             self._logger.error(f"Failed to determine indices for group '{group_name}': {e}")
             result_state["parsing_status"] = "failed"; return result_state

        field_to_parse = initial_state['field_to_parse']
        # Use the sample_size from the state
        sample_lines = self._get_sample_lines(source_index, field_to_parse, sample_size)
        if not sample_lines:
            self._logger.warning(f"No sample lines found for group '{group_name}'. Cannot generate pattern.")
            result_state["parsing_status"] = "failed"; return result_state

        grok_pattern = self._generate_grok_pattern(sample_lines)
        if not grok_pattern:
            self._logger.error(f"Failed to generate Grok pattern for group '{group_name}'.")
            result_state["parsing_status"] = "failed"; return result_state
        result_state["generated_grok_pattern"] = grok_pattern
        result_state["parsing_status"] = "pattern_generated"

        source_query = {"query": {"match_all": {}}} # Ensure query is wrapped

        # Prepare state for the lower-level agent, passing the batch_size
        scroll_parser_state: ScrollGrokParserState = {
            "source_index": source_index,
            "target_index": target_index,
            "grok_pattern": grok_pattern,
            "field_to_parse": field_to_parse,
            "source_query": source_query,
            "fields_to_copy": initial_state.get("fields_to_copy"),
            "batch_size": batch_size, # <--- Pass batch size down
            "processed_count": 0, "indexed_count": 0, "error_count": 0, "status": "pending"
        }

        try:
             self._logger.info(f"Invoking ScrollGrokParserAgent for group '{group_name}'...")
             result_state["parsing_status"] = "parsing_running"
             parsing_result = self._scroll_parser_agent.run(scroll_parser_state)
             result_state["parsing_result"] = parsing_result
             if parsing_result["status"] == "completed":
                  result_state["parsing_status"] = "completed"
                  self._logger.info(f"Successfully completed parsing for group '{group_name}'.")
             else:
                  result_state["parsing_status"] = "failed"
                  self._logger.error(f"Parsing failed for group '{group_name}'.")
        except Exception as e:
             self._logger.error(f"Error invoking ScrollGrokParserAgent for group '{group_name}': {e}")
             result_state["parsing_status"] = "failed"
             if 'parsing_result' not in result_state or result_state["parsing_result"] is None:
                  scroll_parser_state["status"] = "failed"
                  result_state["parsing_result"] = scroll_parser_state

        return result_state


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
        num_threads: int = 1, # Note: Argument name is threads, but uses ProcessPoolExecutor
        batch_size: int = 5000,
        sample_size: int = 20
    ) -> AllGroupsParserState:
        self._logger.info(f"Starting AllGroupsParserAgent run. Group Index: '{initial_state['group_info_index']}'. Workers: {num_threads}, BatchSize: {batch_size}, SampleSize: {sample_size}")
        result_state = initial_state.copy()
        result_state["status"] = "running"
        result_state["group_results"] = {}

        groups_to_process = self._get_all_groups(initial_state['group_info_index'])
        if not groups_to_process:
             result_state["status"] = "completed"; return result_state

        field_to_parse = initial_state['field_to_parse']
        fields_to_copy = initial_state.get('fields_to_copy')
        effective_num_workers = max(1, num_threads) # Use 'workers' internally for clarity

        # Need the path for the prompts file to pass to workers
        prompts_json_path = self._prompts_manager.json_file

        if effective_num_workers <= 1:
            # --- Sequential Execution (remains largely the same) ---
            self._logger.info("Running group parsing sequentially.")
            for group_info in groups_to_process:
                group_name = group_info["group_name"]
                self._logger.info(f"--- Processing Group: {group_name} ---")
                single_group_state: SingleGroupParserState = {
                    "group_name": group_name,
                    "field_to_parse": field_to_parse,
                    "fields_to_copy": fields_to_copy,
                    "batch_size": batch_size,
                    "sample_size": sample_size,
                    "group_id_field": None,"group_id_value": None,"source_index": "","target_index": "",
                    "generated_grok_pattern": None,"parsing_status": "pending","parsing_result": None
                }
                try:
                    final_group_state = self._single_group_agent.run(single_group_state)
                    result_state["group_results"][group_name] = final_group_state
                except Exception as e:
                    self._logger.error(f"Error processing group '{group_name}' sequentially: {e}")
                    single_group_state["parsing_status"] = "failed"
                    result_state["group_results"][group_name] = single_group_state
        else:
            # --- Parallel Execution (Use the top-level worker) ---
            self._logger.info(f"Running group parsing in parallel with {effective_num_workers} workers.")
            with concurrent.futures.ProcessPoolExecutor(max_workers=effective_num_workers) as executor:
                future_to_group = {
                    # Submit the top-level worker function, passing necessary args
                    executor.submit(
                        _parallel_group_worker, # The top-level function
                        group_info,
                        field_to_parse,
                        fields_to_copy,
                        batch_size,
                        sample_size,
                        prompts_json_path # Pass the path
                     ): group_info["group_name"]
                    for group_info in groups_to_process
                }

                for future in concurrent.futures.as_completed(future_to_group):
                    group_name_future = future_to_group[future]
                    try:
                        # Result is (group_name, final_state) from the worker
                        group_name_result, final_state = future.result()
                        result_state["group_results"][group_name_result] = final_state
                    except Exception as e:
                         # Error during future.result() (e.g., worker raised exception, pickling failed on return)
                         self._logger.error(f"Error retrieving result for group '{group_name_future}' from worker: {e}", exc_info=True)
                         # Create a failure state if result couldn't be obtained
                         failed_state : SingleGroupParserState = result_state["group_results"].get(group_name_future, {"group_name": group_name_future, "parsing_status": "failed"})
                         failed_state["parsing_status"] = "failed" # Ensure status is failed
                         result_state["group_results"][group_name_future] = failed_state

        result_state["status"] = "completed"
        self._logger.info("AllGroupsParserAgent run finished.")
        return result_state
