from typing import List, Dict, Any, Annotated
from langgraph.graph import StateGraph

from .agent_abc import Agent, add_string_message
from llm_model import LLMModel

class State(Agent):
    messages: Annotated[List[str], add_string_message]

class ReasoningAgent(Agent):
    def __init__(self, model : LLMModel):
        self._model = model

        self.workflow = StateGraph(State)

        self.graph = self._build_graph(self.workflow)

    def _build_graph(self, workflow: StateGraph) -> StateGraph:
        pass

        graph = workflow.compile()

        return graph

    def parse_input(self, input: Dict[str, Any]) -> State:

        sound = f"""
        Determine if it’s a direct question, statement, command, or ambiguous prompt.
        """



