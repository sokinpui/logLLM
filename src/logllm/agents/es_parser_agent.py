# src/logllm/agents/es_parser_agent.py (New File)
import os
import time
import pandas as pd
from typing import TypedDict, Dict, List, Optional, Tuple, Any, Callable
from pygrok import Grok
from pydantic import BaseModel, Field
import concurrent.futures

# Relative imports
try:
    from ..utils.llm_model import LLMModel, GeminiModel # Assuming Gemini or a base class
    from ..utils.logger import Logger
    from ..utils.prompts_manager import PromptsManager
    from ..utils.database import ElasticsearchDatabase
    from ..config import config as cfg
except ImportError as e:
     print(f"Error during agent imports: {e}")
     import sys
     sys.exit(1)

# --- LLM Schema ---
class GrokPatternSchema(BaseModel):
    """Pydantic schema for the LLM response containing the Grok pattern."""
    grok_pattern: str = Field(description="Output only the Grok pattern string.")

# --- Agent States ---
class ScrollGrokParserState(TypedDict):
    source_index: str
    target_index: str
    grok_pattern: str
    field_to_parse: str # e.g., "content"
    # Optional query to filter source documents (defaults to match_all if None)
    source_query: Optional[Dict[str, Any]]
    # Optional fields to copy from source to target besides parsed ones
    fields_to_copy: Optional[List[str]]
    # Results
    processed_count: int
    indexed_count: int
    error_count: int
    status: str # "pending", "running", "completed", "failed"

class SingleGroupParserState(TypedDict):
    group_name: str
    # Optional: If logs are tagged with a group ID during collection
    group_id_field: Optional[str]
    group_id_value: Optional[Any]
    # Index patterns determined from group_name using config functions
    source_index: str
    target_index: str
    # Configuration
    field_to_parse: str
    fields_to_copy: Optional[List[str]]
    # State/Results
    generated_grok_pattern: Optional[str]
    parsing_status: str # e.g., "pending", "pattern_generated", "parsing_running", "completed", "failed"
    parsing_result: Optional[ScrollGrokParserState] # Embed result from lower agent

class AllGroupsParserState(TypedDict):
    group_info_index: str
    # Configuration passed down
    field_to_parse: str
    fields_to_copy: Optional[List[str]]
    # Results per group
    group_results: Dict[str, SingleGroupParserState] # Map group name to its final state
    status: str # "pending", "running", "completed"


# src/logllm/agents/es_parser_agent.py (continued)

class ScrollGrokParserAgent:
    """
    Parses documents from a source Elasticsearch index using a provided Grok
    pattern and indexes the structured results into a target index.
    Uses scrolling and bulk indexing for efficiency. No AI involved.
    """
    BATCH_SIZE = 10000 # How many docs to process/index at once

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

    def _initialize_grok(self, pattern: str) -> bool:
        """Compile the Grok pattern."""
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
        field_to_parse: str,
        fields_to_copy: Optional[List[str]]
    ) -> Optional[Dict[str, Any]]:
        """Parses a single document hit and prepares it for indexing."""
        if self._grok_instance is None:
            self._logger.error("Grok instance not initialized, cannot parse hit.")
            return None

        source_doc = hit.get("_source", {})
        original_content = source_doc.get(field_to_parse)

        if not isinstance(original_content, str):
            self._logger.warning(f"Field '{field_to_parse}' not found or not a string in doc ID {hit.get('_id')}. Skipping parse.")
            self._total_parse_failures += 1
            return None # Cannot parse non-string content

        # Perform Grok matching
        parsed_fields = self._grok_instance.match(original_content)

        if parsed_fields:
            # Create the new document for the target index
            target_doc = parsed_fields.copy()

            # Add original timestamp if available and not parsed
            # (Commonly want to preserve original log time)
            if 'timestamp' not in target_doc and '@timestamp' in source_doc:
                 target_doc['@original_timestamp'] = source_doc['@timestamp']
            elif 'timestamp' in target_doc and '@timestamp' not in target_doc:
                 # If grok parsed a timestamp field, make it the primary one
                 target_doc['@timestamp'] = target_doc['timestamp']

            # Optionally copy other fields from the source
            if fields_to_copy:
                for field in fields_to_copy:
                    if field in source_doc and field not in target_doc:
                        target_doc[field] = source_doc[field]

            # Add original raw content for reference? Optional.
            # target_doc['original_message'] = original_content

            return target_doc
        else:
            self._logger.debug(f"Grok pattern did not match content in doc ID {hit.get('_id')}. Skipping.")
            # Optionally store skipped docs/content elsewhere? For now, just count.
            self._total_parse_failures += 1
            return None # Return None if parsing failed

    def _process_batch(self, hits: List[Dict[str, Any]], state: ScrollGrokParserState) -> bool:
        """Processes a batch of hits retrieved by the scroll."""
        self._logger.debug(f"Processing batch of {len(hits)} hits...")
        field_to_parse = state['field_to_parse']
        fields_to_copy = state.get('fields_to_copy')

        for hit in hits:
             parsed_doc = self._process_single_hit(hit, field_to_parse, fields_to_copy)
             if parsed_doc:
                  self._current_batch.append(parsed_doc)

        # Index the accumulated batch if it's large enough
        if len(self._current_batch) >= self.BATCH_SIZE:
            self._flush_batch(state['target_index'])

        return True # Continue scrolling

    def _flush_batch(self, target_index: str):
        """Indexes the current batch of parsed documents."""
        if not self._current_batch:
            return

        self._logger.info(f"Indexing batch of {len(self._current_batch)} parsed documents to '{target_index}'...")
        success_count, errors = self._db.bulk_index(self._current_batch, target_index)

        self._total_indexed_successfully += success_count
        self._total_index_failures += len(errors)
        if errors:
             # Store or handle errors as needed
             self._errors_in_batch.extend(errors)
             self._logger.warning(f"{len(errors)} errors occurred during bulk indexing this batch.")

        # Clear the batch regardless of errors (failed docs are reported in 'errors')
        self._current_batch = []


    def run(self, initial_state: ScrollGrokParserState) -> ScrollGrokParserState:
        """Executes the scroll, parse, and bulk index workflow."""
        self._logger.info(f"Starting ScrollGrokParserAgent run. Source: '{initial_state['source_index']}', Target: '{initial_state['target_index']}'")
        result_state = initial_state.copy()
        result_state["status"] = "running"
        result_state["processed_count"] = 0
        result_state["indexed_count"] = 0
        result_state["error_count"] = 0

        # Reset internal counters for this run
        self._current_batch = []
        self._errors_in_batch = []
        self._total_processed = 0
        self._total_indexed_successfully = 0
        self._total_parse_failures = 0
        self._total_index_failures = 0

        # 1. Initialize Grok
        if not self._initialize_grok(initial_state['grok_pattern']):
            result_state["status"] = "failed"
            result_state["error_count"] = 1 # Indicate pattern compilation error
            self._logger.error("Run failed due to invalid Grok pattern.")
            return result_state

        # 2. Define query and source fields
        source_query = initial_state.get("source_query") or {"match_all": {}}
        # Fields needed: the field to parse + any fields to copy
        fields_needed = set([initial_state['field_to_parse']])
        if initial_state.get('fields_to_copy'):
            fields_needed.update(initial_state['fields_to_copy'])
        # Always good to fetch original timestamp if available
        if '@timestamp' not in fields_needed:
            fields_needed.add('@timestamp')

        source_fields_list = list(fields_needed)

        # 3. Scroll and Process
        try:
            # Define the processing function closure to capture state
            def batch_processor(hits: List[Dict[str, Any]]) -> bool:
                return self._process_batch(hits, result_state)

            processed_count, _ = self._db.scroll_and_process_batches(
                index=initial_state['source_index'],
                query=source_query,
                batch_size=self.BATCH_SIZE,
                process_batch_func=batch_processor,
                source_fields=source_fields_list
            )
            self._total_processed = processed_count # Total hits received from scroll

            # 4. Flush any remaining documents in the last batch
            self._flush_batch(initial_state['target_index'])

            result_state["status"] = "completed"
            self._logger.info("ScrollGrokParserAgent run completed.")

        except Exception as e:
            result_state["status"] = "failed"
            self._logger.error(f"Run failed during scroll/processing: {e}", exc_info=True)
            # Flush any partial batch that might exist before the error
            try:
                self._flush_batch(initial_state['target_index'])
            except Exception as flush_err:
                self._logger.error(f"Error flushing final batch after main error: {flush_err}")


        # 5. Populate final results
        result_state["processed_count"] = self._total_processed # Docs received
        result_state["indexed_count"] = self._total_indexed_successfully # Docs indexed ok
        # Total errors = parse failures + index failures
        result_state["error_count"] = self._total_parse_failures + self._total_index_failures
        # Optionally store detailed errors somewhere if needed: result_state["index_errors"] = self._errors_in_batch

        self._logger.info(f"Run Summary: Processed={self._total_processed}, Indexed OK={self._total_indexed_successfully}, Parse Failures={self._total_parse_failures}, Index Failures={self._total_index_failures}")

        return result_state

# src/logllm/agents/es_parser_agent.py (continued)

class SingleGroupParserAgent:
    """
    Manages parsing for a single group of logs stored in Elasticsearch.
    - Determines source/target indices.
    - Gets sample logs.
    - Uses LLM to generate a Grok pattern.
    - Invokes ScrollGrokParserAgent to perform the actual parsing and indexing.
    """
    SAMPLE_SIZE = 20 # How many log lines to fetch for pattern generation

    def __init__(self, model: LLMModel, db: ElasticsearchDatabase, prompts_manager: PromptsManager):
        self._model = model
        self._db = db
        self._prompts_manager = prompts_manager
        self._logger = Logger()
        self._scroll_parser_agent = ScrollGrokParserAgent(db) # Instantiate the lower-level agent

    def _get_sample_lines(self, source_index: str, field_to_parse: str) -> List[str]:
        """Fetches sample log lines from the source index."""
        self._logger.info(f"Fetching sample lines for field '{field_to_parse}' from index '{source_index}'...")
        # Using the refined DB method
        samples = self._db.get_sample_lines(
            index=source_index,
            field=field_to_parse,
            sample_size=self.SAMPLE_SIZE
            # query=query # Add query here if needed, e.g., match group_id if available
        )
        if not samples:
             self._logger.warning(f"Could not retrieve samples from index '{source_index}'. Pattern generation might fail.")
        return samples

    def _generate_grok_pattern(self, sample_logs: List[str]) -> Optional[str]:
        """Generate Grok pattern using LLM based on log samples."""
        if not sample_logs:
            self._logger.warning("No sample logs provided, cannot generate Grok pattern.")
            return None

        try:
            # Ensure the prompt key exists and prompt is correctly formatted
            prompt_key = "logllm.agents.parser_agent.SimpleGrokLogParserAgent._generate_grok_pattern" # Reusing same prompt logic
            prompt = self._prompts_manager.get_prompt(metadata=prompt_key, sample_logs=str(sample_logs))

            self._logger.info("Requesting Grok pattern from LLM...")
            response = self._model.generate(prompt, schema=GrokPatternSchema)

            if response and isinstance(response, GrokPatternSchema) and response.grok_pattern:
                pattern = response.grok_pattern.strip()
                if "%{" in pattern and "}" in pattern:
                    self._logger.info(f"LLM generated Grok pattern: {pattern}")
                    return pattern
                else:
                    self._logger.warning(f"LLM response doesn't look like a valid Grok pattern: {pattern}")
                    return None
            else:
                self._logger.warning(f"LLM did not return a valid GrokPatternSchema object. Response: {response}")
                return None

        except KeyError:
             self._logger.error(f"Prompt key '{prompt_key}' not found in {self._prompts_manager.json_file}. Cannot generate Grok pattern.")
             return None
        except ValueError as ve:
             self._logger.error(f"Error getting or formatting prompt for Grok generation: {ve}", exc_info=True)
             return None
        except Exception as e:
            self._logger.error(f"LLM call failed during Grok pattern generation: {e}", exc_info=True)
            return None

    def run(self, initial_state: SingleGroupParserState) -> SingleGroupParserState:
        """Executes the parsing workflow for a single group."""
        group_name = initial_state['group_name']
        self._logger.info(f"Starting SingleGroupParserAgent run for group: '{group_name}'")
        result_state = initial_state.copy()
        result_state["parsing_status"] = "running"
        result_state["generated_grok_pattern"] = None
        result_state["parsing_result"] = None

        # 1. Determine Indices (using config functions)
        try:
             source_index = cfg.get_log_storage_index(group_name)
             target_index = cfg.get_parsed_log_storage_index(group_name)
             result_state["source_index"] = source_index
             result_state["target_index"] = target_index
             self._logger.info(f"Determined indices for group '{group_name}': Source='{source_index}', Target='{target_index}'")
        except Exception as e:
             self._logger.error(f"Failed to determine indices for group '{group_name}': {e}", exc_info=True)
             result_state["parsing_status"] = "failed"
             return result_state

        # 2. Get Sample Logs
        field_to_parse = initial_state['field_to_parse']
        sample_lines = self._get_sample_lines(source_index, field_to_parse)
        if not sample_lines:
            # Decide if we should fail or attempt parsing without a pattern (will fail later)
             self._logger.warning(f"No sample lines found for group '{group_name}'. Cannot generate pattern.")
             result_state["parsing_status"] = "failed" # Fail if no samples
             return result_state

        # 3. Generate Grok Pattern
        grok_pattern = self._generate_grok_pattern(sample_lines)
        if not grok_pattern:
            self._logger.error(f"Failed to generate Grok pattern for group '{group_name}'.")
            result_state["parsing_status"] = "failed"
            return result_state
        result_state["generated_grok_pattern"] = grok_pattern
        result_state["parsing_status"] = "pattern_generated"

        # 4. Prepare and Run ScrollGrokParserAgent
        # Define query for the source index (e.g., match all for the group index)
        # If group_id was available, you could filter here:
        # source_query = {"term": {initial_state.get("group_id_field", "group_id"): initial_state["group_id_value"]}}
        source_query = {"query": {"match_all": {}}} # Wrap match_all inside "query" key

        scroll_parser_state: ScrollGrokParserState = {
            "source_index": source_index,
            "target_index": target_index,
            "grok_pattern": grok_pattern,
            "field_to_parse": field_to_parse,
            "source_query": source_query,
            "fields_to_copy": initial_state.get("fields_to_copy"),
            "processed_count": 0,
            "indexed_count": 0,
            "error_count": 0,
            "status": "pending"
        }

        try:
             self._logger.info(f"Invoking ScrollGrokParserAgent for group '{group_name}'...")
             result_state["parsing_status"] = "parsing_running"
             parsing_result = self._scroll_parser_agent.run(scroll_parser_state)
             result_state["parsing_result"] = parsing_result

             # Update overall status based on parser result
             if parsing_result["status"] == "completed":
                  result_state["parsing_status"] = "completed"
                  self._logger.info(f"Successfully completed parsing for group '{group_name}'.")
             else:
                  result_state["parsing_status"] = "failed"
                  self._logger.error(f"Parsing failed for group '{group_name}'. See scroll parser results.")

        except Exception as e:
             self._logger.error(f"Error invoking ScrollGrokParserAgent for group '{group_name}': {e}", exc_info=True)
             result_state["parsing_status"] = "failed"
             # Store partial result if available
             if 'parsing_result' not in result_state or result_state["parsing_result"] is None:
                  scroll_parser_state["status"] = "failed" # Mark the attempt as failed
                  result_state["parsing_result"] = scroll_parser_state


        return result_state

# src/logllm/agents/es_parser_agent.py (continued)

class AllGroupsParserAgent:
    """
    Orchestrates the parsing of all log groups defined in the Elasticsearch
    group information index by invoking SingleGroupParserAgent for each group.
    """
    def __init__(self, model: LLMModel, db: ElasticsearchDatabase, prompts_manager: PromptsManager):
        self._model = model
        self._db = db
        self._prompts_manager = prompts_manager
        self._logger = Logger()
        # Instantiate the agent that handles a single group
        self._single_group_agent = SingleGroupParserAgent(model, db, prompts_manager)

    def _get_all_groups(self, group_info_index: str) -> List[Dict[str, Any]]:
        """Fetches group definitions from the specified index."""
        self._logger.info(f"Fetching all group definitions from index '{group_info_index}'...")
        try:
            query = {"query": {"match_all": {}}}
            # Use scroll_search as group info index is likely small, but robust
            groups_data = self._db.scroll_search(query=query, index=group_info_index)

            if not groups_data:
                 self._logger.warning(f"No group info found in index '{group_info_index}'. Cannot parse any groups.")
                 return []

            # Extract relevant info (e.g., group name)
            valid_groups = []
            for hit in groups_data:
                 source = hit.get("_source", {})
                 group_name = source.get("group")
                 # Add other relevant fields if needed (like group_id)
                 if group_name:
                      valid_groups.append({"group_name": group_name}) # Extend dict as needed
                 else:
                      self._logger.warning(f"Skipping group document without 'group' field: ID {hit.get('_id')}")

            self._logger.info(f"Fetched {len(valid_groups)} valid group definitions.")
            return valid_groups
        except Exception as e:
            self._logger.error(f"Failed to fetch groups from index '{group_info_index}': {e}", exc_info=True)
            return []

    def run(self, initial_state: AllGroupsParserState, num_threads: int = 1) -> AllGroupsParserState:
        """
        Executes the parsing workflow for all defined groups, potentially in parallel.
        """
        self._logger.info(f"Starting AllGroupsParserAgent run. Group Index: '{initial_state['group_info_index']}'. Threads: {num_threads}")
        result_state = initial_state.copy()
        result_state["status"] = "running"
        result_state["group_results"] = {}

        # 1. Fetch Groups
        groups_to_process = self._get_all_groups(initial_state['group_info_index'])
        if not groups_to_process:
             result_state["status"] = "completed" # Completed, but nothing done
             self._logger.warning("No groups found to process.")
             return result_state

        # 2. Prepare common configuration
        field_to_parse = initial_state['field_to_parse']
        fields_to_copy = initial_state.get('fields_to_copy')

        # 3. Execute parsing (Sequential or Parallel)
        effective_num_threads = max(1, num_threads) # Ensure at least 1

        if effective_num_threads <= 1:
            self._logger.info("Running group parsing sequentially.")
            for group_info in groups_to_process:
                group_name = group_info["group_name"]
                self._logger.info(f"--- Processing Group: {group_name} ---")
                single_group_state: SingleGroupParserState = {
                    "group_name": group_name,
                    "field_to_parse": field_to_parse,
                    "fields_to_copy": fields_to_copy,
                    # Set defaults or get from group_info if available
                    "group_id_field": None,
                    "group_id_value": None,
                    "source_index": "", # Will be set by agent
                    "target_index": "", # Will be set by agent
                    "generated_grok_pattern": None,
                    "parsing_status": "pending",
                    "parsing_result": None
                }
                try:
                    final_group_state = self._single_group_agent.run(single_group_state)
                    result_state["group_results"][group_name] = final_group_state
                except Exception as e:
                    self._logger.error(f"Unhandled error processing group '{group_name}' sequentially: {e}", exc_info=True)
                    # Record failure state
                    single_group_state["parsing_status"] = "failed"
                    result_state["group_results"][group_name] = single_group_state

        else:
            self._logger.info(f"Running group parsing in parallel with {effective_num_threads} workers.")
            # --- Parallel Execution ---
            # Define a worker function for parallel processing
            def group_worker(group_info: Dict[str, Any]) -> Tuple[str, SingleGroupParserState]:
                group_name = group_info["group_name"]
                worker_logger = Logger() # Potentially use shared logger or context logger
                worker_logger.info(f"[Worker] Processing Group: {group_name}")

                 # Re-initialize dependencies per worker if necessary (DB connection might be okay if thread-safe, LLM/Prompts usually fine)
                 # db_worker = ElasticsearchDatabase() # Or pass the main instance if safe
                 # sg_agent_worker = SingleGroupParserAgent(self._model, self._db, self._prompts_manager) # Pass dependencies

                single_group_state: SingleGroupParserState = {
                    "group_name": group_name,
                    "field_to_parse": field_to_parse,
                    "fields_to_copy": fields_to_copy,
                    "group_id_field": None, "group_id_value": None, # Add if needed
                    "source_index": "", "target_index": "",
                    "generated_grok_pattern": None, "parsing_status": "pending", "parsing_result": None
                }
                try:
                     # Use the instance created in the main process or re-init here
                     final_state = self._single_group_agent.run(single_group_state)
                     worker_logger.info(f"[Worker] Finished Group: {group_name}, Status: {final_state['parsing_status']}")
                     return group_name, final_state
                except Exception as e:
                    worker_logger.error(f"[Worker] Error processing group '{group_name}': {e}", exc_info=True)
                    single_group_state["parsing_status"] = "failed"
                    return group_name, single_group_state


            with concurrent.futures.ProcessPoolExecutor(max_workers=effective_num_threads) as executor:
                future_to_group = {
                    executor.submit(group_worker, group_info): group_info["group_name"]
                    for group_info in groups_to_process
                }

                for future in concurrent.futures.as_completed(future_to_group):
                    group_name_future = future_to_group[future]
                    try:
                        group_name_result, final_state = future.result()
                        result_state["group_results"][group_name_result] = final_state
                    except Exception as e:
                         # Log error from the future itself
                         self._logger.error(f"Error retrieving result for group '{group_name_future}' from worker: {e}", exc_info=True)
                         # Create a failure state if result couldn't be obtained
                         failed_state : SingleGroupParserState = result_state["group_results"].get(group_name_future, {"group_name": group_name_future, "parsing_status": "failed"})
                         failed_state["parsing_status"] = "failed" # Ensure status is failed
                         result_state["group_results"][group_name_future] = failed_state


        result_state["status"] = "completed"
        self._logger.info("AllGroupsParserAgent run finished.")
        # TODO: Add summary logging of overall success/failures per group
        return result_state
