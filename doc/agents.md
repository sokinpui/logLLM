# Detailed Documentation for Agent-Related Files

## File: `chunk_manager.py`

### Class: `ESTextChunkManager`
- **Purpose**: Manages the retrieval and chunking of text data from Elasticsearch for analysis, ensuring chunks fit within a specified token limit.
- **Key Methods**:
  - **`__init__(self, id: Any, field: str, index: str, db: ElasticsearchDatabase)`**
    - **Description**: Initializes the chunk manager with an ID, field, index, and database instance, fetching all relevant hits upfront.
    - **Parameters**:
      - `id` (Any): Identifier for the documents to retrieve.
      - `field` (str): Field name containing the text (e.g., "content").
      - `index` (str): Elasticsearch index to query.
      - `db` (ElasticsearchDatabase): Database instance.
    - **Usage**: `chunk_manager = ESTextChunkManager(6, "content", "pre_process_1", db)`
  - **`_build_chunk(self, initial_size: int, start: int, hits: list, max_len: int, len_fn: Callable[[str], int]) -> str`**
    - **Description**: Constructs a chunk of text from hits, dynamically adjusting size to stay under `max_len`.
    - **Parameters**:
      - `initial_size` (int): Starting number of hits per chunk (e.g., 1024).
      - `start` (int): Starting index in the hits list.
      - `hits` (list): List of Elasticsearch hits.
      - `max_len` (int): Maximum token length for the chunk.
      - `len_fn` (Callable[[str], int]): Function to count tokens.
    - **Returns**: String chunk of text.
    - **Usage**: Internal method called by `get_next_chunk` to build chunks iteratively.
  - **`_get_all_hits(self) -> list`**
    - **Description**: Retrieves all hits matching the `id` from the specified index using the Scroll API.
    - **Returns**: List of Elasticsearch hits.
    - **Usage**: Called during initialization to cache all relevant data.
  - **`is_end(self) -> bool`**
    - **Description**: Checks if all hits have been processed.
    - **Returns**: `True` if `start` exceeds `total_hits`, `False` otherwise.
    - **Usage**: `if chunk_manager.is_end(): print("Done")`
  - **`get_next_chunk(self, max_len: int, len_fn: Callable[[str], int]) -> str`**
    - **Description**: Retrieves the next chunk of text, updating the internal state (`start`, `hits_in_current_chunk`).
    - **Parameters**:
      - `max_len` (int): Maximum token limit for the chunk.
      - `len_fn` (Callable[[str], int]): Token counting function.
    - **Returns**: String chunk or empty string if at end.
    - **Usage**: `chunk = chunk_manager.get_next_chunk(80000, model.token_count)`
  - **`get_current_chunk(self) -> str | None`**
    - **Description**: Returns the current chunk of text.
    - **Returns**: Current chunk or `None` if not set.
    - **Usage**: Access the last retrieved chunk without advancing.

- **Utility Function**: **`test_chunk_manager(chunk_manager: ESTextChunkManager, max_tokens: int, token_count: Callable[[str], int], model)`**
  - **Purpose**: Tests the chunk manager by iterating through all chunks and printing state information.
  - **Parameters**:
    - `chunk_manager`: Instance to test.
    - `max_tokens` (int): Token limit per chunk.
    - `token_count` (Callable): Token counting function.
    - `model`: Model instance (for token counting).
  - **Usage**: `test_chunk_manager(chunk_manager, 80000, model.token_count, model)`

---

## File: `agent_abc.py`

### Class: `Agent(ABC)`
- **Purpose**: Abstract base class defining the interface for all agents in the system, using a graph-based workflow.
- **Key Methods**:
  - **`_build_graph(self, typed_state) -> CompiledStateGraph`**
    - **Description**: Abstract method to construct the agent’s workflow graph.
    - **Parameters**:
      - `typed_state`: Type definition for the agent’s state.
    - **Returns**: Compiled `StateGraph`.
    - **Usage**: Implemented by subclasses to define their logic flow.
  - **`run(self)`**
    - **Description**: Abstract method to execute the agent synchronously.
    - **Usage**: Subclasses implement to process input state and return output.
  - **`arun(self)`**
    - **Description**: Abstract method to execute the agent asynchronously.
    - **Usage**: Subclasses implement for async execution.

- **Utility Function**: **`add_string_message(left: list[str], right: str | list[str]) -> list[str]`**
  - **Purpose**: Helper function to append messages to a list, supporting both string and list inputs.
  - **Parameters**:
    - `left` (list[str]): Existing message list.
    - `right` (str | list[str]): Message(s) to append.
  - **Returns**: Updated list of messages.
  - **Usage**: Used in `Annotated` state fields for state updates (e.g., `message`, `memories`).

---

## File: `linear_analyze_agent.py`

### Class: `LinearAnalyzeAgentState(TypedDict)`
- **Purpose**: Defines the state structure for the `LinearAnalyzeAgent`.
- **Fields**:
  - `working_event` (Event): Current event being analyzed.
  - `message` (Annotated[list[str], add_string_message]): List of messages (e.g., analysis results).
  - `memories` (Annotated[list[str], add_string_message]): Summarized memories from previous chunks.
  - `working_file_ids` (list[str]): List of file IDs to process.
  - `chunk` (str): Current chunk of text being analyzed.

### Class: `LinearAnalyzeAgent(Agent)`
- **Purpose**: Analyzes log chunks linearly for a given event, maintaining a memory of summaries within a token limit.
- **Key Methods**:
  - **`__init__(self, model: LLMModel, db: ElasticsearchDatabase, typed_state)`**
    - **Description**: Initializes the agent with a model, database, and state type, building the workflow graph.
    - **Parameters**:
      - `model` (LLMModel): Language model for generation.
      - `db` (ElasticsearchDatabase): Database instance.
      - `typed_state`: State type (e.g., `LinearAnalyzeAgentState`).
    - **Usage**: `agent = LinearAnalyzeAgent(model, db, LinearAnalyzeAgentState)`
  - **`run(self, state: LinearAnalyzeAgentState) -> LinearAnalyzeAgentState`**
    - **Description**: Executes the agent synchronously.
    - **Parameters**:
      - `state`: Initial state.
    - **Returns**: Updated state after execution.
    - **Usage**: `result = agent.run(state)`
  - **`arun(self, state: LinearAnalyzeAgentState) -> LinearAnalyzeAgentState`**
    - **Description**: Executes the agent asynchronously.
    - **Usage**: `result = await agent.arun(state)`
  - **`_build_graph(self, typed_state) -> CompiledStateGraph`**
    - **Description**: Constructs a workflow graph with nodes for setup, chunk retrieval, analysis, memory management, and file ID handling.
    - **Nodes**:
      - `setup`: Initializes file IDs and chunk manager.
      - `get_chunk`: Retrieves the next chunk.
      - `chunk_analysis`: Analyzes the current chunk.
      - `memorize`: Updates memory with analysis results.
      - `pop_file_id`: Moves to the next file ID.
    - **Edges**: Defines a linear flow with conditional transitions based on file and chunk completion.
    - **Usage**: Internal setup for agent execution.
  - **`is_done(self, state: LinearAnalyzeAgentState)`**
    - **Description**: Checks if all file IDs have been processed.
    - **Returns**: `True` if `working_file_ids` is empty, `False` otherwise.
    - **Usage**: Determines if the agent should terminate.
  - **`is_working_file_done(self, state: LinearAnalyzeAgentState)`**
    - **Description**: Checks if the current file’s chunks are fully processed.
    - **Returns**: `True` if `chunk_manager.is_end()`, `False` otherwise.
    - **Usage**: Controls loop back to `get_chunk` or advance to `pop_file_id`.
  - **`get_chunk(self, state: LinearAnalyzeAgentState)`**
    - **Description**: Retrieves the next chunk using the chunk manager.
    - **Returns**: Updated state with the new `chunk`.
    - **Usage**: `state["chunk"] = chunk_manager.get_next_chunk(...)`
  - **`chunk_analysis(self, state: LinearAnalyzeAgentState)`**
    - **Description**: Analyzes the current chunk using the model and event context.
    - **Returns**: Updated state with analysis result in `message`.
    - **Usage**: Generates insights from log data based on the event description.
  - **`memorize(self, state: LinearAnalyzeAgentState)`**
    - **Description**: Summarizes analysis results and manages memory size, condensing if exceeding `MEMORY_TOKENS_LIMIT`.
    - **Returns**: Updated state with new memory entry.
    - **Usage**: Ensures memory stays within token limits (e.g., 20,000 tokens).
  - **`pop_file_id(self, state: LinearAnalyzeAgentState)`**
    - **Description**: Removes the processed file ID from the list.
    - **Returns**: Updated state with reduced `working_file_ids`.
    - **Usage**: Advances to the next file.
  - **`setup_working_file(self, state: LinearAnalyzeAgentState)`**
    - **Description**: Initializes the chunk manager with the first file ID and sets up `working_file_ids`.
    - **Returns**: Updated state with file IDs.
    - **Usage**: Prepares the agent for chunk-by-chunk analysis.

---

## File: `reasoning_agent.py`

### Class: `State(TypedDict)`
- **Purpose**: Defines the state structure for the `ReasoningAgent`.
- **Fields**:
  - `messages` (Annotated[List[str], add_string_message]): Accumulated responses.
  - `original_prompt` (str): User’s initial input.
  - `question` (str): Converted or parsed question.
  - `context` (str): Contextual analysis of the question.
  - `goal` (str): Determined goal of the question.
  - `sub_questions` (List[str]): Decomposed sub-questions.
  - `processed_sub_questions` (Annotated[List[str], add_string_message]): Processed sub-questions.
  - `final_response` (str): Final synthesized answer.

### Class: `ReasoningAgent(Agent)`
- **Purpose**: Breaks down complex questions into sub-questions, solves them, and synthesizes a final response.
- **Key Methods**:
  - **`__init__(self, model: LLMModel, typed_state)`**
    - **Description**: Initializes the agent with a model and state type, building the workflow graph.
    - **Parameters**:
      - `model` (LLMModel): Language model.
      - `typed_state`: State type (e.g., `State`).
    - **Usage**: `agent = ReasoningAgent(model, State)`
  - **`run(self, state: State) -> State`** and **`arun(self, state: State) -> State`**
    - **Description**: Synchronous and asynchronous execution methods.
    - **Usage**: `result = agent.run(state)` or `result = await agent.arun(state)`
  - **`_build_graph(self, typed_state) -> CompiledStateGraph`**
    - **Description**: Constructs a workflow with nodes for parsing, context analysis, goal determination, decomposition, sub-question solving, combining answers, and formulating the final response.
    - **Nodes**:
      - `parse_input`: Converts input to a question.
      - `context_understanding`: Analyzes context.
      - `determine_goal`: Identifies the goal.
      - `decompose_question`: Breaks into sub-questions.
      - `solve_sub_question`: Answers each sub-question.
      - `combine_sub_answer`: Synthesizes sub-answers.
      - `formulate_response`: Formats the final response.
    - **Edges**: Conditional flow based on question detection and sub-question completion.
  - **`is_question(self, state: State) -> bool`**
    - **Description**: Determines if the input is or can be converted to a question.
    - **Returns**: `True` if question-like, `False` otherwise.
    - **Usage**: Controls whether to proceed with processing.
  - **`parse_input(self, state: State) -> State | dict`**
    - **Description**: Converts the original prompt into a clear question.
    - **Returns**: Updated state with `question`.
    - **Usage**: `state["question"] = "What is X?"`
  - **`context_understanding(self, state: State) -> State | dict`**
    - **Description**: Extracts context, domain, and ambiguities from the question.
    - **Returns**: Updated state with `context`.
    - **Usage**: Provides background for decomposition.
  - **`determine_goal(self, state: State) -> State | dict`**
    - **Description**: Identifies the question’s goal and response type.
    - **Returns**: Updated state with `goal`.
    - **Usage**: Guides the decomposition strategy.
  - **`decompose_question(self, state: State) -> State | dict`**
    - **Description**: Breaks the question into sub-questions.
    - **Returns**: Updated state with `sub_questions`.
    - **Usage**: `state["sub_questions"] = ["What is A?", "How does A work?"]`
  - **`solve_sub_question(self, state: State) -> State | dict`**
    - **Description**: Answers the first sub-question in the list.
    - **Returns**: Updated state with answer in `messages`.
    - **Usage**: Processes sub-questions iteratively.
  - **`is_sub_question_empty(self, state: State) -> bool`**
    - **Description**: Checks if all sub-questions are processed, moving the current one to `processed_sub_questions`.
    - **Returns**: `True` if `sub_questions` is empty, `False` otherwise.
    - **Usage**: Controls transition to `combine_sub_answer`.
  - **`combine_sub_answer(self, state: State) -> State | dict`**
    - **Description**: Synthesizes sub-answers into a coherent response.
    - **Returns**: Updated state with combined answer in `messages`.
    - **Usage**: Builds a unified narrative.
  - **`formulate_response(self, state: State) -> State | dict`**
    - **Description**: Formats the final response with structure and tone.
    - **Returns**: Updated state with `final_response`.
    - **Usage**: `state["final_response"] = "Here’s the answer..."`

---

## File: `pre_process_agent.py`

### Class: `PreProcessAgentState(TypedDict)`
- **Purpose**: Defines the state structure for the `PreProcessAgent`.
- **Fields**:
  - `working_event` (Event): Event to preprocess logs for.
  - `message` (Annotated[list[str], add_string_message]): Messages (e.g., required info, feedback).
  - `files` (List[LogFile]): List of log files.
  - `apps` (List[str]): Relevant applications.
  - `query` (dict): Elasticsearch query.
  - `hits` (int): Number of matching log entries.
  - `route_back` (bool): Flag to refine the search.

### Class: `PreProcessAgent(Agent)`
- **Purpose**: Preprocesses logs by generating and refining Elasticsearch queries based on an event, storing filtered results.
- **Key Methods**:
  - **`__init__(self, model: LLMModel, rag: RAGManager, db: ElasticsearchDatabase, typed_state)`**
    - **Description**: Initializes the agent with a model, RAG manager, database, and state type.
    - **Parameters**:
      - `model` (LLMModel): Language model.
      - `rag` (RAGManager): RAG instance for context retrieval.
      - `db` (ElasticsearchDatabase): Database instance.
      - `typed_state`: State type (e.g., `PreProcessAgentState`).
    - **Usage**: `agent = PreProcessAgent(model, rag, db, PreProcessAgentState)`
  - **`run(self, state: PreProcessAgentState) -> PreProcessAgentState`** and **`arun(self, state: PreProcessAgentState) -> PreProcessAgentState`**
    - **Description**: Synchronous and asynchronous execution methods.
    - **Usage**: `result = agent.run(state)`
  - **`_build_graph(self, typed_state) -> CompiledStateGraph`**
    - **Description**: Constructs a workflow with nodes for event interpretation, query generation, database search, and feedback.
    - **Nodes**:
      - `interpre_event`: Extracts required info and apps.
      - `gen_search_query`: Generates an Elasticsearch query.
      - `db_search`: Executes the query and stores results.
      - `search_feedback`: Evaluates results and decides if refinement is needed.
    - **Edges**: Loops back to `gen_search_query` if refinement is needed.
  - **`_list_to_indices(self, apps: List[str]) -> str`**
    - **Description**: Converts a list of app names to a comma-separated list of indices (e.g., "log_app1,log_app2").
    - **Parameters**:
      - `apps` (List[str]): Application names.
    - **Returns**: String of indices.
    - **Usage**: `indices = agent._list_to_indices(["app1", "app2"])`
  - **`interpre_event(self, state: PreProcessAgentState) -> PreProcessAgentState | dict | None`**
    - **Description**: Interprets the event to identify required information and relevant apps using RAG.
    - **Returns**: Updated state with `message` (required info) and `apps`.
    - **Usage**: Initial step to understand the event’s context.
  - **`gen_search_query(self, state: PreProcessAgentState) -> PreProcessAgentState | dict | None`**
    - **Description**: Generates a JSON-formatted Elasticsearch query based on event, required info, and random log samples.
    - **Returns**: Updated state with `query` or `None` on JSON error.
    - **Usage**: `state["query"] = {"query": {"match": {"content": "error"}}}`.
  - **`search_in_db(self, state: PreProcessAgentState) -> PreProcessAgentState | dict | None`**
    - **Description**: Executes the query, storing results in an alias index (e.g., `pre_process_1`).
    - **Returns**: Updated state with `hits` (count of matches).
    - **Usage**: Filters logs relevant to the event.
  - **`search_feedback(self, state: PreProcessAgentState) -> PreProcessAgentState | dict | None`**
    - **Description**: Evaluates search results and decides if refinement is needed.
    - **Returns**: Updated state with feedback in `message` and `route_back` flag.
    - **Usage**: `state["route_back"] = True` if results are insufficient.


---

## Usage Notes
- **Dependencies**: Requires `langgraph`, `pydantic`, and other libraries from the system (e.g., `llm_model.py`, `database.py`).
- **Configuration**: Relies on `config.py` for settings like `MEMORY_TOKENS_LIMIT` and index names.
- **Scalability**: `ESTextChunkManager` and `LinearAnalyzeAgent` handle large datasets by processing chunks iteratively.
- **Error Handling**: Agents log errors (e.g., JSON decoding failures) and may return partial states; ensure robust error checking in production.
- **Integration**: `graph.py` shows how agents can be chained; extend this for additional agents or custom workflows.

This documentation provides a comprehensive guide to the agent-related components. Let me know if you need further details or examples!
