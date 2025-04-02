# src/logllm/agents/drain_log_parser_agent.py

import os
import shutil
import pandas as pd
from typing import TypedDict, List, Annotated, Optional
from pydantic import BaseModel, Field as PydanticField
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from elasticsearch import helpers
from logparser.Drain import LogParser # Import Drain

# Use relative imports because we run with python -m
from ..utils.llm_model import LLMModel
from ..utils.database import ElasticsearchDatabase
from ..utils.prompts_manager.prompts_manager import PromptsManager
from ..utils.logger import Logger
from ..config import config as cfg
from .agent_abc import Agent, add_string_message # Assuming agent_abc.py is in the same directory


# Pydantic schema for the LLM output (even though we expect just a string,
# using a schema can help enforce structure if needed later, or catch errors)
class LogFormatSchema(BaseModel):
    log_format: str = PydanticField(description="The generated log format string for Drain.")

# Agent State Definition
class DrainLogParserAgentState(TypedDict):
    input_directory: str              # Input: The single directory containing logs to parse.
    log_group: Optional[str]          # Derived from input_directory. Used for index naming.
    sample_logs: List[str]            # Intermediate: Sample raw log lines for LLM.
    log_format: Optional[str]         # Intermediate: Generated format string for Drain.
    parsed_files_info: List[dict]     # Intermediate: List of dicts {'original_path': str, 'structured_csv_path': str}
    target_index: Optional[str]       # Output: ES index name for parsed logs.
    processed_files_count: int        # Output: Number of files successfully parsed by Drain.
    inserted_lines_count: int         # Output: Total lines inserted into ES.
    error_messages: Annotated[List[str], add_string_message] # Output: Errors encountered.

class DrainLogParserAgent(Agent):
    PROMPT_GENERATE_FORMAT = "logllm.agents.drain_log_parser_agent.generate_log_format"
    TEMP_DRAIN_OUTPUT_DIR = "./drain_temp_output/" # Temporary dir for Drain CSVs

    def __init__(self, model: LLMModel, db: ElasticsearchDatabase, prompts_manager: PromptsManager):
        self._model = model
        self._db = db
        self._prompts_manager = prompts_manager
        self._logger = Logger()
        self.graph = self._build_graph(DrainLogParserAgentState)

    def run(self, initial_state: dict) -> dict:
        if "input_directory" not in initial_state or not isinstance(initial_state["input_directory"], str):
             raise ValueError("Missing or invalid 'input_directory' (string) in initial state for DrainLogParserAgent")

        initial_state.setdefault("log_group", None)
        initial_state.setdefault("sample_logs", [])
        initial_state.setdefault("log_format", None)
        initial_state.setdefault("parsed_files_info", [])
        initial_state.setdefault("target_index", None)
        initial_state.setdefault("processed_files_count", 0)
        initial_state.setdefault("inserted_lines_count", 0)
        initial_state.setdefault("error_messages", [])

        # Clean up temp dir before starting, just in case
        if os.path.exists(self.TEMP_DRAIN_OUTPUT_DIR):
             shutil.rmtree(self.TEMP_DRAIN_OUTPUT_DIR)

        final_state = self.graph.invoke(initial_state)

        # Clean up temp dir after finishing
        if os.path.exists(self.TEMP_DRAIN_OUTPUT_DIR):
             shutil.rmtree(self.TEMP_DRAIN_OUTPUT_DIR)
        self._logger.info(f"Cleaned up temporary directory: {self.TEMP_DRAIN_OUTPUT_DIR}")

        return final_state

    async def arun(self, initial_state: dict) -> dict:
        # Async run follows the same logic for setup and cleanup
        if "input_directory" not in initial_state or not isinstance(initial_state["input_directory"], str):
             raise ValueError("Missing or invalid 'input_directory' (string) in initial state for DrainLogParserAgent")

        initial_state.setdefault("log_group", None)
        initial_state.setdefault("sample_logs", [])
        initial_state.setdefault("log_format", None)
        initial_state.setdefault("parsed_files_info", [])
        initial_state.setdefault("target_index", None)
        initial_state.setdefault("processed_files_count", 0)
        initial_state.setdefault("inserted_lines_count", 0)
        initial_state.setdefault("error_messages", [])

        if os.path.exists(self.TEMP_DRAIN_OUTPUT_DIR):
             shutil.rmtree(self.TEMP_DRAIN_OUTPUT_DIR)

        final_state = await self.graph.ainvoke(initial_state)

        if os.path.exists(self.TEMP_DRAIN_OUTPUT_DIR):
             shutil.rmtree(self.TEMP_DRAIN_OUTPUT_DIR)
        self._logger.info(f"Cleaned up temporary directory: {self.TEMP_DRAIN_OUTPUT_DIR}")

        return final_state

    def _build_graph(self, typed_state) -> CompiledStateGraph:
        workflow = StateGraph(typed_state)

        # Define Nodes
        workflow.add_node("validate_input_and_setup", self.validate_input_and_setup)
        workflow.add_node("get_log_sample", self.get_log_sample)
        workflow.add_node("generate_log_format", self.generate_log_format)
        workflow.add_node("run_drain_parser", self.run_drain_parser)
        workflow.add_node("ingest_parsed_logs", self.ingest_parsed_logs)

        # Define Edges
        workflow.add_edge(START, "validate_input_and_setup")
        workflow.add_conditional_edges(
            "validate_input_and_setup",
            lambda state: "get_log_sample" if state.get("log_group") else END, # Proceed only if setup was successful
            {"get_log_sample": "get_log_sample", END: END}
        )
        workflow.add_edge("get_log_sample", "generate_log_format")
        workflow.add_conditional_edges(
            "generate_log_format",
             lambda state: "run_drain_parser" if state.get("log_format") else END, # Proceed only if format was generated
             {"run_drain_parser": "run_drain_parser", END: END}
        )
        workflow.add_edge("run_drain_parser", "ingest_parsed_logs")
        workflow.add_edge("ingest_parsed_logs", END)

        return workflow.compile()

    # --- Node Implementations ---

    def validate_input_and_setup(self, state: DrainLogParserAgentState) -> dict:
        """
        Validates the input directory, extracts the log group name,
        and determines the target Elasticsearch index name.
        """
        input_dir = state["input_directory"]
        self._logger.info(f"DrainParserAgent: Validating input directory: {input_dir}")

        if not os.path.isdir(input_dir):
            error_msg = f"Input directory does not exist or is not a directory: {input_dir}"
            self._logger.error(error_msg)
            return {"error_messages": error_msg, "log_group": None} # Signal failure

        # Check if directory is empty (ignoring hidden files)
        if not any(f for f in os.listdir(input_dir) if not f.startswith('.')):
             error_msg = f"Input directory is empty: {input_dir}"
             self._logger.warning(error_msg)
             # Decide if empty dir is an error or just means no work - treating as no work
             return {"error_messages": error_msg, "log_group": None}

        # Derive log group name from the last part of the directory path
        log_group = os.path.basename(os.path.normpath(input_dir))
        if not log_group: # Handle cases like '/' or '.'
             error_msg = f"Could not derive a valid log group name from directory: {input_dir}"
             self._logger.error(error_msg)
             return {"error_messages": error_msg, "log_group": None}

        target_index = cfg.get_parsed_log_storage_index(log_group)
        self._logger.info(f"DrainParserAgent: Setup complete. Log Group: '{log_group}', Target Index: '{target_index}'")

        return {"log_group": log_group, "target_index": target_index}

    def get_log_sample(self, state: DrainLogParserAgentState) -> dict:
        """Fetches random log samples from the original log index."""
        log_group = state["log_group"]
        # Assuming raw logs are stored in index like 'log_ssh_logs'
        source_index = cfg.get_log_stroage_index(log_group)
        sample_size = 50 # Or make configurable
        self._logger.info(f"DrainParserAgent: Getting {sample_size} samples from raw log index '{source_index}'")

        try:
            if not self._db.instance.indices.exists(index=source_index):
                 error_msg = f"Source raw log index '{source_index}' does not exist."
                 self._logger.error(error_msg)
                 return {"error_messages": error_msg, "sample_logs": []} # Allow graph to continue, but format gen will fail

            samples_hits = self._db.random_sample(source_index, sample_size)
            # Ensure 'content' field exists in source documents
            sample_logs = [hit['_source']['content'] for hit in samples_hits if 'content' in hit.get('_source', {})]

            if not sample_logs:
                error_msg = f"No logs with 'content' field found in index '{source_index}' to sample."
                self._logger.warning(error_msg)
                return {"error_messages": error_msg, "sample_logs": []}

            self._logger.info(f"DrainParserAgent: Retrieved {len(sample_logs)} samples.")
            return {"sample_logs": sample_logs}

        except Exception as e:
            error_msg = f"Error getting log samples from {source_index}: {e}"
            self._logger.error(error_msg, exc_info=True)
            return {"error_messages": error_msg, "sample_logs": []}

    def generate_log_format(self, state: DrainLogParserAgentState) -> dict:
        """Generates the log format string using LLM based on samples."""
        sample_logs = state["sample_logs"]
        if not sample_logs:
             error_msg = "DrainParserAgent: No sample logs provided to generate log format."
             self._logger.error(error_msg)
             return {"error_messages": error_msg, "log_format": None} # Signal failure

        self._logger.info("DrainParserAgent: Generating log format using LLM...")
        try:
            prompt_template = self._prompts_manager.get_prompt(metadata=self.PROMPT_GENERATE_FORMAT)
            formatted_samples = "\n".join(f"- {line.strip()}" for line in sample_logs)
            prompt = prompt_template.format(sample_logs=formatted_samples)

            # We expect just the format string directly based on the prompt
            generated_format = self._model.generate(prompt) # No schema needed if prompt asks for only the string

            if isinstance(generated_format, str) and generated_format.strip():
                 log_format = generated_format.strip()
                 self._logger.info(f"DrainParserAgent: Successfully generated log format: '{log_format}'")
                 return {"log_format": log_format}
            else:
                 error_msg = f"LLM failed to generate a valid log format string. Output: {generated_format}"
                 self._logger.error(error_msg)
                 return {"error_messages": error_msg, "log_format": None}

        except (KeyError, ValueError) as e:
             error_msg = f"Error retrieving/formatting prompt '{self.PROMPT_GENERATE_FORMAT}': {e}"
             self._logger.error(error_msg)
             return {"error_messages": error_msg, "log_format": None}
        except Exception as e:
            error_msg = f"Error during LLM format generation: {e}"
            self._logger.error(error_msg, exc_info=True)
            return {"error_messages": error_msg, "log_format": None}

    def run_drain_parser(self, state: DrainLogParserAgentState) -> dict:
        """Runs the Drain parser on all .log files in the input directory."""
        input_dir = state["input_directory"]
        log_format = state["log_format"]
        log_files_to_parse = [f for f in os.listdir(input_dir) if f.endswith(".log")] # Simple filter

        if not log_files_to_parse:
            msg = f"DrainParserAgent: No '.log' files found in {input_dir}. Skipping parsing."
            self._logger.warning(msg)
            return {"error_messages": msg, "processed_files_count": 0, "parsed_files_info": []}

        # Prepare Drain's output directory
        os.makedirs(self.TEMP_DRAIN_OUTPUT_DIR, exist_ok=True)
        self._logger.info(f"DrainParserAgent: Using temporary output directory: {self.TEMP_DRAIN_OUTPUT_DIR}")

        processed_count = 0
        parsed_files_info = []
        errors = []

        # Drain parameters (can be made configurable)
        drain_depth = 4
        drain_st = 0.5
        drain_rex = [
            r'blk_(|-)[0-9]+',
            r'(/|)([0-9]+\.){3}[0-9]+(:[0-9]+|)(:|)',
            r'(?<=[^A-Za-z0-9])(\-?\+?\d+)(?=[^A-Za-z0-9])|\b\d+\b',
        ]

        self._logger.info(f"DrainParserAgent: Parsing {len(log_files_to_parse)} file(s) using format: '{log_format}'")

        for log_filename in log_files_to_parse:
            original_log_path = os.path.join(input_dir, log_filename)
            self._logger.info(f"DrainParserAgent: Parsing '{log_filename}'...")
            try:
                parser = LogParser(
                    log_format=log_format,
                    indir=input_dir, # Drain reads the file from here
                    outdir=self.TEMP_DRAIN_OUTPUT_DIR, # Drain writes results here
                    depth=drain_depth,
                    st=drain_st,
                    rex=drain_rex
                )
                parser.parse(log_filename) # Tell Drain which file in 'indir' to parse

                # Construct expected output paths
                structured_csv_path = os.path.join(self.TEMP_DRAIN_OUTPUT_DIR, f"{log_filename}_structured.csv")
                # templates_csv_path = os.path.join(self.TEMP_DRAIN_OUTPUT_DIR, f"{log_filename}_templates.csv") # We might not need templates

                if os.path.exists(structured_csv_path):
                     processed_count += 1
                     parsed_files_info.append({
                         'original_path': original_log_path,
                         'structured_csv_path': structured_csv_path
                     })
                     self._logger.info(f"DrainParserAgent: Successfully parsed '{log_filename}'. Output: {structured_csv_path}")
                else:
                     msg = f"Drain parsing finished for '{log_filename}' but structured output CSV not found at expected location: {structured_csv_path}"
                     self._logger.error(msg)
                     errors.append(msg)

            except Exception as e:
                msg = f"Error running Drain parser on file '{log_filename}': {e}"
                self._logger.error(msg, exc_info=True)
                errors.append(msg)

        return {
            "processed_files_count": processed_count,
            "parsed_files_info": parsed_files_info,
            "error_messages": errors # Add parsing errors
        }

    def ingest_parsed_logs(self, state: DrainLogParserAgentState) -> dict:
        """Reads parsed CSVs and bulk inserts data into Elasticsearch."""
        parsed_files_info = state["parsed_files_info"]
        target_index = state["target_index"]

        if not parsed_files_info:
            msg = "DrainParserAgent: No successfully parsed files to ingest."
            self._logger.warning(msg)
            return {"error_messages": msg, "inserted_lines_count": 0}

        if not target_index:
            msg = "DrainParserAgent: Target index not set. Cannot ingest data."
            self._logger.error(msg)
            return {"error_messages": msg, "inserted_lines_count": 0}

        self._logger.info(f"DrainParserAgent: Ingesting data from {len(parsed_files_info)} parsed file(s) into index '{target_index}'")

        # Ensure target index exists (create if not) - consider adding mappings later
        try:
            if not self._db.instance.indices.exists(index=target_index):
                 self._db.instance.indices.create(index=target_index)
                 self._logger.info(f"Created target index: {target_index}")
        except Exception as e:
            error_msg = f"Error ensuring target index '{target_index}' exists: {e}"
            self._logger.error(error_msg, exc_info=True)
            return {"error_messages": error_msg}

        total_inserted_count = 0
        bulk_errors = []
        batch_size = 1000 # ES Bulk batch size

        for file_info in parsed_files_info:
            csv_path = file_info['structured_csv_path']
            self._logger.debug(f"Processing CSV: {csv_path}")
            try:
                df = pd.read_csv(csv_path, low_memory=False) # low_memory=False can help with mixed types
                # Drain typically adds LineId, remove if not needed or rename
                # df = df.rename(columns={"LineId": "OriginalLineId"}) # Example rename

                # Convert DataFrame rows to dictionaries for ES bulk ingestion
                # Handle potential NaN values which ES doesn't like
                actions = []
                for record in df.to_dict(orient='records'):
                    # Clean NaN/NaT values - replace with None or appropriate default
                    cleaned_record = {k: (None if pd.isna(v) else v) for k, v in record.items()}
                    # Add reference to original file if desired
                    cleaned_record['_original_log_file'] = file_info['original_path']
                    action = {
                        "_index": target_index,
                        "_source": cleaned_record
                    }
                    actions.append(action)

                    # Bulk insert when batch is full
                    if len(actions) >= batch_size:
                        try:
                            success_count, _ = helpers.bulk(self._db.instance, actions, raise_on_error=False, raise_on_exception=False)
                            total_inserted_count += success_count
                            self._logger.debug(f"Bulk inserted {success_count} records from {os.path.basename(csv_path)}.")
                            actions = [] # Clear batch
                        except helpers.BulkIndexError as bulk_error:
                            msg = f"Bulk insert error processing {os.path.basename(csv_path)} (partial failure possible): {bulk_error}"
                            self._logger.error(msg)
                            bulk_errors.append(msg)
                            actions = [] # Clear batch even on error


                # Insert any remaining actions for the current file
                if actions:
                     try:
                        success_count, _ = helpers.bulk(self._db.instance, actions, raise_on_error=False, raise_on_exception=False)
                        total_inserted_count += success_count
                        self._logger.debug(f"Bulk inserted final {success_count} records from {os.path.basename(csv_path)}.")
                     except helpers.BulkIndexError as bulk_error:
                          msg = f"Final bulk insert error for {os.path.basename(csv_path)}: {bulk_error}"
                          self._logger.error(msg)
                          bulk_errors.append(msg)

                self._logger.info(f"Finished processing CSV: {csv_path}")
                # Optionally delete the CSV after successful processing
                # try:
                #     os.remove(csv_path)
                #     self._logger.debug(f"Removed processed CSV: {csv_path}")
                # except OSError as e:
                #     self._logger.warning(f"Could not remove CSV {csv_path}: {e}")

            except FileNotFoundError:
                 msg = f"Parsed CSV file not found during ingestion: {csv_path}"
                 self._logger.error(msg)
                 bulk_errors.append(msg)
            except pd.errors.EmptyDataError:
                 msg = f"Parsed CSV file is empty: {csv_path}"
                 self._logger.warning(msg)
                 # Optionally delete empty file?
            except Exception as e:
                msg = f"Error processing or ingesting data from CSV '{csv_path}': {e}"
                self._logger.error(msg, exc_info=True)
                bulk_errors.append(msg)

        self._logger.info(f"DrainParserAgent: Ingestion complete. Total lines inserted: {total_inserted_count}")
        return {
            "inserted_lines_count": total_inserted_count,
            "error_messages": bulk_errors # Add ingestion errors
        }
