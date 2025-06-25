# MCP: Context Manager (`mcp_manager.py`)

## File: `src/logllm/mcp/mcp_manager.py`

### Overview

The `ContextManager` is a utility class designed to simplify the creation and assembly of MCP objects, primarily `ContextItem` and `ContextPayload`.

### Class: `ContextManager`

- **Purpose**: To provide a clean, consistent interface for building context that conforms to the MCP schemas.

- **Key Methods**:

  - **`__init__(self, logger: Optional[Logger] = None)`**:

    - Initializes the manager with an optional logger instance.

  - **`create_context_item(self, type: Union[ContextItemType, str], data: Any, ...)`**:

    - A factory method for creating a `ContextItem`.
    - **Parameters**:
      - `type`: The `ContextItemType` or a custom string.
      - `data`: The payload for the context item.
      - `source_component`, `tags`, `relevance_score`, `related_item_ids`: Optional metadata fields to populate the `ContextMetadata`.
    - **Returns**: A fully formed `ContextItem` instance.

  - **`build_context_payload(self, items: List[ContextItem], ...)`**:

    - Assembles a list of `ContextItem` objects into a single `ContextPayload`.
    - **Returns**: A `ContextPayload` instance.

  - **`format_payload_for_llm_prompt(self, payload: ContextPayload, ...)`**:
    - A utility method to convert a `ContextPayload` into a string that can be easily injected into an LLM prompt.
    - It sorts items by timestamp (most recent first) and formats them in a readable way, including type, source, and data.
    - This provides a basic, consistent way to represent complex context as text for the LLM.

### Example Usage

```python
from src.logllm.mcp.mcp_manager import ContextManager
from src.logllm.mcp.schemas import ContextItemType

# 1. Instantiate the manager
ctx_manager = ContextManager()

# 2. Create individual context items
user_query_item = ctx_manager.create_context_item(
    type=ContextItemType.USER_QUERY,
    data="Show me all null pointer exceptions from the last hour.",
    source_component="API:user_input"
)

retrieved_logs_item = ctx_manager.create_context_item(
    type=ContextItemType.LOG_DATA_PARSED,
    data=[{"loglevel": "ERROR", "message": "Null pointer exception at..."}, ...],
    source_component="ElasticsearchDataService",
    tags=["retrieved_logs", "java_service"]
)

# 3. Build a context payload
payload = ctx_manager.build_context_payload(items=[user_query_item, retrieved_logs_item])

# 4. Format for an LLM (optional)
prompt_context_string = ctx_manager.format_payload_for_llm_prompt(payload)
print(prompt_context_string)

# full_prompt = f"""
# You are a log analysis expert. Based on the following context, answer the user's query.
#
# {prompt_context_string}
#
# Expert Answer:
# """
```
