from typing import List, Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field

from .agent_abc import Agent, add_string_message
from utils.llm_model import LLMModel
from utils.prompts_manager.prompts_manager import PromptsManager  # Import PromptsManager

class State(TypedDict):
    messages: Annotated[List[str], add_string_message]
    original_prompt: str
    question: str
    context: str
    goal: str
    sub_questions: List[str]
    processed_sub_questions: Annotated[List[str], add_string_message]
    final_response: str

class ReasoningAgent(Agent):
    def __init__(self, model: LLMModel, typed_state):
        self._model = model
        self.prompts_manager = PromptsManager(json_file="prompts/prompts.json")  # Initialize PromptsManager
        self.graph = self._build_graph(typed_state)

    def run(self, state: State) -> State:
        state = self.graph.invoke(state)
        return state

    async def arun(self, state: State) -> State:
        state = await self.graph.ainvoke(state)
        return state

    def _build_graph(self, typed_state) -> CompiledStateGraph:
        workflow = StateGraph(typed_state)
        workflow.add_node("parse_input", self.parse_input)
        workflow.add_node("context_understanding", self.context_understanding)
        workflow.add_node("determine_goal", self.determine_goal)
        workflow.add_node("decompose_question", self.decompose_question)
        workflow.add_node("solve_sub_question", self.solve_sub_question)
        workflow.add_node("combine_sub_answer", self.combine_sub_answer)
        workflow.add_node("formulate_response", self.formulate_response)

        workflow.add_conditional_edges(
            START,
            self.is_question,
            {True: "parse_input", False: END}
        )

        workflow.add_edge("parse_input", "context_understanding")
        workflow.add_edge("context_understanding", "determine_goal")
        workflow.add_edge("determine_goal", "decompose_question")
        workflow.add_edge("decompose_question", "solve_sub_question")
        workflow.add_conditional_edges(
            "solve_sub_question",
            self.is_sub_question_empty,
            {False: "solve_sub_question", True: "combine_sub_answer"}
        )
        workflow.add_edge("combine_sub_answer", "formulate_response")
        workflow.add_edge("formulate_response", END)

        return workflow.compile()

    def get_prompt(self, state: State) -> State | dict:
        return state

    def is_question(self, state: State) -> bool:
        original_prompt = state["original_prompt"]
        prompt = self.prompts_manager.get_prompt(original_prompt=original_prompt)

        class Schema(BaseModel):
            is_question: bool = Field(description="Whether the input is a question")

        response = self._model.generate(prompt, Schema)
        return response.is_question

    def parse_input(self, state: State) -> State | dict:
        original_prompt = state["original_prompt"]
        prompt = self.prompts_manager.get_prompt(original_prompt=original_prompt)
        question = self._model.generate(prompt)
        return {"question": question}

    def context_understanding(self, state: State) -> State | dict:
        question = state["question"]
        prompt = self.prompts_manager.get_prompt(question=question)
        context = self._model.generate(prompt)
        return {"context": context}

    def determine_goal(self, state: State) -> State | dict:
        question = state["question"]
        prompt = self.prompts_manager.get_prompt(question=question)
        goal = self._model.generate(prompt)
        return {"goal": goal}

    def decompose_question(self, state: State) -> State | dict:
        context = state["context"]
        question = state["question"]
        prompt = self.prompts_manager.get_prompt(question=question, context=context)

        class Schema(BaseModel):
            sub_questions: List[str] = Field(description="The sub-questions")

        response = self._model.generate(prompt, Schema)
        return {"sub_questions": response.sub_questions}

    def solve_sub_question(self, state: State) -> State | dict:
        sub_question = state["sub_questions"][0]
        context = state["context"]
        prompt = self.prompts_manager.get_prompt(sub_question=sub_question)
        response = self._model.generate(prompt)
        return {"messages": response}

    def is_sub_question_empty(self, state: State) -> bool:
        sub_question = state["sub_questions"].pop(0)
        state["processed_sub_questions"].append(sub_question)
        return len(state["sub_questions"]) == 0

    def combine_sub_answer(self, state: State) -> State | dict:
        goal = state["goal"]
        messages = state["messages"]
        context = state["context"]
        prompt = self.prompts_manager.get_prompt(goal=goal, context=context, messages=str(messages))
        response = self._model.generate(prompt)
        return {"messages": response}

    def formulate_response(self, state: State) -> State | dict:
        combined_answer = state["messages"][-1]
        prompt = self.prompts_manager.get_prompt(combined_answer=combined_answer)
        response = self._model.generate(prompt)
        return {"final_response": response}

def main():
    from utils.llm_model import GeminiModel

    model = GeminiModel()
    reasoning_agent = ReasoningAgent(model, State)

    state = {
        "original_prompt": "Can you check if there exist some IP address keep login as a invalid userk",
    }

    response = reasoning_agent.run(state)
    import json
    with open("./result.json", "w") as f:
        json.dump(response, f, indent=4)

if __name__ == "__main__":
    main()
