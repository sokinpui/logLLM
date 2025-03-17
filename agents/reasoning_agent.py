from typing import List, Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field

from .agent_abc import Agent, add_string_message
from llm_model import LLMModel

class State(TypedDict):
    messages: Annotated[List[str], add_string_message]
    original_prompt: str
    question: str
    context: str
    goal: str
    sub_questions: List[str]
    final_response: str

class ReasoningAgent(Agent):
    def __init__(self, model : LLMModel):
        self._model = model

        self.workflow = StateGraph(State)
        # self._build_graph()
        # self.graph = self.workflow.compile()

    def run(self, state: State) -> State:
        """
        run the agent synchronously with `invoke` method
        """
        state = self.graph.invoke(state)
        return state

    async def arun(self, state: State) -> State:
        """
        run the agent asynchronously with `invoke` method
        """
        state = await self.graph.ainvoke(state)
        return state

    def _build_graph(self):
        self.workflow.add_node("parse_input", self.parse_input)
        self.workflow.add_node("context_understanding", self.context_understanding)
        self.workflow.add_node("determine_goal", self.determine_goal)
        self.workflow.add_node("decompose_question", self.decompose_question)
        self.workflow.add_node("solve_sub_question", self.solve_sub_question)
        self.workflow.add_node("combine_sub_answer", self.combine_sub_answer)
        self.workflow.add_node("formulate_response", self.formulate_response)

        self.workflow.add_conditional_edges(
                START,
                self.is_question,
                {
                    True: "parse_input",
                    False: END

                }
        )

        self.workflow.add_edge("parse_input", "context_understanding")
        self.workflow.add_edge("context_understanding", "determine_goal")
        self.workflow.add_edge("determine_goal", "decompose_question")

        self.workflow.add_edge("decompose_question", "solve_sub_question")

        self.workflow.add_conditional_edges(
                "solve_sub_question",
                self.is_sub_question_empty,
                {
                    False: "solve_sub_question",
                    True: "combine_sub_answer"
                }
        )
        self.workflow.add_edge("combine_sub_answer", "formulate_response")
        self.workflow.add_edge("formulate_response", END)

    def get_prompt(self, state: State) -> State | dict:
        return state

    def is_question(self, state: State) -> bool:
        """
        determine if the user input is a question

        Output:
            True: if the input is a question, or can be converted into a question
            False: cannot be converted into a question
        """
        original_prompt = state["original_prompt"]

        sound = f"""
**Task**: Determine if the user input can be converted into a question. Follow these steps:

1. **Evaluate Input Type**:
   - Check if the input is already a question (e.g., starts with "What," "How," "Why," etc.).
   - If it’s not a question, determine if it contains an implicit query or intent that can be converted into a question.

2. **Identify Implicit Intent**:
   - Look for keywords or phrases that suggest an underlying question (e.g., "I want to know…," "Explain…," "Tell me about…").
   - Use context clues to infer the user’s intent (e.g., "It’s cold here" → "Can you adjust the temperature?").

3. **output**:
    - if it the input is already a question: answer yes
    - if it is not a question:
        - if it can be converted to a question: answer yes
        - if it cannot be converted to a question: answer no

**User Input**: "{original_prompt}"
        """

        class Schema(BaseModel):
            is_question: bool = Field(description="Whether the input is a question")

        response = self._model.generate(sound, Schema)

        return response.is_question

    def parse_input(self, state: State) -> State | dict:
        """
        convert the user input into a question
        """

        original_prompt = state["original_prompt"]

        sound = f"""
**Task**: Determine if the user input can be converted into a question. If yes, rewrite it as a clear and actionable question. Follow these steps:

1. **Evaluate Input Type**:
   - Check if the input is already a question (e.g., starts with "What," "How," "Why," etc.).
   - If it’s not a question, determine if it contains an implicit query or intent that can be converted into a question.

2. **Identify Implicit Intent**:
   - Look for keywords or phrases that suggest an underlying question (e.g., "I want to know…," "Explain…," "Tell me about…").
   - Use context clues to infer the user’s intent (e.g., "It’s cold here" → "Can you adjust the temperature?").

3. **Rewrite as Question**:
   - If the input can be converted, rewrite it as a clear, concise, and actionable question.
   - Ensure the rewritten question aligns with the user’s intent and context.

4. **Output Format**:
   - **Converted Question**: [If applicable, the rewritten question]

**Example**:
**User Input**: "Tell me about blockchain."
- **Is Question?**: No.
- **Converted Question**: "What is blockchain, and how does it work?"
- **Notes**: The input implies a request for information, which can be converted into a question.

**User Input**: "How does blockchain work?"
- **Is Question?**: Yes.
- **Converted Question**: [No conversion needed]
- **Notes**: The input is already a question.

**User Input**: "It’s cold here."
- **Is Question?**: No.
- **Converted Question**: "Can you adjust the temperature?"
- **Notes**: The input implies a request for action, which can be converted into a question.

**User Input**: "{original_prompt}"
        """

        question = self._model.generate(sound)

        return {
            "question": question
            }

    def context_understanding(self, state: State) -> State | dict:
        question = state["question"]

        sound = f"""
**Task**: Analyze the following user prompt to extract its context, domain, and potential ambiguities. Follow these steps:

1. **Identify Explicit Context**:
   - Use the "5 Ws" (Who, What, Where, When, Why/How) to list explicit details.
   - Example: "How do I fix a leaking sink?" → What: Fixing a sink. How: Repair steps.

2. **Domain Classification**:
   - Classify the question into a broad domain (e.g., "Home Repair," "Science," "Technology").
   - If hybrid (e.g., "AI in healthcare"), identify all relevant domains.

3. **Ambiguity Detection**:
   - List ambiguous terms/phrases (e.g., "best," "quickly," jargon like "LLM").
   - For each ambiguity, propose 1–2 clarifying questions or assumptions.

4. **Assumptions & Scope**:
   - State assumptions needed to answer (e.g., user’s location, technical skill level).
   - Define the scope (e.g., "Focus on cost-effective solutions").

**Output Format**:
- **Explicit Context**: [Bullet points of 5 Ws]
- **Domain**: [Domain + subdomains if applicable]
- **Ambiguities**: [Term + possible meanings/clarifications]
- **Assumptions**: [List of assumptions to proceed]

**Example**:
**User Prompt**: "Explain how blockchain works for supply chains."
- **Explicit Context**:
  - What: Blockchain technology.
  - How: Functionality in supply chains.
- **Domain**: Technology (Blockchain), Logistics.
- **Ambiguities**:
  - "Works": Clarify depth (technical vs. high-level).
  - "Supply chains": Specific industry? (Assume retail).
- **Assumptions**:
  - User seeks a non-technical explanation.
  - Focus on transparency/tracking use cases.

  **User Prompt**:  "{question}"
        """

        context = self._model.generate(sound)

        return {
                "context": context,
        }

    def determine_goal(self, state: State) -> State | dict:

        context = state["context"]
        question = state["question"]

        sound = f"""
        **Task**: Analyze the following user prompt to determine its goal and the type of response required. Follow these steps:

1. **Categorize Question Type**:
   - Classify the question into one or more of the following types:
     - **Factual**: Requests specific information (e.g., "What is X?").
     - **Procedural**: Asks for steps or instructions (e.g., "How do I do Y?").
     - **Comparative**: Compares two or more things (e.g., "What’s the difference between A and B?").
     - **Causal**: Explains reasons or causes (e.g., "Why did Z happen?").
     - **Hypothetical**: Explores scenarios or possibilities (e.g., "What if X happens?").
     - **Opinion-based**: Seeks subjective input (e.g., "What do you think about X?").

2. **Determine Response Structure**:
   - Based on the question type, define the structure of the expected answer:
     - **Factual**: Concise, direct answer.
     - **Procedural**: Step-by-step instructions.
     - **Comparative**: Point-by-point comparison.
     - **Causal**: Explanation with logical flow.
     - **Hypothetical**: Scenario analysis with assumptions.
     - **Opinion-based**: Balanced perspective with reasoning.

3. **Clarify Goal**:
   - Identify the user’s underlying goal (e.g., "Why is the sky blue?" → Understand light scattering).
   - If the goal is unclear, propose 1–2 clarifying questions.

4. **Output Format**:
   - **Question Type**: [Type(s) of question]
   - **Response Structure**: [Structure of the answer]
   - **User Goal**: [Underlying goal or intent]
   - **Clarifying Questions**: [If needed, list questions to refine the goal]

**Example**:
**User Prompt**: "How do I bake a cake?"
- **Question Type**: Procedural.
- **Response Structure**: Step-by-step instructions.
- **User Goal**: Learn how to bake a cake from scratch.
- **Clarifying Questions**: None.

**User Prompt**: "What’s better: electric cars or gas cars?"
- **Question Type**: Comparative, Opinion-based.
- **Response Structure**: Point-by-point comparison with pros/cons.
- **User Goal**: Decide which type of car to buy.
- **Clarifying Questions**:
  - Are you looking for cost, environmental impact, or performance comparisons?

**User Prompt**: "{question}"
        """

        goal = self._model.generate(sound)

        return {
                "goal": goal,
        }

    def decompose_question(self, state: State) -> State | dict:

        context = state["context"]
        question = state["question"]
        goal = state["goal"]

        sound = f"""
        **Task**: Break down the following question into smaller, logically connected sub-questions. Use the provided context to guide the decomposition process. Follow these steps:

1. **Review Context**:
   - **Explicit Context**: {context}
   - Use this context to ensure the decomposition aligns with the user’s intent and domain.

2. **Identify Key Components**:
   - Extract the main components of the question (e.g., subjects, actions, relationships).
   - Example: "How does blockchain improve supply chain transparency?" → Components: Blockchain, Supply Chain, Transparency.

3. **Decompose into Sub-Questions**:
   - Use logical reasoning to split the question into smaller, answerable sub-questions.
   - Apply one or more of the following decomposition strategies:
     - **Divide and Conquer**: Break into independent sub-tasks (e.g., "What is blockchain?" → "How does it work?").
     - **Backward Chaining**: Start from the goal and identify prerequisites (e.g., "Why is transparency important in supply chains?").
     - **Schema-Based**: Use domain-specific templates (e.g., for "How does X work?" → "What is X?" → "What are its components?" → "How do they interact?").

4. **Ensure Logical Flow**:
   - Arrange sub-questions in a logical sequence (e.g., foundational → advanced).
   - Ensure each sub-question is necessary to answer the main question.

5. **Output Format**:
   - **Main Question**: [Original question]
   - **Key Components**: [List of main components]
   - **Sub-Questions**: [List of sub-questions in logical order]

**Example**:
**Main Question**: "How does blockchain improve supply chain transparency?"
- **Context**:
  - **Explicit Context**: What: Blockchain technology. How: Functionality in supply chains.
  - **Domain**: Technology (Blockchain), Logistics.
  - **Assumptions**: User seeks a non-technical explanation. Focus on transparency/tracking use cases.
- **Key Components**: Blockchain, Supply Chain, Transparency.
- **Sub-Questions**:
  1. What is blockchain, and how does it work?
  2. What are the key challenges in supply chain transparency?
  3. How does blockchain address these challenges?
  4. What are real-world examples of blockchain improving supply chain transparency?

**Main Question**: "{question}"
        """

        class Schema(BaseModel):
            sub_questions: List[str] = Field(description="The sub-questions")


        response = self._model.generate(sound, Schema)

        sub_questions = response.sub_questions

        return {
            "sub_questions": sub_questions
        }

    def solve_sub_question(self, state: State) -> State | dict:
        sub_question = state["sub_questions"][0]
        context = state["context"]

        sound = f"""
**Task**: Answer the following sub-question based on the provided context, goal, and assumptions. Follow these steps:

1. **Review Context and Goal**:
    - **Explicit Context**: {context}

2. **Answer the Sub-Question**:
   - Provide a concise and accurate answer to the sub-question.
   - Use trusted knowledge sources or logical reasoning.
   - If the answer requires assumptions, state them explicitly.

**Sub-Question**: "{sub_question}"
        """

        response = self._model.generate(sound)

        return {
            "messages": response
            }

    def is_sub_question_empty(self, state: State) -> bool:
        state["sub_questions"].pop(0)
        return len(state["sub_questions"]) == 0

    def combine_sub_answer(self, state: State) -> State | dict:
        goal = state["goal"]
        messages = state["messages"]
        context = state["context"]

        sound = f"""
**Task**: Combine the following sub-answers into a single, coherent response to the main question. Follow these steps:

1. **Review Context and Goal**:
   - **Context**: {context}
   - **Goal**: {goal}

2. **Organize Sub-Answers**:
   - Arrange the sub-answers in a logical sequence that builds toward answering the main question.
   - Use connectors (e.g., "because," "therefore," "as a result") to maintain flow and coherence.

3. **Synthesize Information**:
   - Combine the sub-answers into a single narrative, avoiding redundancy.
   - Highlight key insights or conclusions that emerge from the sub-answers.

4. **Validate the Response**:
   - Ensure the final response addresses all parts of the main question.
   - Check for consistency and logical flow.

**all sub-answers**: {messages}
"""

        response = self._model.generate(sound)

        return {
                "messages": response
            }

    def formulate_response(self, state: State) -> State | dict:
        combined_answer = state["messages"][-1]

        sound = f"""
**Task**: Formulate a final response based on the synthesized sub-answers. Follow these steps:

2. **Structure the Response**:
   - Begin with a **brief introduction** that restates the main question or intent.
   - Organize the body of the response into **logical sections** (e.g., overview, details, examples).
   - End with a **conclusion** that summarizes key points or provides actionable insights.

3. **Tailor the Tone and Depth**:
   - Adjust the tone (e.g., formal, casual) and depth (e.g., technical, simple) based on the user’s assumed knowledge level and preferences.
   - Use **connectors** (e.g., "because," "therefore," "for example") to maintain flow and coherence.

4. **Validate the Response**:
   - Ensure the response addresses all parts of the main question.
   - Check for clarity, conciseness, and logical flow.

**Synthesized Answer**: {combined_answer}
"""

        response = self._model.generate(sound)

        return {
            "final_response": response
        }


def main():
    from llm_model import GeminiModel

    model = GeminiModel()

    reasoning_agent = ReasoningAgent(model)

    state = {
        "original_prompt": "How do I bake a cake?",
    }

    response = reasoning_agent.run(state)

    import pprint

    pprint.pprint(response)

if __name__ == "__main__":
    main()
