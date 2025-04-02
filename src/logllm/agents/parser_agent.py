import os
import pandas as pd
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.graph import CompiledGraph
from logparser.Drain import LogParser  # Import Drain

from pydantic import BaseModel, Field

# Relative imports for running with python -m
from ..utils.llm_model import LLMModel
from ..utils.logger import Logger
from ..utils.prompts_manager.prompts_manager import PromptsManager

class SimpleDrainLogParserState(TypedDict):
    log_file_path: str         # Input: Path to the single .log file
    log_format: str            # Intermediate: Generated format string for Drain
    output_csv_path: str       # Output: Path to the generated CSV file
    sample_logs: str

class SimpleDrainLogParserAgent:
    # Prompt key for LLM log format generation
    PROMPT_GENERATE_FORMAT = "logllm.agents.simple_drain_log_parser_agent.generate_log_format"
    SAMPLE_SIZE = 50           # Number of lines to sample from the file

    def __init__(self, model: LLMModel):
        self._model = model
        self._logger = Logger()
        self.graph = self._build_graph()

        self.prompts_manager = PromptsManager(json_file="prompts/prompts.json")

    def run(self, initial_state: dict) -> dict:
        """Run the agent with an initial state containing the log file path."""
        if "log_file_path" not in initial_state or not os.path.isfile(initial_state["log_file_path"]):
            raise ValueError("Valid 'log_file_path' must be provided in initial state")

        # Set default state values
        return self.graph.invoke(initial_state)

    def _build_graph(self) -> CompiledGraph:
        """Build the state graph for single-file parsing."""
        workflow = StateGraph(SimpleDrainLogParserState)

        workflow.add_node("get_log_sample", self.get_log_sample)
        workflow.add_node("generate_log_format", self.generate_log_format)
        workflow.add_node("run_drain_parser", self.run_drain_parser)

        workflow.add_edge(START, "get_log_sample")
        workflow.add_conditional_edges(
            START,
            self.should_generate_format,
            {"generate_log_format": "get_log_sample", "run_drain_parser": "run_drain_parser"}
        )
        workflow.add_edge("get_log_sample", "generate_log_format")
        workflow.add_edge("generate_log_format", "run_drain_parser")
        workflow.add_edge("run_drain_parser", END)

        return workflow.compile()

    def get_log_sample(self, state: SimpleDrainLogParserState) -> dict:
        """Sample random lines from the log file."""
        log_file_path = state["log_file_path"]
        self._logger.info(f"Sampling {self.SAMPLE_SIZE} lines from {log_file_path}")

        try:
            with open(log_file_path, 'r') as f:
                lines = f.readlines()
                # Simple random sampling (or take first N if file is small)
                sample_size = min(self.SAMPLE_SIZE, len(lines))
                sample_logs = pd.Series(lines).sample(sample_size).tolist()
            return {"sample_logs": str(sample_logs)}
        except Exception as e:
            self._logger.error(f"Failed to sample {log_file_path}: {e}")
            return {"sample_logs": ""}

    def should_generate_format(self, state: SimpleDrainLogParserState) -> str:
        """Check if log format generation is needed."""
        return "generate_log_format" if state["log_format"] is None else "run_drain_parser"

    def generate_log_format(self, state: SimpleDrainLogParserState) -> dict:
        """Generate log format using LLM based on sampled logs."""
        sample_logs = state["sample_logs"]
        if not sample_logs:
            self._logger.error("No samples available to generate log format")
            return {"log_format": ""}

        self._logger.info("Generating log format with LLM")
        formatted_samples = "\n".join(f"- {line.strip()}" for line in sample_logs)
        prompt = self.prompts_manager.get_prompt(sample_logs=formatted_samples)

        # TODO: use structured output from LLM
        class schema(BaseModel):
            log_format: str = Field(description="log format used for logparser.Drain")

        try:
            response = self._model.generate(prompt, schema)
            log_format = response.log_format

            self._logger.info(f"Generated log format: {log_format}")
            return {"log_format": log_format}
        except Exception as e:
            self._logger.error(f"LLM failed to generate log format: {e}")
            return {"log_format": ""}

    def run_drain_parser(self, state: SimpleDrainLogParserState) -> dict:
        """Run Drain parser on the log file and save output as CSV."""
        log_file_path = state["log_file_path"]
        log_format = state["log_format"]
        if not log_format:
            self._logger.error("No log format provided; skipping parsing")
            return {"output_csv_path": ""}

        # Define output CSV path with prefix in same directory
        dir_name = os.path.dirname(log_file_path)
        base_name = os.path.basename(log_file_path)
        output_csv = os.path.join(dir_name, f"parsed_{base_name}_structured.csv")

        self._logger.info(f"Parsing {log_file_path} with Drain")
        try:
            parser = LogParser(
                log_format=log_format,
                indir=os.path.dirname(log_file_path),  # Input directory
                outdir=os.path.dirname(log_file_path), # Output in same directory
                depth=4,                               # Drain tree depth
                st=0.5,                                # Similarity threshold
                rex=[                                  # Regex for variable parts
                    r'blk_(|-)[0-9]+',
                    r'(/|)([0-9]+\.){3}[0-9]+(:[0-9]+|)(:|)',
                    r'(?<=[^A-Za-z0-9])(\-?\+?\d+)(?=[^A-Za-z0-9])|\b\d+\b',
                ]
            )
            parser.parse(base_name)  # Parse the specific file

            # Check if output exists and rename with prefix
            temp_output = os.path.join(dir_name, f"{base_name}_structured.csv")
            if os.path.exists(temp_output):
                os.rename(temp_output, output_csv)
                self._logger.info(f"Generated CSV at {output_csv}")
                return {"output_csv_path": output_csv}
            else:
                self._logger.error("Drain parsing failed; no output CSV found")
                return {"output_csv_path": ""}
        except Exception as e:
            self._logger.error(f"Drain parsing failed for {log_file_path}: {e}")
            return {"output_csv_path": ""}

from langgraph.graph import StateGraph, START, END
from ..utils.database import ElasticsearchDatabase

from typing import List, Dict, Optional

class GroupLogParserState(TypedDict):
    groups: Dict[str, List[str]]       # Group name -> List of file paths
    current_group: Optional[str]       # Current group being processed
    current_file: Optional[str]        # Current file being processed
    log_format: Optional[str]          # Log format for the current group
    progress: Dict[str, List[str]]     # Group name -> List of generated CSV paths

class GroupLogParserAgent:
    def __init__(self, model, es_host: str = "localhost:9200"):
        self._logger = Logger()
        self._db = ElasticsearchDatabase()  # Connects to Elasticsearch via config
        self._simple_parser_agent = SimpleDrainLogParserAgent(model)
        self.graph = self._build_graph()

    def run(self, initial_state: dict) -> dict:
        """Run the agent to process all log files in groups."""
        return self.graph.invoke(initial_state)

    def _build_graph(self) -> CompiledGraph:
        """Build the state graph for processing all log files in groups."""
        workflow = StateGraph(GroupLogParserState)

        # Add nodes
        workflow.add_node("fetch_groups", self.fetch_groups)
        workflow.add_node("select_next_group", self.select_next_group)
        workflow.add_node("select_next_file", self.select_next_file)
        workflow.add_node("parse_file", self.parse_file)

        # Add edges
        workflow.add_edge(START, "fetch_groups")
        workflow.add_edge("fetch_groups", "select_next_group")
        workflow.add_edge("select_next_group", "select_next_file")
        workflow.add_conditional_edges(
            "select_next_file",
            self.should_parse_file,
            {
                "parse_file": "parse_file",
                "select_next_group": "select_next_group",
                "end": END
            }
        )
        workflow.add_edge("parse_file", "select_next_file")

        return workflow.compile()

    def fetch_groups(self, state: GroupLogParserState) -> dict:
        """Fetch group information from the database using scroll_search."""
        self._logger.info("Fetching group information from the database using scroll_search")
        try:
            query = {"query": {"match_all": {}}}
            groups_data = self._db.scroll_search(query=query, index="group_infos")
            groups = {doc["_source"]["group"]: doc["_source"]["files"] for doc in groups_data}
            self._logger.info(f"Found groups: {list(groups.keys())}")
            return {
                "groups": groups,
                "progress": {group: [] for group in groups},
                "current_group": None,
                "current_file": None,
                "log_format": None
            }
        except Exception as e:
            self._logger.error(f"Failed to fetch groups: {e}")
            return {
                "groups": {},
                "progress": {},
                "current_group": None,
                "current_file": None,
                "log_format": None
            }

    def select_next_group(self, state: GroupLogParserState) -> dict:
        """Select the next group with unprocessed files and reset log_format."""
        groups = state["groups"]
        progress = state["progress"]
        remaining_groups = [g for g in groups if len(progress[g]) < len(groups[g])]
        if not remaining_groups:
            self._logger.info("All groups processed")
            return {"current_group": None, "log_format": None}
        current_group = remaining_groups[0]  # Take the first available group
        self._logger.info(f"Selected next group: {current_group}")
        return {"current_group": current_group, "log_format": None}

    def select_next_file(self, state: GroupLogParserState) -> dict:
        """Select the next unprocessed file in the current group."""
        current_group = state["current_group"]
        if current_group is None:
            return {"current_file": None}
        group_files = state["groups"][current_group]
        parsed_count = len(state["progress"][current_group])
        if parsed_count < len(group_files):
            current_file = group_files[parsed_count]
            self._logger.info(f"Selected next file: {current_file} in group {current_group}")
            return {"current_file": current_file}
        return {"current_file": None}

    def parse_file(self, state: GroupLogParserState) -> dict:
        """Parse the current file using the SimpleDrainLogParserAgent subgraph."""
        current_group = state["current_group"]
        current_file = state["current_file"]
        log_format = state["log_format"]
        progress = state["progress"].copy()

        is_first_file = len(progress[current_group]) == 0
        subgraph_state = {
            "log_file_path": current_file,
            "log_format": None if is_first_file else log_format,
            "output_csv_path": "",
            "sample_logs": ""
        }

        self._logger.info(f"Invoking subgraph to parse file: {current_file} with log_format: {log_format}")
        try:
            result = self._simple_parser_agent.run(subgraph_state)
        except Exception as e:
            self._logger.error(f"Failed to parse file {current_file}: {e}")
            return {}

        if is_first_file and result["log_format"]:
            log_format = result["log_format"]
            self._logger.info(f"Generated log format for group {current_group}: {log_format}")

        if result["output_csv_path"]:
            progress[current_group].append(result["output_csv_path"])
            self._logger.info(f"Generated CSV for {current_file}: {result['output_csv_path']}")

        return {"log_format": log_format, "progress": progress}

    def should_parse_file(self, state: GroupLogParserState) -> str:
        """Determine the next step after selecting a file."""
        if state["current_file"] is not None:
            return "parse_file"
        elif state["current_group"] is not None:
            return "select_next_group"
        else:
            return "end"

# Example usage
if __name__ == "__main__":
    from src.logllm.utils.llm_model import GeminiModel

    model = GeminiModel()
    agent = GroupLogParserAgent(model=model)

    initial_state = {
        "groups": {},
        "current_group": None,
        "current_file": None,
        "log_format": None,
        "progress": {}
    }

    result = agent.run(initial_state)
    print("Processing complete. Output CSV paths:")
    for group, csv_paths in result["progress"].items():
        print(f"Group {group}:")
        for csv_path in csv_paths:
            print(f"  {csv_path}")
