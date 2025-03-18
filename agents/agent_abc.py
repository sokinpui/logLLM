from abc import ABC, abstractmethod
from langgraph.graph.state import CompiledStateGraph

def add_string_message(left: list[str], right: str | list[str]) -> list[str]:
    if isinstance(right, str):
        return left + [right]
    return left + right

class Agent(ABC):

    graph: CompiledStateGraph

    @abstractmethod
    def _build_graph(self, typed_state) -> CompiledStateGraph:
        pass

    @abstractmethod
    def run(self):
        pass

    @abstractmethod
    async def arun(self):
        pass

