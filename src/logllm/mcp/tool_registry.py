# src/logllm/mcp/tool_registry.py
from typing import Callable, Dict, Any, Optional, Type
from pydantic import BaseModel, ValidationError

from ..utils.logger import Logger
from .schemas import (
    MCPToolDefinition,
    MCPToolCall,
    MCPToolResult,
    MCPToolParameterSchema,
)


# Type alias for a tool function
ToolCallable = Callable[
    ..., Any
]  # Arguments will be based on tool definition, returns Any


class RegisteredTool(BaseModel):
    """Internal representation of a registered tool."""

    name: str
    callable_func: ToolCallable
    definition: MCPToolDefinition
    parameter_model: Optional[Type[BaseModel]] = (
        None  # Optional Pydantic model for input validation
    )


class ToolRegistry:
    """A simple registry for discovering and invoking tools."""

    def __init__(self, logger: Optional[Logger] = None):
        self._tools: Dict[str, RegisteredTool] = {}
        self._logger = logger or Logger()

    def _create_pydantic_model_for_tool_params(
        self, tool_name: str, params_schema: Dict[str, MCPToolParameterSchema]
    ) -> Optional[Type[BaseModel]]:
        """Dynamically creates a Pydantic model for tool parameter validation if schema is provided."""
        if not params_schema:
            return None

        fields: Dict[str, Any] = {}
        for param_name, schema in params_schema.items():
            # Basic type mapping; can be expanded
            field_type: Any
            if schema.type == "string":
                field_type = str
            elif schema.type == "integer":
                field_type = int
            elif schema.type == "number":
                field_type = float
            elif schema.type == "boolean":
                field_type = bool
            elif schema.type == "array":
                # For simplicity, assuming array of basic types or Any.
                # More complex item types would need deeper schema parsing.
                item_type_str = (
                    schema.items.get("type", "Any") if schema.items else "Any"
                )
                item_type = str  # Default for now
                if item_type_str == "string":
                    item_type = str
                elif item_type_str == "integer":
                    item_type = int
                # ... other item types
                field_type = List[item_type]  # type: ignore
            elif schema.type == "object":
                field_type = Dict[str, Any]  # Simplified
            else:
                field_type = Any

            field_default = ... if schema.required else None
            fields[param_name] = (
                field_type,
                Field(default=field_default, description=schema.description),
            )

        # Create a unique model name to avoid Pydantic conflicts
        model_name = f"{tool_name.capitalize().replace('_','')}ParamsModel"
        try:
            param_model = type(model_name, (BaseModel,), {"__annotations__": fields})
            return param_model
        except Exception as e:
            self._logger.error(
                f"Failed to create Pydantic model for tool '{tool_name}' parameters: {e}",
                exc_info=True,
            )
            return None

    def register_tool(self, func: ToolCallable, definition: MCPToolDefinition):
        """
        Registers a tool function along with its definition.
        The function's signature should ideally match the parameters in the definition.
        """
        if definition.name in self._tools:
            self._logger.warning(
                f"Tool '{definition.name}' is already registered. Overwriting."
            )

        param_model = None
        if definition.parameters:
            param_model = self._create_pydantic_model_for_tool_params(
                definition.name, definition.parameters
            )
            if not param_model:
                self._logger.warning(
                    f"Could not create parameter validation model for tool '{definition.name}'. Proceeding without validation."
                )

        self._tools[definition.name] = RegisteredTool(
            name=definition.name,
            callable_func=func,
            definition=definition,
            parameter_model=param_model,
        )
        self._logger.info(f"Tool '{definition.name}' registered.")

    def get_tool_definition(self, tool_name: str) -> Optional[MCPToolDefinition]:
        """Retrieves the definition of a registered tool."""
        tool = self._tools.get(tool_name)
        return tool.definition if tool else None

    def get_all_tool_definitions(self) -> List[MCPToolDefinition]:
        """Returns definitions of all registered tools."""
        return [tool.definition for tool in self._tools.values()]

    def invoke_tool(self, tool_call: MCPToolCall) -> MCPToolResult:
        """
        Invokes a registered tool based on a ToolCall object.
        Validates arguments against the tool's parameter schema if available.
        """
        self._logger.info(
            f"Attempting to invoke tool: '{tool_call.tool_name}' with call ID: {tool_call.id}"
        )
        registered_tool = self._tools.get(tool_call.tool_name)

        if not registered_tool:
            self._logger.error(f"Tool '{tool_call.tool_name}' not found in registry.")
            return MCPToolResult(
                call_id=tool_call.id,
                tool_name=tool_call.tool_name,
                output=None,
                is_error=True,
                error_message=f"Tool '{tool_call.tool_name}' not found.",
            )

        validated_args = tool_call.arguments
        if registered_tool.parameter_model:
            try:
                # Pydantic model validation handles required fields etc.
                model_instance = registered_tool.parameter_model.model_validate(
                    tool_call.arguments
                )
                validated_args = model_instance.model_dump(
                    exclude_unset=True
                )  # Pass only provided args
                self._logger.debug(
                    f"Tool '{tool_call.tool_name}' arguments validated successfully."
                )
            except ValidationError as ve:
                self._logger.error(
                    f"Argument validation failed for tool '{tool_call.tool_name}': {ve}"
                )
                return MCPToolResult(
                    call_id=tool_call.id,
                    tool_name=tool_call.tool_name,
                    output=None,
                    is_error=True,
                    error_message=f"Invalid arguments: {str(ve)}",
                )

        try:
            # Assumes the callable function can accept arguments as a dictionary or kwargs
            result_data = registered_tool.callable_func(**validated_args)
            self._logger.info(f"Tool '{tool_call.tool_name}' executed successfully.")
            return MCPToolResult(
                call_id=tool_call.id,
                tool_name=tool_call.tool_name,
                output=result_data,
                is_error=False,
            )
        except Exception as e:
            self._logger.error(
                f"Error executing tool '{tool_call.tool_name}': {e}", exc_info=True
            )
            return MCPToolResult(
                call_id=tool_call.id,
                tool_name=tool_call.tool_name,
                output=None,
                is_error=True,
                error_message=str(e),
            )


# Example Usage (typically done elsewhere, e.g., when setting up the application)
# def example_tool_function(param1: str, optional_param: int = 0) -> Dict[str, Any]:
#     """This is an example tool that does something."""
#     return {"message": f"Tool called with {param1} and {optional_param}"}

# example_tool_def = MCPToolDefinition(
#     name="example_tool",
#     description="An example tool for demonstration.",
#     parameters={
#         "param1": MCPToolParameterSchema(type="string", description="A required string parameter.", required=True),
#         "optional_param": MCPToolParameterSchema(type="integer", description="An optional integer parameter.", required=False)
#     }
# )

# registry = ToolRegistry()
# registry.register_tool(example_tool_function, example_tool_def)
# tool_call_request = MCPToolCall(tool_name="example_tool", arguments={"param1": "hello"})
# result = registry.invoke_tool(tool_call_request)
# print(result.model_dump_json(indent=2))
