from abc import ABC, abstractmethod
from langgraph.graph import StateGraph

def add_string_message(left: list[str], right: str | list[str]) -> list[str]:
    if isinstance(right, str):
        return left + [right]
    return left + right

class Agent(ABC):

    workflow: StateGraph
    graph: StateGraph

    @abstractmethod
    def _build_graph(self):
        pass

    @abstractmethod
    def run(self):
        pass

    @abstractmethod
    async def arun(self):
        pass

