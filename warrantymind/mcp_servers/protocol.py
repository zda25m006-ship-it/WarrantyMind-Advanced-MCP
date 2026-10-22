from typing import Callable, Dict, Any, List
from warrantymind.schemas import BaseModel


class MCPToolDefinition(BaseModel):
    server_name: str
    tool_name: str
    description: str
    input_schema: Dict[str, Any]


class LocalFastMCPRegistry:
    '''
    Lightweight FastMCP-compatible protocol registry that exposes tools both:
    1. Over standard MCP JSON-RPC / tool discovery (`list_tools()`, `call_tool()`)
    2. Directly to the LangGraph Subgraphs without requiring separate OS sub-processes during local laptop startup.
    '''
    def __init__(self, server_name: str, instructions: str):
        self.server_name = server_name
        self.instructions = instructions
        self._tools: Dict[str, Callable] = {}
        self._Metadata: Dict[str, MCPToolDefinition] = {}

    def tool(self, name: str, description: str, input_schema: Dict[str, Any]):
        def decorator(fn: Callable):
            self._tools[name] = fn
            self._Metadata[name] = MCPToolDefinition(
                server_name=self.server_name,
                tool_name=name,
                description=description,
                input_schema=input_schema,
            )
            return fn
        return decorator

    def list_tools(self) -> List[Dict[str, Any]]:
        return [m.model_dump() for m in self._Metadata.values()]

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' not registered on MCP server '{self.server_name}'")
        return self._tools[name](**arguments)
