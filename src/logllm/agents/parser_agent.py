# parser_agent.py

import os
import pandas as pd
from typing import TypedDict, Dict, List, Optional # Added Optional, List, Dict
from logparser.Drain import LogParser
from pydantic import BaseModel, Field
from contextlib import redirect_stdout
import sys # Keep sys for progress bar flushing

# Relative imports
from ..utils.llm_model import LLMModel
from ..utils.logger import Logger
from ..utils.prompts_manager.prompts_manager import PromptsManager
from ..utils.database import ElasticsearchDatabase
# Assuming config is accessible as cfg
from ..config import config as cfg


# --- SimpleDrainLogParserState and Agent (Keep as is, including rex refinement suggestion) ---
class SimpleDrainLogParserState(TypedDict):
    log_file_path: str
    log_format: Optional[str] # Use Optional typing
    output_csv_path: str
    sample_logs: str

class SimpleDrainLogParserAgent:
    SAMPLE_SIZE = 50

    def __init__(self, model: LLMModel):
        self._model = model
        self._logger = Logger()
        # Ensure the path to prompts.json is correct relative to execution context
        self.prompts_manager = PromptsManager(json_file="prompts/prompts.json") # Adjust path if needed

    def run(self, initial_state: SimpleDrainLogParserState) -> SimpleDrainLogParserState:
        if "log_file_path" not in initial_state or not os.path.isfile(initial_state["log_file_path"]):
            self._logger.error("Valid 'log_file_path' must be provided in initial state")
            raise ValueError("Valid 'log_file_path' must be provided in initial state")

        log_file_path = initial_state["log_file_path"]
        log_format = initial_state.get("log_format") # Use .get for optional format
        result: SimpleDrainLogParserState = {
            "log_file_path": log_file_path,
            "log_format": log_format,
            "output_csv_path": "",
            "sample_logs": ""
        }

        # Use provided format or generate a new one
        if not log_format:
            self._logger.info(f"No format provided for {os.path.basename(log_file_path)}, generating...")
            log_format = self._generate_log_format(log_file_path)
            result["log_format"] = log_format # Store generated format
            if not log_format:
                 self._logger.warning(f"Failed to generate log format for {os.path.basename(log_file_path)}. Skipping parsing.")
                 return result # Cannot parse without a format

        # Run Drain parser
        return self._run_drain_parser(result) # Pass result which now includes log_format

    def _generate_log_format(self, log_file_path: str) -> Optional[str]: # Return Optional[str]
        # Sample logs
        try:
            with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f: # Added encoding/errors
                lines = f.readlines()
                if not lines:
                    self._logger.warning(f"Log file is empty: {log_file_path}")
                    return None
                sample_size = min(self.SAMPLE_SIZE, len(lines))
                # Ensure sample_size isn't 0 if len(lines) < SAMPLE_SIZE
                if sample_size > 0:
                     sample_logs = pd.Series(lines).sample(sample_size).tolist()
                else:
                     self._logger.warning(f"Cannot sample from file with {len(lines)} lines: {log_file_path}")
                     return None

        except Exception as e:
            self._logger.error(f"Failed to sample {log_file_path}: {e}", exc_info=True)
            return None

        if not sample_logs:
            self._logger.error(f"No samples generated for {log_file_path}")
            return None

        # Generate log format using LLM
        try:
            # Make sure the prompt exists and the key is correct
            prompt_key = "_generate_log_format" # Or whatever key you use in prompts.json
            prompt = self.prompts_manager.get_prompt(prompt_key=prompt_key, sample_logs=str(sample_logs))
            if not prompt:
                 self._logger.error(f"Prompt '{prompt_key}' not found or failed to format.")
                 return None

            class LogFormatSchema(BaseModel): # Renamed schema class
                log_format: str = Field(description="Output only the log format string, without any additional text or explanations.")

            response = self._model.generate(prompt, LogFormatSchema) # Use renamed schema
            if response and isinstance(response, LogFormatSchema) and response.log_format:
                generated_format = response.log_format.strip()
                # Basic validation: Check for at least one <tag>
                if "<" in generated_format and ">" in generated_format:
                    self._logger.info(f"Generated log format for {os.path.basename(log_file_path)}: {generated_format}")
                    return generated_format
                else:
                    self._logger.warning(f"LLM returned invalid format: '{generated_format}' for {os.path.basename(log_file_path)}")
                    return None
            else:
                 self._logger.error(f"LLM did not return expected schema object or format for {os.path.basename(log_file_path)}. Response: {response}")
                 return None
        except Exception as e:
            self._logger.error(f"LLM failed to generate log format for {os.path.basename(log_file_path)}: {e}", exc_info=True)
            return None

    def _run_drain_parser(self, state: SimpleDrainLogParserState) -> SimpleDrainLogParserState:
        log_file_path = state["log_file_path"]
        log_format = state["log_format"] # Already checked if None in run method
        result = state.copy()

        # Define output CSV path
        dir_name = os.path.dirname(log_file_path)
        base_name = os.path.basename(log_file_path)
        # Use the configured function for naming consistency if desired, otherwise keep simple prefix
        # output_csv = cfg.get_parsed_log_storage_index(base_name) + ".csv" # Example if using config func
        output_csv = os.path.join(dir_name, f"parsed_{base_name}_structured.csv") # Original approach

        try:
            # --- Consider adding more specific regexes here ---
            parser = LogParser(
                log_format=log_format,
                indir=dir_name,
                outdir=dir_name, # Drain outputs to outdir
                depth=4,       # Max depth of log template tree
                st=0.5,        # Similarity threshold
                rex=[
                    # --- Add more specific regexes here ---
                    r'application_\d+_\d+',
                    r'container_\d+_\d+_\d+_\d+',
                    r'job_\d+_\d+',
                    r'(?:[a-zA-Z0-9-]+\.)+[a-zA-Z_][a-zA-Z0-9_]+', # Java Class Names
                    r'blk_(|-)[0-9]+', # Block IDs
                    r'(/|)([0-9]+\.){3}[0-9]+(:[0-9]+|)(:|)', # IP addresses
                    # Generic numbers (keep towards end)
                    r'(?<=[^A-Za-z0-9])(\-?\+?\d+)(?=[^A-Za-z0-9])|\b\d+\b',
                ]
            )
            self._logger.info(f"Running Drain on {base_name} with format: {log_format}")
            # Drain tries to parse the file matching base_name within indir
            # Suppress Drain's own stdout logging
            with open(os.devnull, 'w') as devnull:
                with redirect_stdout(devnull):
                     # Check if file exists before parsing
                     if os.path.exists(os.path.join(dir_name, base_name)):
                          parser.parse(base_name)
                     else:
                          self._logger.error(f"Input file not found for Drain: {os.path.join(dir_name, base_name)}")
                          return result # Cannot parse if file is missing

            # Drain creates file named like "original_filename_structured.csv"
            temp_output = os.path.join(dir_name, f"{base_name}_structured.csv")

            if os.path.exists(temp_output):
                # Rename to include "parsed_" prefix
                final_output_path = os.path.join(dir_name, f"parsed_{base_name}_structured.csv")
                try:
                    # If the final path already exists, remove it before renaming
                    if os.path.exists(final_output_path):
                         os.remove(final_output_path)
                    os.rename(temp_output, final_output_path)
                    result["output_csv_path"] = final_output_path
                    self._logger.info(f"Successfully parsed {base_name} -> {os.path.basename(final_output_path)}")
                except OSError as rename_error:
                     self._logger.error(f"Failed to rename Drain output {temp_output} to {final_output_path}: {rename_error}")
                     # Keep temp output path if rename fails? Or None?
                     result["output_csv_path"] = temp_output # Keep temp path maybe

            else:
                # This case might be hit if Drain fails internally without an exception we caught
                self._logger.warning(f"Drain parsing completed but no output CSV found: {temp_output}")

        except Exception as e:
            # Catch specific Drain errors if possible, otherwise generic Exception
            self._logger.error(f"Drain parsing failed for {base_name} with format '{log_format}'. Error: {e}", exc_info=True) # Log traceback
            result["output_csv_path"] = "" # Ensure path is empty on failure

        return result


class GroupLogParserAgent:
    def __init__(self, model: LLMModel): # Pass LLMModel type hint
        self._logger = Logger()
        self._db = ElasticsearchDatabase()
        self._simple_parser_agent = SimpleDrainLogParserAgent(model)

    def fetch_groups(self) -> Optional[Dict[str, List[str]]]: # Return Optional Dict
        """Fetch group information from the database using scroll_search."""
        try:
            query = {"query": {"match_all": {}}}
            # Ensure the index name matches your config/collector
            groups_index = cfg.INDEX_GROUP_INFOS
            self._logger.info(f"Fetching groups from index: {groups_index}")
            groups_data = self._db.scroll_search(query=query, index=groups_index)

            if not groups_data:
                 self._logger.warning(f"No group information found in index '{groups_index}'.")
                 return None

            groups = {doc["_source"]["group"]: doc["_source"]["files"] for doc in groups_data}
            self._logger.info(f"Fetched {len(groups)} groups.")
            return groups
        except Exception as e:
            self._logger.error(f"Failed to fetch groups from index '{groups_index}': {e}", exc_info=True)
            return None

    def parse_all_logs(self, groups: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """Parse all log files in the provided groups and return progress."""
        # groups should not be None here based on run() logic, but check anyway
        if not groups:
            self._logger.error("No groups provided to parse")
            return {}

        progress: Dict[str, List[str]] = {group: [] for group in groups}
        total_files = sum(len(files) for files in groups.values())
        processed_files = 0

        if total_files == 0:
            self._logger.warning("No log files found within the fetched groups.")
            return progress

        self._logger.info(f"Starting parsing for {total_files} files across {len(groups)} groups.")

        for group, files in groups.items():
            self._logger.info(f"Processing group: '{group}' with {len(files)} files.")
            # Determine log format once per group (based on the first file)
            group_log_format: Optional[str] = None
            first_file_parsed = False

            for file_path in files:
                # Update progress bar before processing
                processed_files += 1
                # Pass filename to progress bar function
                self._update_progress_bar(processed_files, total_files, current_file=os.path.basename(file_path))

                # Check if file exists before attempting to parse
                if not os.path.isfile(file_path):
                    self._logger.warning(f"Skipping missing file: {file_path}")
                    continue

                current_format_to_use = group_log_format # Use group format if already determined

                # --- Robust Parsing Attempt ---
                try:
                    # Prepare state
                    state: SimpleDrainLogParserState = {
                        "log_file_path": file_path,
                        "log_format": current_format_to_use, # Pass None if first file, or group format
                        "output_csv_path": "",
                        "sample_logs": "" # Sample logs generated inside agent if format is None
                    }

                    # Run the simple parser
                    result = self._simple_parser_agent.run(state)

                    # If this was the first file attempt for the group, store the determined format
                    if not first_file_parsed and result.get("log_format"):
                        group_log_format = result["log_format"]
                        self._logger.info(f"Determined format for group '{group}': {group_log_format}")
                        first_file_parsed = True # Mark that we have tried to get/use a group format

                    # Check if parsing was successful (output path exists)
                    if result.get("output_csv_path"):
                        progress[group].append(result["output_csv_path"])
                    else:
                         # Parsing failed even with the determined format (or format generation failed)
                         self._logger.warning(f"Parsing ultimately failed for {os.path.basename(file_path)} in group '{group}'. Check previous logs for details.")
                         # --- Optional Fallback: Try File-Specific Format ---
                         # Uncomment below to try regenerating format specifically for this file
                         # self._logger.info(f"Attempting fallback: Generate format specifically for {os.path.basename(file_path)}")
                         # fallback_state: SimpleDrainLogParserState = { "log_file_path": file_path, "log_format": None, "output_csv_path": "", "sample_logs": ""}
                         # fallback_result = self._simple_parser_agent.run(fallback_state)
                         # if fallback_result.get("output_csv_path"):
                         #     self._logger.info(f"Fallback parsing successful for {os.path.basename(file_path)}")
                         #     progress[group].append(fallback_result["output_csv_path"])
                         # else:
                         #     self._logger.error(f"Fallback parsing also failed for {os.path.basename(file_path)}")
                         # --- End Optional Fallback ---


                except Exception as e:
                    # Catch unexpected errors during the agent run itself
                    self._logger.error(f"Agent run failed unexpectedly for file {os.path.basename(file_path)}: {e}", exc_info=True)
                    continue # Skip to the next file

        # Ensure progress bar finishes cleanly
        self._update_progress_bar(total_files, total_files, force_newline=True)
        return progress

    def _update_progress_bar(self, current: int, total: int, current_file: str = "", force_newline: bool = False):
        """Display a single-line progress bar, showing the current file."""
        bar_length = 40 # Slightly shorter bar
        progress = 0 if total == 0 else current / total # Avoid division by zero
        filled = int(bar_length * progress)
        bar = '=' * filled + '-' * (bar_length - filled)
        percentage = int(progress * 100)

        # Prepare display string for current file (truncate if too long)
        max_filename_len = 30
        display_file = current_file
        if len(display_file) > max_filename_len:
            display_file = "..." + display_file[-(max_filename_len-3):]

        # Construct the progress line
        # Use carriage return \r to overwrite the line. Add spaces at the end to clear previous longer filenames.
        clear_len = 80 # Estimate line length to clear
        progress_line = f"\rProgress: [{bar}] {percentage}% ({current}/{total}) Processing: {display_file:<{max_filename_len+2}}"
        progress_line += " " * (clear_len - len(progress_line)) # Pad with spaces

        sys.stdout.write(progress_line)
        sys.stdout.flush()

        if force_newline or (total > 0 and current == total):
            sys.stdout.write('\n') # Move to a new line when done
            sys.stdout.flush()


    def run(self) -> dict:
        """Run the agent to fetch and parse all log files."""
        groups = self.fetch_groups()

        if groups is None:
            self._logger.error("Cannot proceed without groups. Check Elasticsearch connection and 'group_infos' index.")
            return {} # Return empty dict on failure to fetch
        return self.parse_all_logs(groups)

# Example usage
if __name__ == "__main__":
    from ..utils.llm_model import GeminiModel
    from pprint import pprint

    # It's good practice to initialize necessary components like the model first
    try:
        print("Initializing LLM Model...")
        model = GeminiModel() # Make sure GENAI_API_KEY is set
        print("Initializing GroupLogParserAgent...")
        agent = GroupLogParserAgent(model=model)

        print("Running parser agent...")
        parsing_results = agent.run() # Changed variable name

        print("\n--- Parsing Summary ---")
        successful_groups = 0
        total_csvs = 0
        failed_groups = []

        for group, csv_paths in parsing_results.items():
            if csv_paths:
                print(f"Group '{group}': {len(csv_paths)} CSVs generated")
                # Uncomment to list all paths
                # for csv_path in csv_paths:
                #     print(f"  -> {os.path.basename(csv_path)}")
                successful_groups += 1
                total_csvs += len(csv_paths)
            else:
                print(f"Group '{group}': No CSVs generated (check logs for errors)")
                failed_groups.append(group)

        print("\n--- Overall ---")
        print(f"Total Groups Processed: {len(parsing_results)}")
        print(f"Groups with at least one successful parse: {successful_groups}")
        print(f"Total CSV files generated: {total_csvs}")
        if failed_groups:
             print(f"Groups with no successful parses: {', '.join(failed_groups)}")
        print("Processing complete. Check logs for detailed errors.")

    except ValueError as val_err:
         print(f"\nConfiguration Error: {val_err}")
    except Exception as e:
         print(f"\nAn unexpected error occurred: {e}")
         import traceback
         traceback.print_exc()
