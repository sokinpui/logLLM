# MCP: Tool Registry (`tool_registry.py`)

## File: `src/logllm/mcp/tool_registry.py`

### Overview

The `ToolRegistry` provides a centralized mechanism to define, register, and invoke "tools." A tool is simply a Python function that can be called by name, with its capabilities and parameters described by an `MCPToolDefinition`. This allows the system, and potentially LLMs, to discover and use available functionalities dynamically.

### Class: `ToolRegistry`

- **Purpose**: To manage a collection of callable tools, validate their inputs, and handle their execution.

- **Key Methods**:

  - **`__init__(self, logger: Optional[Logger] = None)`**:

    - Initializes the registry's internal tool dictionary.

  - **`register_tool(self, func: ToolCallable, definition: MCPToolDefinition)`**:

    - Registers a tool. It takes the callable Python function and its corresponding `MCPToolDefinition`.
    - It automatically creates a Pydantic model from the `definition.parameters` to handle input validation.
    - **Example**: `registry.register_tool(my_search_func, my_search_tool_def)`

  - **`get_tool_definition(self, tool_name: str) -> Optional[MCPToolDefinition]`**:

    - Retrieves the definition for a single tool by its name.

  - **`get_all_tool_definitions(self) -> List[MCPToolDefinition]`**:

    - Returns a list of all registered `MCPToolDefinition`s. This is crucial for providing the list of available tools to an LLM.

  - **`invoke_tool(self, tool_call: MCPToolCall) -> MCPToolResult`**:
    - The core execution method.
    - It takes an `MCPToolCall` object (which an LLM might generate).
    - It finds the corresponding tool in the registry.
    - It validates the `tool_call.arguments` against the tool's parameter schema.
    - It calls the tool function with the validated arguments.
    - It wraps the function's output (or any error) in an `MCPToolResult` object.

### How to Define and Register a Tool

The process involves three steps:

1.  **Write the Python function** that performs the tool's action.
2.  **Create an `MCPToolDefinition`** that describes the function, its purpose, and its parameters.
3.  **Register them** with a `ToolRegistry` instance.

#### Example

```python
# --- 1. Define the tool's function ---
def fetch_logs_from_elasticsearch(group_name: str, query_string: str, limit: int = 100) -> dict:
    """Fetches logs from a specific group in Elasticsearch."""
    # ... implementation to query Elasticsearch ...
    print(f"Fetching {limit} logs for '{group_name}' with query: '{query_string}'")
    return {"status": "success", "count": 5, "logs": [...]}

# --- 2. Create the MCPToolDefinition ---
from src.logllm.mcp.schemas import MCPToolDefinition, MCPToolParameterSchema

fetch_logs_tool_def = MCPToolDefinition(
    name="fetch_logs_from_elasticsearch",
    description="Fetches log entries from Elasticsearch for a specified group, filtering by a query string.",
    parameters={
        "group_name": MCPToolParameterSchema(
            type="string",
            description="The log group to query (e.g., 'apache', 'system_kernel').",
            required=True
        ),
        "query_string": MCPToolParameterSchema(
            type="string",
            description="A Lucene query string to filter the logs.",
            required=True
        ),
        "limit": MCPToolParameterSchema(
            type="integer",
            description="The maximum number of log entries to return.",
            required=False # This parameter is optional
        )
    }
)

# --- 3. Register the tool ---
from src.logllm.mcp.tool_registry import ToolRegistry
from src.logllm.mcp.schemas import MCPToolCall

# Typically, you would have a single registry instance for your application
registry = ToolRegistry()
registry.register_tool(fetch_logs_from_elasticsearch, fetch_logs_tool_def)

# Now the tool can be invoked
tool_call_request = MCPToolCall(
    tool_name="fetch_logs_from_elasticsearch",
    arguments={"group_name": "apache", "query_string": "status:500"}
)

result = registry.invoke_tool(tool_call_request)

print(result.model_dump_json(indent=2))
```
