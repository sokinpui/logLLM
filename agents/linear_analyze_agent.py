from langgraph.graph import StateGraph, END, START
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field
from typing import TypedDict, Annotated, List

from .agent_abc import Agent, add_string_message
from data_struct import Event
from database import ElasticsearchDatabase
from llm_model import LLMModel
from logger import Logger
import config as cfg
from .chunk_manager import ESTextChunkManager
import prompts.agents.linear_analyze_agent as pal

class LinearAnalyzeAgentState(TypedDict):
    working_event: Event
    message: Annotated[list[str], add_string_message]
    memories: Annotated[list[str], add_string_message]
    working_file_ids: list[str] # list of file ids
    chunk: str


class LinearAnalyzeAgent(Agent):
    def __init__(self, model : LLMModel, db : ElasticsearchDatabase, typed_state):

        self._model = model
        self.graph = self._build_graph(typed_state)

        self._db = db
        self._logger = Logger()

        self._memory_size = cfg.MEMRORY_TOKENS_LIMIT
        self._chunk_manager: ESTextChunkManager

    def run(self, state: LinearAnalyzeAgentState) -> LinearAnalyzeAgentState:
        """
        run the agent synchronously with `invoke` method
        """
        state = self.graph.invoke(state)
        return state

    async def arun(self, state: LinearAnalyzeAgentState) -> LinearAnalyzeAgentState:
        """
        run the agent asynchronously with `invoke` method
        """
        state = await self.graph.ainvoke(state)
        return state

    def _build_graph(self, typed_state) -> CompiledStateGraph:
        workflow = StateGraph(typed_state)

        workflow.add_node("setup", self.setup_working_file)
        workflow.add_node("get_chunk", self.get_chunk)
        workflow.add_node("chunk_analysis", self.chunk_analysis)
        workflow.add_node("memorize", self.memorize)
        workflow.add_node("pop_file_id", self.pop_file_id)

        workflow.add_edge(START, "setup")
        workflow.add_edge("setup", "get_chunk")
        workflow.add_edge("get_chunk", "chunk_analysis")
        workflow.add_edge("chunk_analysis", "memorize")
        workflow.add_conditional_edges(
            "memorize",
            self.is_working_file_done,
            {
                True: "pop_file_id",
                False: "get_chunk"
            }
        )
        workflow.add_conditional_edges(
            "pop_file_id",
            self.is_done,
            {
                True: END,
                False: "setup"
            }
        )

        graph = workflow.compile()
        return graph

    def is_done(self, state: LinearAnalyzeAgentState):
        """
        Check if the agent is done
        """
        return len(state["working_file_ids"]) == 0

    def is_working_file_done(self, state: LinearAnalyzeAgentState):
        """
        Check if the current working file is done
        """
        return self._chunk_manager.is_end()

    def get_chunk(self, state: LinearAnalyzeAgentState):
        """
        Get the next chunk of text to analyze
        """
        tokens_limit = self._model.context_size - self._memory_size
        token_count_fn = self._model.token_count
        chunk = self._chunk_manager.get_next_chunk(max_len=tokens_limit, len_fn=token_count_fn)
        return {
            "chunk": chunk
        }

    def chunk_analysis(self, state: LinearAnalyzeAgentState):
        """
        Analyze the chunk of text
        """
        event = state["working_event"]
        chunk = state["chunk"]
        required_info = state["message"][0] # get the first message that should be the required info in last step
        memories = state["memories"]

        prompt = pal.chunk_analysis_prompt(event.description, required_info, memories, chunk)

        result = self._model.generate(prompt)
        self._logger.info(f"Chunk analysis result:\n{result[:100]}")

        return {
            "message": result
        }

    def memorize(self, state: LinearAnalyzeAgentState):
        """
        Memorize the result
        """
        memory = state["memories"]

        if len(state["message"]) >= 1:
            last_result = state["message"][-1]
        else:
            last_result = ""
        event = state["working_event"]
        reqired_info = state["message"][0]

        summary = pal.summarize_chunk_analysis_result(event.description, reqired_info, last_result)

        result = self._model.generate(summary)
        memory.append(result)

        self._logger.info(f"Memorized result:\n{result[:100]}")

        total_tokens = sum([self._model.token_count(m) for m in memory])

        if total_tokens > self._memory_size:
            summaized_memory = self._model.generate(prompt=f"""
                                                    summarize those memeories:
                                                    - summary those memories concisely
                                                    - concisely without losing any important information

                                                    ## Memories
                                                    {memory}
                                                    """)
            state["memories"] = [summaized_memory]

            self._logger.info(f"Memory exceeds limit, Summarized memory:\n{summaized_memory[:100]}")

        return state


    def pop_file_id(self, state: LinearAnalyzeAgentState):
        """
        Pop the finished file id from the list aka ids[0]
        """
        working_file_ids = state["working_file_ids"]
        state["working_file_ids"] = working_file_ids[1:]
        return state

    def setup_working_file(self, state: LinearAnalyzeAgentState):
        """
        setup the agent
        setup the chunk manager for the first file id
        get working file ids
        """
        event = state["working_event"]
        ids = self._db.get_unique_values(index=cfg.get_pre_process_index(event.id), field="id")

        self._chunk_manager = ESTextChunkManager(ids[0], "content", cfg.get_pre_process_index(event.id), self._db)

        return {
            "working_file_ids": ids
        }

def main():
    from llm_model import GeminiModel
    db = ElasticsearchDatabase()
    model = GeminiModel()
    agent = LinearAnalyzeAgent(model, db, LinearAnalyzeAgentState)

    state = {
        "working_event": Event("asdfasdfsd"),
    }

    agent.setup_working_file(state)
    result = agent.get_chunk(state)

    print(result)

if __name__ == "__main__":
    main()
