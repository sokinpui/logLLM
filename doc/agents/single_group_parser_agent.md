# Single Group Parser Agent (LangGraph) (`es_parser_agent.py`)

## File: `src/logllm/agents/es_parser_agent.py`

### Overview

This document describes the `SingleGroupParserAgent`, a LangGraph-based agent that orchestrates the parsing of a single log group within Elasticsearch.

### Class: `SingleGroupParseGraphState(TypedDict)`

- **Purpose**: Defines the comprehensive state managed by the LangGraph workflow within the `SingleGroupParserAgent`. It holds configuration parameters passed down from the orchestrator and tracks dynamic state across the different nodes of the graph.
- **Fields**:
  - _Configuration_:
    - `group_name` (str): The name of the log group being processed.
    - `source_index` (str): ES index containing raw logs for this group.
    - `target_index` (str): ES index for successfully parsed logs for this group.
    - `failed_index` (str): ES index for failed/fallback logs for this group.
    - `field_to_parse` (str): Field name containing the raw log line.
    - `fields_to_copy` (Optional[List[str]]): Additional fields to copy.
    - `sample_size_generation` (int): Number of samples for LLM pattern generation.
    - `sample_size_validation` (int): Number of samples for validating the generated pattern.
    - `validation_threshold` (float): Success rate (0.0-1.0) required on validation samples.
    - `batch_size` (int): Batch size for bulk indexing operations.
    - `max_regeneration_attempts` (int): Maximum _total_ attempts allowed for pattern generation/validation (includes initial attempt).
    - `keep_unparsed_index` (bool): If `True`, do not delete the `failed_index` before starting the run.
    - `provided_grok_pattern` (Optional[str]): A specific Grok pattern provided by the user via the CLI, bypassing LLM generation.
  - _Dynamic State_:
    - `current_attempt` (int): Tracks the current attempt number for pattern generation/validation (starts at 1).
    - `current_grok_pattern` (Optional[str]): The Grok pattern currently being used or just generated.
    - `last_failed_pattern` (Optional[str]): Stores the pattern from the previous attempt if it failed validation, used as context for retries.
    - `sample_lines_for_generation` (List[str]): Log lines sampled for LLM pattern generation context.
    - `sample_lines_for_validation` (List[str]): Log lines sampled for pattern validation.
    - `validation_passed` (bool): Flag indicating if the `current_grok_pattern` passed the validation step.
    - `final_parsing_status` (str): The overall outcome of the parsing process for this group (e.g., "success", "success_with_errors", "success_fallback", "failed", "failed_fallback"). Set by the final parsing/fallback nodes.
    - `final_parsing_results_summary` (Optional[Dict[str, int]]): A dictionary summarizing the results from the underlying `ScrollGrokParserAgent` run (containing counts like processed, successful, failed, parse_errors, index_errors).
    - `error_messages` (List[str]): A list accumulating error or warning messages encountered during the graph execution.

### Class: `SingleGroupParserAgent(Agent)`

- **Purpose**: An agent implementing the `Agent` interface using `langgraph`. It orchestrates the entire parsing process for a _single_ log group within Elasticsearch. This involves potentially generating a Grok pattern via LLM, validating the pattern against sample data, handling retries if validation fails, invoking the `ScrollGrokParserAgent` to perform the actual parsing and indexing (either with the validated pattern or a fallback), and storing the results of the run in a history index (`cfg.INDEX_GROK_RESULTS_HISTORY`).
- **Key Methods**:
  - **`__init__(self, model: LLMModel, db: ElasticsearchDatabase, prompts_manager: PromptsManager)`**
    - **Description**: Initializes the agent with its core dependencies: an `LLMModel` for pattern generation, an `ElasticsearchDatabase` for data access and sampling, and a `PromptsManager` for retrieving prompts. It also instantiates the `ScrollGrokParserAgent` sub-agent and calls `_build_graph` to compile its internal LangGraph workflow.
  - **`run(self, initial_config: Dict[str, Any]) -> SingleGroupParseGraphState`**
    - **Description**: The main entry point for executing the parsing workflow for a single group. It takes a dictionary containing the initial configuration (group name, field names, sizes, thresholds, etc.), converts it into the `SingleGroupParseGraphState` format required by the graph, and then invokes the compiled LangGraph using `self.graph.invoke()`.
    - **Parameters**: `initial_config` (dict): A dictionary containing all necessary configuration parameters for parsing this specific group.
    - **Returns**: (SingleGroupParseGraphState): The final state of the graph after execution, containing the outcome status, results summary, and any accumulated error messages.
  - **`_build_graph(self) -> CompiledGraph`**:
    - **Description**: Defines the structure of the agent's workflow using `langgraph.StateGraph`. It adds nodes corresponding to different logical steps (start, generate, validate, parse, fallback, retry prep, store results) and defines the edges (transitions) between them, including conditional edges based on the state.
    - **Returns**: (CompiledGraph): The compiled LangGraph ready for execution.
  - **Graph Nodes**:
    - **`_start_node`**: Initializes the run. Gets index names, clears the failed index (if `keep_unparsed_index` is False), fetches sample lines for generation (if no pattern provided) and validation from the source index using `db.get_sample_lines`. Sets initial state values.
    - **`_generate_grok_node`**: Called if no pattern was provided or if retrying. Uses the LLM (`self._model.generate`) with the appropriate prompt (fetched via `self._prompts_manager`) and the `GrokPatternSchema` to generate a Grok pattern based on `sample_lines_for_generation` and context from `last_failed_pattern` (if retrying). Updates `current_grok_pattern` in the state.
    - **`_validate_pattern_node`**: Attempts to compile the `current_grok_pattern` using `pygrok.Grok`. If successful, it tests the pattern against the `sample_lines_for_validation` and calculates the success rate. Updates `validation_passed` based on whether the rate meets the `validation_threshold`.
    - **`_parse_all_node`**: Called if validation passes. Configures and runs the `self._scroll_parser_agent` in normal parsing mode (not fallback). Updates `final_parsing_status` and `final_parsing_results_summary` based on the sub-agent's results.
    - **`_fallback_node`**: Called if pattern generation or validation fails after all retries. Configures and runs the `self._scroll_parser_agent` in fallback mode (`is_fallback_run=True`), writing all source documents to the `failed_index`. Updates `final_parsing_status` and `final_parsing_results_summary`.
    - **`_prepare_for_retry_node`**: Called if validation fails but retries remain. Increments the `current_attempt` counter, stores the `current_grok_pattern` into `last_failed_pattern`, and clears `current_grok_pattern` to trigger regeneration in the next loop.
    - **`_store_results_node`**: Called after either `_parse_all_node` or `_fallback_node` completes. It compiles a summary document containing the group name, status, pattern used, timestamp, and result counts, and inserts it into the `cfg.INDEX_GROK_RESULTS_HISTORY` index using `self._db.insert`.
  - **Conditional Edges**:
    - **`_decide_pattern_source`**: Called after `_start_node`. Checks if `provided_grok_pattern` exists in the state. If yes, routes to `validate_pattern`; otherwise, routes to `generate_grok`.
    - **`_decide_after_generate`**: Called after `_generate_grok_node`. Checks if a pattern was successfully generated. If yes, routes to `validate_pattern`. If no, checks if `current_attempt` < `max_regeneration_attempts`; if yes, routes to `prepare_for_retry`; otherwise, routes to `fallback`. Also checks for critical errors like missing validation samples and routes to `fallback`.
    - **`_decide_after_validation`**: Called after `_validate_pattern_node`. Checks if `validation_passed` is True. If yes, routes to `parse_all`. If no, checks if `current_attempt` < `max_regeneration_attempts`; if yes, routes to `prepare_for_retry`; otherwise, routes to `fallback`.
