# Agent Abstract Base Class (`agent_abc.py`)

## File: `src/logllm/agents/agent_abc.py`

### Overview

This file defines the abstract base class `Agent` that serves as an interface for other agent implementations, particularly those using graph-based workflows like LangGraph. It also includes a utility function for state management within LangGraph.

### Class: `Agent(ABC)`

- **Purpose**: Abstract base class defining the common interface for all agents in the system. It enforces the implementation of methods for building a workflow graph (if applicable) and for synchronous/asynchronous execution.
- **Key Attributes**:
  - `graph` (CompiledStateGraph): Expected attribute for agents implementing a LangGraph workflow, holding the compiled graph object.
- **Key Methods**:

  - **`_build_graph(self, typed_state) -> CompiledStateGraph`**
    - **Type**: Abstract Method.
    - **Description**: Intended for subclasses that utilize `langgraph.StateGraph`. This method should be implemented to construct the agent's specific workflow graph, defining nodes and edges based on the provided state type.
    - **Parameters**:
      - `typed_state`: The type definition (typically a `TypedDict`) representing the structure of the agent's state that the graph will operate on.
    - **Returns**: A compiled `langgraph` graph (`CompiledGraph` or similar).
    - **Usage**: Subclasses like `SingleGroupParserAgent` implement this to define their multi-step logic flow.
  - **`run(self)`**
    - **Type**: Abstract Method.
    - **Description**: Defines the primary synchronous execution logic for an agent. Subclasses _must_ implement this method to be runnable.
    - **Parameters**: Varies by implementation (e.g., might take initial state or input data).
    - **Returns**: Varies by implementation (e.g., final state, results dictionary).
    - **Usage**: Called to start the agent's task, e.g., `result = agent.run(input_data)`.
  - **`arun(self)`**
    - **Type**: Abstract Method.
    - **Description**: Defines the primary asynchronous execution logic for an agent. Subclasses _must_ implement this method if asynchronous execution is required.
    - **Parameters**: Varies by implementation.
    - **Returns**: Varies by implementation (awaitable).
    - **Usage**: Called to start the agent's task asynchronously, e.g., `result = await agent.arun(input_data)`.

- **Utility Function**: **`add_string_message(left: list[str], right: str | list[str]) -> list[str]`**
  - **Purpose**: A helper function designed for use with `langgraph` state updates, specifically for fields annotated to accumulate messages. It appends a new string or a list of strings to an existing list within the agent's state.
  - **Parameters**:
    - `left` (list[str]): The current list of messages from the agent's state.
    - `right` (str | list[str]): The new message(s) to be added.
  - **Returns**: (list[str]): The combined list of messages.
  - **Usage**: Often used in `TypedDict` state definitions with `Annotated` types to simplify appending messages during graph execution, e.g., `error_messages: Annotated[list[str], add_string_message]`.
