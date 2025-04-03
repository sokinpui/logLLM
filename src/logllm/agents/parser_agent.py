import os
import pandas as pd
from typing import TypedDict
from logparser.Drain import LogParser  # Import Drain
from pydantic import BaseModel, Field
from contextlib import redirect_stdout

# Relative imports for running with python -m
from ..utils.llm_model import LLMModel
from ..utils.logger import Logger
from ..utils.prompts_manager.prompts_manager import PromptsManager

class SimpleDrainLogParserState(TypedDict):
    log_file_path: str         # Input: Path to the single .log file
    log_format: str | None     # Intermediate: Generated format string for Drain
    output_csv_path: str       # Output: Path to the generated CSV file
    sample_logs: str           # Intermediate: Sampled logs for format generation

class SimpleDrainLogParserAgent:
    SAMPLE_SIZE = 50  # Number of lines to sample from the file

    def __init__(self, model: LLMModel):
        self._model = model
        self._logger = Logger()
        self.prompts_manager = PromptsManager(json_file="prompts/prompts.json")

    def run(self, initial_state: SimpleDrainLogParserState) -> SimpleDrainLogParserState:
        """
        Parse a single log file and return the result.
        Args:
            initial_state: Dict with 'log_file_path' and optional 'log_format'.
        Returns:
            Dict with 'log_format' (if generated) and 'output_csv_path'.
        """
        # Validate input
        if "log_file_path" not in initial_state or not os.path.isfile(initial_state["log_file_path"]):
            self._logger.error("Valid 'log_file_path' must be provided in initial state")
            raise ValueError("Valid 'log_file_path' must be provided in initial state")

        log_file_path = initial_state["log_file_path"]
        log_format = initial_state.get("log_format")
        result: SimpleDrainLogParserState = {
            "log_file_path": log_file_path,
            "log_format": log_format,
            "output_csv_path": "",
            "sample_logs": ""
        }

        # Step 1: Check if log format is provided; if yes, skip to parsing
        if log_format:
            self._logger.info(f"Using provided log format: {log_format}")
            return self._run_drain_parser(result)

        # Step 2: Generate log format if not provided
        log_format = self._generate_log_format(log_file_path)
        result["log_format"] = log_format

        # Step 3: Run Drain parser with the generated log format
        return self._run_drain_parser(result)

    def _generate_log_format(self, log_file_path: str) -> str:
        """
        Generate a log format for the given log file using sampled logs and LLM.
        Args:
            log_file_path: Path to the log file.
        Returns:
            Generated log format string, or empty string if generation fails.
        """
        # Sample logs
        try:
            with open(log_file_path, 'r') as f:
                lines = f.readlines()
                sample_size = min(self.SAMPLE_SIZE, len(lines))
                sample_logs = pd.Series(lines).sample(sample_size).tolist()
        except Exception as e:
            self._logger.error(f"Failed to sample {log_file_path}: {e}")
            return ""

        if not sample_logs:
            self._logger.error("No samples available to generate log format")
            return ""

        # Generate log format using LLM
        prompt = self.prompts_manager.get_prompt(sample_logs=str(sample_logs))

        class schema(BaseModel):
            log_format: str = Field(description="Output only the log format string, without any additional text or explanations.")

        try:
            response = self._model.generate(prompt, schema)
            self._logger.info(f"Generated log format: {response.log_format}")
            return response.log_format
        except Exception as e:
            self._logger.error(f"LLM failed to generate log format: {e}")
            return ""

    def _run_drain_parser(self, state: SimpleDrainLogParserState) -> SimpleDrainLogParserState:
        """Run Drain parser on the log file and save output as CSV."""
        log_file_path = state["log_file_path"]
        log_format = state["log_format"]
        result = state.copy()

        if not log_format:
            self._logger.error("No log format provided; skipping parsing")
            return result

        # Define output CSV path with prefix in same directory
        dir_name = os.path.dirname(log_file_path)
        base_name = os.path.basename(log_file_path)
        output_csv = os.path.join(dir_name, f"parsed_{base_name}_structured.csv")

        try:
            parser = LogParser(
                log_format=log_format,
                indir=os.path.dirname(log_file_path),
                outdir=os.path.dirname(log_file_path),
                depth=4,
                st=0.5,
                rex=[
                    r'blk_(|-)[0-9]+',
                    r'(/|)([0-9]+\.){3}[0-9]+(:[0-9]+|)(:|)',
                    r'(?<=[^A-Za-z0-9])(\-?\+?\d+)(?=[^A-Za-z0-9])|\b\d+\b',
                ]
            )
            with open(os.devnull, 'w') as devnull:
                with redirect_stdout(devnull):
                    parser.parse(base_name)

            # Check if output exists and rename with prefix
            temp_output = os.path.join(dir_name, f"{base_name}_structured.csv")
            if os.path.exists(temp_output):
                os.rename(temp_output, output_csv)
                result["output_csv_path"] = output_csv
            else:
                self._logger.error("Drain parsing failed; no output CSV found")
        except Exception as e:
            self._logger.error(f"Drain parsing failed for {log_file_path}: {e}")

        return result

from ..utils.database import ElasticsearchDatabase
from ..utils.logger import Logger
import sys

class GroupLogParserAgent:
    def __init__(self, model):
        self._logger = Logger()
        self._db = ElasticsearchDatabase()  # Connects to Elasticsearch via config
        self._simple_parser_agent = SimpleDrainLogParserAgent(model)

    def fetch_groups(self) -> dict | None:
        """Fetch group information from the database using scroll_search."""
        try:
            query = {"query": {"match_all": {}}}
            groups_data = self._db.scroll_search(query=query, index="group_infos")
            groups = {doc["_source"]["group"]: doc["_source"]["files"] for doc in groups_data}
            return groups
        except Exception as e:
            self._logger.error(f"Failed to fetch groups: {e}")
            return None

    def parse_all_logs(self, groups: dict) -> dict:
        """Parse all log files in the provided groups and return progress."""
        if groups is None:
            self._logger.error("No groups provided to parse")
            return {}

        progress = {group: [] for group in groups}  # Track CSV paths for each group

        # Calculate total number of files for progress bar
        total_files = sum(len(files) for files in groups.values())
        processed_files = 0

        for group, files in groups.items():
            log_format = None
            for file in files:
                # Update progress bar
                processed_files += 1
                self._update_progress_bar(processed_files, total_files)

                try:
                    # Prepare the state for SimpleDrainLogParserAgent
                    state: SimpleDrainLogParserState = {
                        "log_file_path": file,
                        "log_format": log_format,
                        "output_csv_path": "",
                        "sample_logs": ""
                    }
                    result = self._simple_parser_agent.run(state)
                    if not log_format and result["log_format"]:
                        log_format = result["log_format"]
                    if result["output_csv_path"]:
                        progress[group].append(result["output_csv_path"])
                except Exception as e:
                    self._logger.error(f"Failed to parse file {file}: {e}")
                    continue  # Skip to the next file on failure

        # Ensure progress bar reaches 100% and moves to a new line
        self._update_progress_bar(total_files, total_files, force_newline=True)
        return progress

    def _update_progress_bar(self, current: int, total: int, force_newline: bool = False):
        """Display a single-line progress bar."""
        bar_length = 50
        progress = current / total
        filled = int(bar_length * progress)
        bar = '=' * filled + '-' * (bar_length - filled)
        percentage = int(progress * 100)
        print(f"\rProgress: [{bar}] {percentage}% ({current}/{total})\n", end="", flush=True)
        if force_newline or current == total:
            print()  # Move to a new line when done

    def run(self) -> dict:
        """Run the agent to fetch and parse all log files."""
        groups = self.fetch_groups()

        if groups is None:
            self._logger.error("Cannot proceed without groups")
            return {}
        return self.parse_all_logs(groups)

# Example usage
if __name__ == "__main__":
    from ..utils.llm_model import GeminiModel
    from pprint import pprint

    model = GeminiModel()
    agent = GroupLogParserAgent(model=model)
    progress = agent.run()
    print("Processing complete. Output CSV paths:")
    for group, csv_paths in progress.items():
        print(f"Group {group}:")
        for csv_path in csv_paths:
            print(f"  {csv_path}")
