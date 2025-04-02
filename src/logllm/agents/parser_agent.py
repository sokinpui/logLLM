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
        initial_state.setdefault("log_format", "")
        initial_state.setdefault("output_csv_path", "")

        return self.graph.invoke(initial_state)

    def _build_graph(self) -> CompiledGraph:
        """Build the state graph with simplified workflow."""
        workflow = StateGraph(SimpleDrainLogParserState)

        # Define nodes
        workflow.add_node("get_log_sample", self.get_log_sample)
        workflow.add_node("generate_log_format", self.generate_log_format)
        workflow.add_node("run_drain_parser", self.run_drain_parser)

        # Define edges
        workflow.add_edge(START, "get_log_sample")
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


from typing import List
from ..utils.database import ElasticsearchDatabase
from ..config import config as cfg
from ..utils.data_struct import LogFile  # Import your LogFile class

class RecursiveDrainLogParserState(TypedDict):
    input_directory: str       # Input: Directory containing log files
    log_files: List[LogFile]   # Intermediate: List of LogFile objects
    processed_files: List[dict] # Output: List of {path: str, csv_path: str, group: str}

class RecursiveDrainLogParserAgent:
    def __init__(self, model: LLMModel, db: ElasticsearchDatabase):
        self._model = model
        self._db = db
        self._logger = Logger()
        self._simple_parser = SimpleDrainLogParserAgent(model)  # Sub-agent
        self.graph = self._build_graph()

    def run(self, initial_state: dict) -> dict:
        """Run the agent with an initial state containing the input directory."""
        if "input_directory" not in initial_state or not os.path.isdir(initial_state["input_directory"]):
            raise ValueError("Valid 'input_directory' must be provided in initial state")

        initial_state.setdefault("log_files", [])
        initial_state.setdefault("processed_files", [])

        return self.graph.invoke(initial_state)

    def _build_graph(self) -> 'CompiledGraph':
        """Build the state graph for recursive parsing."""
        workflow = StateGraph(RecursiveDrainLogParserState)

        workflow.add_node("collect_log_files", self.collect_log_files)
        workflow.add_node("parse_and_ingest", self.parse_and_ingest)

        workflow.add_edge(START, "collect_log_files")
        workflow.add_edge("collect_log_files", "parse_and_ingest")
        workflow.add_edge("parse_and_ingest", END)

        return workflow.compile()

    def collect_log_files(self, state: RecursiveDrainLogParserState) -> dict:
        """Recursively collect all .log files as LogFile objects, grouping by first subdirectory."""
        input_dir = state["input_directory"]
        self._logger.info(f"Collecting .log files from {input_dir}")

        log_files = []
        input_dir_abs = os.path.abspath(input_dir)  # Normalize input_dir

        for root, _, files in os.walk(input_dir):
            if os.path.basename(root).startswith('.'):
                continue
            # Compute the group as the first subdirectory under input_dir
            rel_path = os.path.relpath(root, input_dir_abs)  # Path relative to input_dir
            if rel_path == '.':  # If root is input_dir itself
                group = os.path.basename(input_dir_abs)  # Fallback to input_dir name
            else:
                group = rel_path.split(os.sep)[0]  # First subdirectory

            for file in files:
                if file.endswith('.log') and not file.startswith('.'):
                    file_path = os.path.abspath(os.path.join(root, file))
                    log_file = LogFile(filename=file_path, parent=group)
                    log_files.append(log_file)

        self._logger.info(f"Found {len(log_files)} .log files")
        return {"log_files": log_files}

    def parse_and_ingest(self, state: RecursiveDrainLogParserState) -> dict:
        """Parse each log file with SimpleDrainLogParserAgent and ingest into Elasticsearch."""
        log_files = state["log_files"]
        processed_files = []

        for log_file in log_files:
            group = log_file.belongs_to  # Use LogFile's parent as group
            index = cfg.get_parsed_log_storage_index(group)  # e.g., "parsed_log_hadoop"

            # Parse the file using the sub-agent
            simple_state = {"log_file_path": log_file.name}
            result = self._simple_parser.run(simple_state)
            csv_path = result["output_csv_path"]

            if csv_path:
                self._logger.info(f"Processing {log_file.name} -> {csv_path} for index {index}")
                processed_files.append({"path": log_file.name, "csv_path": csv_path, "group": group})

                # Ensure index exists
                if not self._db.instance.indices.exists(index=index):
                    self._db.instance.indices.create(index=index)

                # Ingest CSV into Elasticsearch
                try:
                    df = pd.read_csv(csv_path)
                    for record in df.to_dict(orient="records"):
                        cleaned_record = {k: (None if pd.isna(v) else v) for k, v in record.items()}
                        self._db.insert(cleaned_record, index)
                    self._logger.info(f"Ingested {len(df)} records from {csv_path} into {index}")
                except Exception as e:
                    self._logger.error(f"Failed to ingest {csv_path} into {index}: {e}")

        return {"processed_files": processed_files}

# Example usage
if __name__ == "__main__":
    from ..utils.llm_model import GeminiModel  # Adjust import based on your structure
    model = GeminiModel()  # Assumes your LLMModel implementation
    agent = SimpleDrainLogParserAgent(model)

    state = {"log_file_path": "logs/ssh/SSH.log"}
    result = agent.run(state)
    print(f"Output CSV: {result['output_csv_path']}")
