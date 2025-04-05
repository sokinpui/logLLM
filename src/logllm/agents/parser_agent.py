# src/logllm/agents/parser_agent.py

import os
import pandas as pd
from typing import TypedDict, Dict, List, Optional, Tuple
from logparser.Drain import LogParser
from pydantic import BaseModel, Field # Import contextlib for conditional suppression
from contextlib import redirect_stdout, nullcontext
import sys
import concurrent.futures
import multiprocessing
from pygrok import Grok
import csv # Import csv module

# Relative imports (ensure paths are correct for your structure)
try:
    from ..utils.llm_model import LLMModel, GeminiModel
    from ..utils.logger import Logger
    from ..utils.prompts_manager import PromptsManager
    from ..utils.database import ElasticsearchDatabase
    from ..config import config as cfg
except ImportError as e:
     print(f"Error during agent imports: {e}")
     # Add more robust import handling if needed
     sys.exit(1)

# --- SimpleDrainLogParserState Definition ---
class SimpleDrainLogParserState(TypedDict):
    log_file_path: str
    log_format: Optional[str]
    output_csv_path: str
    sample_logs: str

class SimpleGrokLogParserState(TypedDict):
    log_file_path: str
    grok_pattern: Optional[str]  # Can be user-provided or LLM-generated
    output_csv_path: str
    sample_logs: str
    parsed_lines: int # Keep track of how many lines were successfully parsed
    skipped_lines: int # Keep track of lines that didn't match

# --- Worker Function for Parallel Processing ---
# (This remains the same as the previous version - it correctly passes show_progress down)
def _parse_file_worker(file_path: str, group_grok_pattern: Optional[str], show_progress: bool) -> Tuple[str, Optional[str]]:
    """
    Worker function to parse a single file using SimpleGrokLogParserAgent.
    Initializes its own dependencies.
    Returns a tuple: (original_file_path, output_csv_path or None on failure)
    """
    worker_logger = Logger() # Each worker gets its own logger instance if needed, or use shared singleton
    output_path: Optional[str] = None
    try:
        # Worker needs its own model instance if running in separate processes
        worker_model = GeminiModel() # Ensure API keys accessible via env
        # *** Use the Grok Agent ***
        worker_agent = SimpleGrokLogParserAgent(model=worker_model)
        # *** Use the Grok State ***
        initial_state: SimpleGrokLogParserState = {
            "log_file_path": file_path,
            "grok_pattern": group_grok_pattern, # Pass the pre-determined group pattern (or None)
            "output_csv_path": "",
            "sample_logs": "", # Agent will populate if needed for generation
            "parsed_lines": 0,
            "skipped_lines": 0
        }
        # 'show_progress' flag is less relevant for Grok's output but pass for consistency
        result_state = worker_agent.run(initial_state, show_progress=show_progress)

        output_path = result_state.get("output_csv_path") or None

        # --- Optional Fallback Logic (If group pattern failed, try generating file-specific) ---
        # Check if parsing failed *and* we were using a pre-provided group pattern
        if not output_path and group_grok_pattern:
             worker_logger.warning(f"Group Grok pattern failed for {os.path.basename(file_path)}. Trying file-specific pattern generation.")
             # Create new state *without* the pattern to trigger LLM generation
             fallback_state: SimpleGrokLogParserState = {
                 "log_file_path": file_path, "grok_pattern": None, # <-- Force generation
                 "output_csv_path": "", "sample_logs": "",
                 "parsed_lines": 0, "skipped_lines": 0
             }
             fallback_result_state = worker_agent.run(fallback_state, show_progress=show_progress)
             output_path = fallback_result_state.get("output_csv_path") or None
             if output_path:
                 worker_logger.info(f"Fallback Grok pattern generation SUCCESSFUL for {os.path.basename(file_path)}")
             else:
                 worker_logger.warning(f"Fallback Grok pattern generation FAILED for {os.path.basename(file_path)}")

        return file_path, output_path

    except Exception as e:
        # Log error specific to this file/worker
        worker_logger.error(f"Error in Grok worker for {os.path.basename(file_path)}: {e}", exc_info=True)
        # Also print to console for immediate feedback during CLI runs
        print(f"[File ???] ERROR (Grok Worker): {os.path.basename(file_path)} - {e}")
        return file_path, None # Ensure failure returns None for the path

# src/logllm/agents/parser_agent.py (add this class)

class GrokPatternSchema(BaseModel):
    """Pydantic schema for the LLM response containing the Grok pattern."""
    grok_pattern: str = Field(description="Output only the Grok pattern string.")

class SimpleGrokLogParserAgent:
    SAMPLE_SIZE = 10 # Number of lines to sample for LLM

    def __init__(self, model: LLMModel):
        self._model = model
        self._logger = Logger()
        # Ensure prompt path is correct
        prompt_path = os.path.join("prompts/prompts.json")
        if not os.path.exists(prompt_path):
             # Attempt relative path if absolute fails (useful if run from project root)
             prompt_path = os.path.join(os.path.dirname(__file__), "..", "..", "prompts/prompts.json")
             if not os.path.exists(prompt_path):
                 raise FileNotFoundError(f"Prompts file not found at primary or relative path: {prompt_path}")
        self.prompts_manager = PromptsManager(json_file=prompt_path)
        # Optional: Preload common patterns (can improve performance slightly)
        # Grok.DEFAULT_PATTERNS_DIRS = [...] # If you have custom pattern files

    def run(self, initial_state: SimpleGrokLogParserState, show_progress: bool = False) -> SimpleGrokLogParserState:
        """Parse a single log file using Grok, conditionally generating the pattern via LLM."""
        if "log_file_path" not in initial_state or not os.path.isfile(initial_state["log_file_path"]):
             self._logger.error("Valid 'log_file_path' must be provided in state.")
             raise ValueError("Valid 'log_file_path' must be provided.")

        log_file_path = initial_state["log_file_path"]
        grok_pattern = initial_state.get("grok_pattern") # Get potential user-provided pattern
        base_name = os.path.basename(log_file_path)

        # --- Initialize result state ---
        result: SimpleGrokLogParserState = initial_state.copy()
        result["output_csv_path"] = "" # Default to no output path
        result["parsed_lines"] = 0
        result["skipped_lines"] = 0

        # --- Generate Grok Pattern if not provided ---
        if not grok_pattern:
            self._logger.info(f"Grok pattern not provided for {base_name}. Generating via LLM...")
            grok_pattern = self._generate_grok_pattern(log_file_path)
            result["grok_pattern"] = grok_pattern # Store the generated pattern in the state

            if not grok_pattern:
                 self._logger.warning(f"Failed to generate Grok pattern for {base_name}. Skipping parsing.")
                 return result # Cannot parse without a pattern

            self._logger.info(f"LLM generated Grok pattern for {base_name}: {grok_pattern}")
        else:
            self._logger.info(f"Using provided Grok pattern for {base_name}: {grok_pattern}")


        # --- Run Grok Parser ---
        try:
             # Pass the potentially updated state
             final_state = self._run_grok_parser(result)
             return final_state
        except Exception as e:
             self._logger.error(f"Error during Grok parsing execution for {base_name}: {e}", exc_info=True)
             # Ensure output path is empty on error
             result["output_csv_path"] = ""
             return result


    def _generate_grok_pattern(self, log_file_path: str) -> Optional[str]:
        """Generate Grok pattern using LLM based on log samples."""
        try:
            with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                # Handle empty files
                if not lines:
                    self._logger.warning(f"Log file is empty, cannot sample: {log_file_path}")
                    return None
                sample_size = min(self.SAMPLE_SIZE, len(lines))
                # Ensure sample size is at least 1 if file has lines
                sample_size = max(1, sample_size)
                # Use pandas sampling if available and useful, otherwise random.sample
                try:
                     sample_logs = pd.Series(lines).sample(sample_size).tolist()
                except NameError: # pandas might not be imported/used everywhere
                     import random
                     sample_logs = random.sample(lines, sample_size)

        except FileNotFoundError:
            self._logger.error(f"Log file not found for sampling: {log_file_path}")
            return None
        except Exception as e:
            self._logger.error(f"Failed to read or sample log file {os.path.basename(log_file_path)}: {e}", exc_info=True)
            return None

        if not sample_logs:
            self._logger.warning(f"No log lines sampled from {os.path.basename(log_file_path)}, cannot generate pattern.")
            return None

        try:
            # --- Use PromptsManager to get the correct prompt ---
            # Make sure the key exists in your prompts.json
            prompt = self.prompts_manager.get_prompt(sample_logs=str(sample_logs))

            # --- Call LLM ---
            response = self._model.generate(prompt, schema=GrokPatternSchema)

            # --- Validate Response ---
            if response and isinstance(response, GrokPatternSchema) and response.grok_pattern:
                pattern = response.grok_pattern.strip()
                # Basic sanity check - does it look like a Grok pattern?
                if "%{" in pattern and "}" in pattern:
                    self._logger.debug(f"LLM returned Grok pattern: {pattern}")
                    return pattern
                else:
                    self._logger.warning(f"LLM response doesn't look like a valid Grok pattern: {pattern}")
                    return None
            else:
                self._logger.warning(f"LLM did not return a valid GrokPatternSchema object. Response: {response}")
                return None

        except ValueError as ve: # Catch potential Pydantic validation errors or missing/extra vars
             self._logger.error(f"Error getting or formatting prompt for Grok generation: {ve}", exc_info=True)
             return None
        except Exception as e:
            self._logger.error(f"LLM call failed during Grok pattern generation: {e}", exc_info=True)
            return None


    def _run_grok_parser(self, state: SimpleGrokLogParserState) -> SimpleGrokLogParserState:
        """Parses the log file using the provided Grok pattern and writes to CSV."""
        log_file_path = state["log_file_path"]
        grok_pattern = state["grok_pattern"]
        base_name = os.path.basename(log_file_path)
        dir_name = os.path.dirname(log_file_path)

        # Define output path relative to input file
        output_csv_path = os.path.join(dir_name, f"parsed_grok_{base_name}.csv")
        result = state.copy() # Work on a copy
        result["output_csv_path"] = "" # Reset path initially

        if not grok_pattern:
            self._logger.error(f"Cannot run Grok parser for {base_name}: No Grok pattern provided in state.")
            return result

        try:
            # --- Compile Grok Pattern ---
            # This can throw ValueError if the pattern syntax is invalid
            grok = Grok(grok_pattern)
            self._logger.info(f"Successfully compiled Grok pattern for {base_name}.")

        except ValueError as e:
            self._logger.error(f"Invalid Grok pattern syntax provided for {base_name}: {grok_pattern} - Error: {e}", exc_info=True)
            print(f"--- Grok FAILED (Invalid Pattern) for: {base_name} ---")
            return result # Cannot proceed with invalid pattern

        parsed_data = []
        skipped_count = 0
        parsed_count = 0
        all_fieldnames = set()
        all_fieldnames.add("OriginalLogLine") # Add this field explicitly

        # --- First Pass: Parse and Collect Data + Headers ---
        self._logger.info(f"Starting Grok parsing pass 1 (reading lines) for {base_name}...")
        try:
            with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as infile:
                for i, line in enumerate(infile):
                    line = line.strip()
                    if not line: # Skip empty lines
                        continue

                    match = grok.match(line)
                    if match:
                        # Add the original line for context/debugging
                        match['OriginalLogLine'] = line
                        parsed_data.append(match)
                        all_fieldnames.update(match.keys()) # Dynamically collect all field names
                        parsed_count += 1
                    else:
                        if skipped_count < 10: # Log only the first few skips to avoid flooding
                            self._logger.warning(f"Line {i+1} in {base_name} did not match Grok pattern: {line[:100]}...")
                        elif skipped_count == 10:
                            self._logger.warning(f"Further Grok mismatches for {base_name} will not be logged individually.")
                        skipped_count += 1
        except FileNotFoundError:
             self._logger.error(f"Input log file not found: {log_file_path}")
             print(f"--- Grok SKIPPED (File not found): {base_name} ---")
             return result
        except Exception as e:
             self._logger.error(f"Error reading log file {base_name}: {e}", exc_info=True)
             print(f"--- Grok FAILED (Read Error): {base_name} ---")
             return result

        result["parsed_lines"] = parsed_count
        result["skipped_lines"] = skipped_count
        self._logger.info(f"Grok parsing pass 1 finished for {base_name}. Parsed: {parsed_count}, Skipped: {skipped_count}")

        if not parsed_data:
             self._logger.warning(f"No lines were successfully parsed by Grok for {base_name}. No CSV will be generated.")
             print(f"--- Grok WARNING (No lines matched): {base_name} ---")
             return result # No data to write

        # --- Second Pass: Write to CSV ---
        # Sort field names for consistent column order, put OriginalLogLine first maybe
        sorted_fieldnames = sorted(list(all_fieldnames))
        if "OriginalLogLine" in sorted_fieldnames:
             sorted_fieldnames.remove("OriginalLogLine")
             sorted_fieldnames.insert(0, "OriginalLogLine")

        self._logger.info(f"Starting Grok parsing pass 2 (writing CSV) for {base_name} to {output_csv_path}...")
        try:
            with open(output_csv_path, 'w', newline='', encoding='utf-8') as outfile:
                writer = csv.DictWriter(outfile, fieldnames=sorted_fieldnames)
                writer.writeheader()
                writer.writerows(parsed_data) # Write all collected data

            result["output_csv_path"] = output_csv_path # Set path only on successful write
            self._logger.info(f"Successfully wrote Grok parsed data for {base_name} to {os.path.basename(output_csv_path)}")
            print(f"--- Grok SUCCESS: {base_name} -> {os.path.basename(output_csv_path)} ---")

        except IOError as e:
             self._logger.error(f"Failed to write CSV file {output_csv_path}: {e}", exc_info=True)
             print(f"--- Grok FAILED (Write Error): {base_name} ---")
             result["output_csv_path"] = "" # Clear path on write error
        except Exception as e:
             self._logger.error(f"Unexpected error writing CSV for {base_name}: {e}", exc_info=True)
             print(f"--- Grok FAILED (Unexpected Write Error): {base_name} ---")
             result["output_csv_path"] = "" # Clear path on write error

        return result

# --- SimpleDrainLogParserAgent Class ---
class SimpleDrainLogParserAgent:
    SAMPLE_SIZE = 10

    def __init__(self, model: LLMModel):
        self._model = model
        self._logger = Logger()
        # Ensure prompt path is correct
        prompt_path = os.path.join("prompts/prompts.json")
        if not os.path.exists(prompt_path):
             raise FileNotFoundError(f"Prompts file not found: {prompt_path}")
        self.prompts_manager = PromptsManager(json_file=prompt_path)

    def run(self, initial_state: SimpleDrainLogParserState, show_progress: bool = False) -> SimpleDrainLogParserState:
        """Parse a single log file, conditionally suppressing Drain output."""
        if "log_file_path" not in initial_state or not os.path.isfile(initial_state["log_file_path"]):
             self._logger.error("Valid 'log_file_path' must be provided.")
             raise ValueError("Valid 'log_file_path' must be provided.")
        log_file_path = initial_state["log_file_path"]
        log_format = initial_state.get("log_format")
        result = initial_state.copy()
        result["output_csv_path"] = ""

        if not log_format:
            self._logger.info(f"Generating format for {os.path.basename(log_file_path)}...")
            log_format = self._generate_log_format(log_file_path)
            result["log_format"] = log_format # Store generated format
            if not log_format:
                 self._logger.warning(f"Failed to generate format. Skipping parsing.")
                 return result # Cannot parse without format

        # Pass the potentially updated state and the flag to drain runner
        state_for_drain = result.copy()
        state_for_drain["log_format"] = log_format
        drain_result_state = self._run_drain_parser(state_for_drain, show_progress=show_progress)
        return drain_result_state

    def _generate_log_format(self, log_file_path: str) -> Optional[str]:
        """Generate log format using LLM."""
        # (This method remains the same as the previous version)
        try:
            with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines(); sample_size = min(self.SAMPLE_SIZE, len(lines))
                if not lines or sample_size <= 0: self._logger.warning(f"Cannot sample: {log_file_path}"); return None
                sample_logs = pd.Series(lines).sample(sample_size).tolist()
        except Exception as e: self._logger.error(f"Sample failed: {e}", exc_info=True); return None
        if not sample_logs: self._logger.error(f"No samples: {log_file_path}"); return None
        try:
            prompt = self.prompts_manager.get_prompt(sample_logs=str(sample_logs))
            if not prompt: self._logger.error("Prompt failed."); return None
            class LogFormatSchema(BaseModel): log_format: str = Field(description="Output only the log format string.")
            response = self._model.generate(prompt, LogFormatSchema)
            if response and isinstance(response, LogFormatSchema) and response.log_format:
                fmt = response.log_format.strip();
                if "<" in fmt and ">" in fmt: self._logger.info(f"Generated format: {fmt}"); return fmt
            self._logger.warning(f"Invalid LLM format response: {response}"); return None
        except Exception as e: self._logger.error(f"LLM failed: {e}", exc_info=True); return None

    # --- CORRECTED _run_drain_parser ---
    def _run_drain_parser(self, state: SimpleDrainLogParserState, show_progress: bool = False) -> SimpleDrainLogParserState:
        """Run Drain parser, conditionally suppressing output based on show_progress."""
        log_file_path = state["log_file_path"]
        log_format = state["log_format"]
        result = state.copy() # Start with the input state

        dir_name = os.path.dirname(log_file_path)
        base_name = os.path.basename(log_file_path)
        output_csv = os.path.join(dir_name, f"parsed_{base_name}_structured.csv")

        if not log_format: # Safety check
             self._logger.error(f"Cannot run Drain for {base_name}: No log format.")
             result["output_csv_path"] = ""
             return result

        try:
            parser = LogParser(
                log_format=log_format, indir=dir_name, outdir=dir_name, depth=4, st=0.5,
                rex = [
                    # IDs (Hadoop/Spark specific - adjust if needed)
                    r'application_\d+_\d+',
                    r'container_\d+_\d+_\d+_\d+',
                    r'job_\d+_\d+',
                    r'task_\d+_m_\d+', # Map task
                    r'task_\d+_r_\d+', # Reduce task
                    # Java Exceptions/Class paths (match common patterns)
                    r'\b[a-zA-Z0-9_]+\.[a-zA-Z0-9._]+\b', # Package/Class names
                    r'(\w+\.){2,}\w+(Exception|Error)', # Exception names
                    # Network addresses
                    r'(?:(?:[0-9]{1,3}\.){3}[0-9]{1,3})', # IPv4
                    r'(?:(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}|::1)', # Basic IPv6
                    # Paths (simple version)
                    r'(?:/[a-zA-Z0-9._-]+)+',
                    # Block IDs
                    r'blk_(?:-?\d+)+',
                    # Hexadecimal values
                    r'0x[0-9a-fA-F]+',
                    # Other common numbers (placed later)
                    r'\b\d+\.\d+\b', # Floating point
                    r'(?<=[^A-Za-z0-9])(\-?\+?\d+)(?=[^A-Za-z0-9])|\b\d+\b', # Integers
                ]
            )
            self._logger.info(f"Running Drain on {base_name} with format: {log_format}")

            # --- Conditional Suppression Logic ---
            # If show_progress is True, use nullcontext (no suppression)
            # If show_progress is False, use redirect_stdout to suppress
            stdout_manager = nullcontext() if show_progress else redirect_stdout(open(os.devnull, 'w'))
            # --------------------------------------

            # Print start marker only if suppressing (otherwise Drain prints its own)
            if not show_progress: print(f"--- Parsing: {base_name} ---", flush=True)

            file_to_parse = os.path.join(dir_name, base_name)
            file_exists = os.path.exists(file_to_parse)

            with stdout_manager: # Apply the chosen context manager
                 if file_exists:
                     parser.parse(base_name) # Drain runs here
                 else:
                     self._logger.error(f"Input file not found for Drain: {file_to_parse}")
                     # Always print skip message clearly
                     print(f"--- Drain SKIPPED (File not found): {base_name} ---")
                     result["output_csv_path"] = ""
                     return result # Exit early

            # Print finish marker only if suppressing
            if not show_progress: print(f"--- Finished: {base_name} ---", flush=True)

            # Check for Drain's output file and rename it
            temp_output = os.path.join(dir_name, f"{base_name}_structured.csv")
            if os.path.exists(temp_output):
                final_output_path = output_csv
                try:
                    if os.path.exists(final_output_path): os.remove(final_output_path)
                    os.rename(temp_output, final_output_path)
                    result["output_csv_path"] = final_output_path
                    self._logger.info(f"Successfully parsed {base_name} -> {os.path.basename(final_output_path)}")
                except OSError as rename_error:
                     self._logger.error(f"Failed rename: {rename_error}")
                     result["output_csv_path"] = "" # Failed rename means no valid output
            else:
                self._logger.warning(f"Drain done, no output CSV found: {temp_output}")
                result["output_csv_path"] = ""

        except Exception as e:
            self._logger.error(f"Drain parsing failed for {base_name}: {e}", exc_info=True)
            print(f"--- Drain FAILED for: {base_name} (Error: {e}) ---") # Always show failure
            result["output_csv_path"] = ""

        return result # Return the final state


# --- GroupLogParserAgent Class ---
class GroupLogParserAgent:
    def __init__(self, model: LLMModel):
        self._logger = Logger()
        self._db = ElasticsearchDatabase()
        # *** Store model instance for sequential runs or pre-determination ***
        self._model_instance = model

    def fetch_groups(self) -> Optional[Dict[str, List[str]]]:
        # (This method remains the same - fetches group info from DB)
        try:
            query = {"query": {"match_all": {}}}
            groups_index = cfg.INDEX_GROUP_INFOS
            self._logger.info(f"Fetching groups from index: {groups_index}")
            groups_data = self._db.scroll_search(query=query, index=groups_index)
            if not groups_data:
                 self._logger.warning(f"No group info found in index '{groups_index}'. Run 'collect' first?")
                 return None
            # Ensure 'files' field exists and is a list
            groups = {}
            for doc in groups_data:
                source = doc.get("_source", {})
                group_name = source.get("group")
                files = source.get("files")
                if group_name and isinstance(files, list):
                    groups[group_name] = files
                else:
                    self._logger.warning(f"Skipping invalid group document in index '{groups_index}': ID {doc.get('_id')}")

            self._logger.info(f"Fetched {len(groups)} valid groups.")
            return groups
        except Exception as e:
            self._logger.error(f"Failed to fetch or process groups from index '{cfg.INDEX_GROUP_INFOS}': {e}", exc_info=True)
            return None


    def parse_all_logs(self, groups: Dict[str, List[str]], num_threads: int, show_progress: bool) -> Dict[str, List[str]]:
        """Parse logs sequentially or in parallel using SimpleGrokLogParserAgent."""
        if not groups:
            self._logger.warning("No groups provided to parse_all_logs.")
            return {}

        tasks: List[Tuple[str, str]] = [] # List of (group_name, file_path)
        group_grok_patterns: Dict[str, Optional[str]] = {} # Store pre-determined patterns
        total_files = 0
        pattern_agent: Optional[SimpleGrokLogParserAgent] = None # Agent instance for pattern generation

        # --- Attempt to pre-determine Grok patterns (optional but can save LLM calls) ---
        # Only makes sense if running in parallel or if you want consistency
        should_predetermine = num_threads > 0 # Let's always try, even for sequential

        if should_predetermine:
             try:
                 # *** Use the Grok Agent for pattern generation ***
                 pattern_agent = SimpleGrokLogParserAgent(self._model_instance)
                 print("Attempting to determine initial Grok patterns for groups...")
             except Exception as model_init_err:
                  self._logger.error(f"Failed to initialize SimpleGrokLogParserAgent for pattern pre-determination: {model_init_err}")
                  pattern_agent = None

        # --- Prepare tasks and generate patterns ---
        for group, files in groups.items():
            group_pattern: Optional[str] = None
            # Find the first valid, existing file in the group to sample from
            first_file_in_group = next((f for f in files if isinstance(f, str) and os.path.isfile(f)), None)

            if first_file_in_group and pattern_agent:
                self._logger.debug(f"Attempting pattern pre-determination for group '{group}' using file '{os.path.basename(first_file_in_group)}'")
                try:
                    # *** Call the Grok pattern generation method ***
                    group_pattern = pattern_agent._generate_grok_pattern(first_file_in_group)
                    if group_pattern:
                         self._logger.info(f"Pre-determined Grok pattern for group '{group}': OK")
                         # print(f"  Pattern for '{group}': {group_pattern}") # Optional: print pattern
                    else:
                         self._logger.warning(f"Could not pre-determine Grok pattern for group '{group}'. Will attempt per-file generation if needed.")
                except Exception as format_e:
                     self._logger.error(f"Error pre-determining Grok pattern for group '{group}': {format_e}", exc_info=True)

            group_grok_patterns[group] = group_pattern

            # Build task list with only existing, valid files
            valid_files = [f for f in files if isinstance(f, str) and os.path.isfile(f)]
            tasks.extend([(group, file_path) for file_path in valid_files])
            missing_count = len(files) - len(valid_files)
            if missing_count > 0:
                 self._logger.warning(f"Group '{group}': Found {missing_count} missing or invalid file paths.")
            total_files += len(valid_files)

        if total_files == 0:
            self._logger.warning("No existing log files found across all provided groups.")
            return {}

        self._logger.info(f"Prepared {total_files} files for Grok parsing using {num_threads} worker(s).")
        print(f"\n=== Starting Group Log Parsing ({total_files} files using {num_threads} worker(s)) ===")

        # --- Execute Parsing (Sequential or Parallel) ---
        progress: Dict[str, List[str]] = {group: [] for group in groups} # Stores successful output CSV paths
        processed_files_count = 0

        if num_threads <= 1:
            # --- Sequential Execution ---
            self._logger.info("Running Grok parsing in sequential mode.")
            # Use the main model instance
            sequential_agent = SimpleGrokLogParserAgent(self._model_instance)
            use_progress_bar = not show_progress # Use bar only if hiding detailed output

            for group, file_path in tasks:
                processed_files_count += 1
                base_name = os.path.basename(file_path)
                if use_progress_bar: self._update_progress_bar(processed_files_count, total_files, current_file=base_name)
                else: print(f"\n[File {processed_files_count}/{total_files}] Processing: {base_name} (Group: {group})")

                try:
                    # *** Use the Grok State ***
                    initial_state: SimpleGrokLogParserState = {
                        "log_file_path": file_path,
                        "grok_pattern": group_grok_patterns.get(group), # Use pre-determined pattern if available
                        "output_csv_path": "", "sample_logs": "",
                        "parsed_lines": 0, "skipped_lines": 0
                    }
                    # Pass the show_progress flag (less relevant for Grok output but maintains interface)
                    result = sequential_agent.run(initial_state, show_progress=show_progress)

                    output_csv = result.get("output_csv_path")
                    if output_csv:
                        progress[group].append(output_csv)
                        if not use_progress_bar: print(f"[File {processed_files_count}/{total_files}] SUCCESS: {base_name} -> {os.path.basename(output_csv)}")
                    elif not use_progress_bar: print(f"[File {processed_files_count}/{total_files}] FAILED: {base_name} (Parsed: {result.get('parsed_lines', 0)}, Skipped: {result.get('skipped_lines', 0)})")
                except Exception as e:
                    self._logger.error(f"Sequential Grok run failed for {base_name}: {e}", exc_info=True)
                    if not use_progress_bar: print(f"[File {processed_files_count}/{total_files}] ERROR (Agent): {base_name} - {e}")

            if use_progress_bar: self._update_progress_bar(total_files, total_files, force_newline=True) # Final newline for the bar

        else:
            # --- Parallel Execution ---
            self._logger.info(f"Running Grok parsing in parallel mode (max_workers={num_threads}).")
            # Progress bar is usually not practical with parallel console output
            print("Parallel mode: Progress updates will be printed per file.")

            with concurrent.futures.ProcessPoolExecutor(max_workers=num_threads) as executor:
                # Map futures to their original task info
                future_to_task = {
                    # *** Submit work using the UPDATED worker function ***
                    executor.submit(_parse_file_worker, file_path, group_grok_patterns.get(group), show_progress): (group, file_path)
                    for group, file_path in tasks # Use pre-filtered tasks
                }

                for future in concurrent.futures.as_completed(future_to_task):
                    original_group, original_file_path = future_to_task[future]
                    base_name = os.path.basename(original_file_path)
                    processed_files_count += 1
                    try:
                        _, output_path = future.result() # Unpack result from worker
                        if output_path:
                            print(f"[File {processed_files_count}/{total_files}] SUCCESS: {base_name} (Group: {original_group}) -> {os.path.basename(output_path)}", flush=True)
                            # Safely append to the shared progress dict (might need locking in extreme cases, but usually okay for appending lists)
                            if original_group in progress:
                                progress[original_group].append(output_path)
                            else:
                                self._logger.warning(f"Group '{original_group}' not found in progress dict while processing parallel result.")
                        else:
                            print(f"[File {processed_files_count}/{total_files}] FAILED: {base_name} (Group: {original_group})", flush=True)
                    except Exception as e:
                        # Log the error associated with the future/worker
                        self._logger.error(f"Error processing Grok future for {base_name}: {e}", exc_info=True)
                        print(f"[File {processed_files_count}/{total_files}] ERROR (Future): {base_name} - {e}", flush=True)

        print(f"\n=== Finished Group Log Parsing ===")
        return progress

    def _update_progress_bar(self, current: int, total: int, current_file: str = "", force_newline: bool = False):
        """Displays overwriting progress bar (only used if sequential and not show_progress)."""
        # (This method remains the same)
        bar_length=40; progress=0 if total==0 else current/total; filled=int(bar_length*progress); bar='='*filled + '-'*(bar_length-filled); percentage=int(progress*100); max_filename_len=30; display_file=current_file;
        if len(display_file)>max_filename_len: display_file="..."+display_file[-(max_filename_len-3):];
        clear_len=80; progress_line=f"\rProgress: [{bar}] {percentage}% ({current}/{total}) Processing: {display_file:<{max_filename_len+2}}"; progress_line+=" "*(clear_len-len(progress_line)); sys.stdout.write(progress_line); sys.stdout.flush();
        if force_newline or (total>0 and current==total): sys.stdout.write('\n'); sys.stdout.flush();


    def run(self, num_threads: int = 1, show_progress: bool = False) -> dict:
        """Fetches groups and initiates Grok parsing respecting flags."""
        groups = self.fetch_groups()
        if groups is None:
            self._logger.error("Cannot proceed with parsing: Failed to fetch groups.")
            return {}
        if not groups:
             self._logger.warning("No groups found to parse.")
             return {}
        # Ensure num_threads is at least 1 for sequential mode
        effective_num_threads = max(1, num_threads)
        return self.parse_all_logs(groups, num_threads=effective_num_threads, show_progress=show_progress)


# --- __main__ block for testing (optional) ---
if __name__ == "__main__":
    # Example test (ensure GENAI_API_KEY is set)
    try:
        print("Initializing LLM Model...")
        model = GeminiModel()
        print("Initializing GroupLogParserAgent...")
        agent = GroupLogParserAgent(model=model)

        print("\nRunning parser agent (Sequential, Progress Bar)...")
        results_seq = agent.run(num_threads=1, show_progress=False)
        # Print summary for results_seq...

        # print("\nRunning parser agent (Parallel, Show Progress)...")
        # num_workers = multiprocessing.cpu_count() # Use available cores
        # results_par = agent.run(num_threads=num_workers, show_progress=True)
        # Print summary for results_par...

    except ValueError as val_err:
         print(f"\nConfiguration Error: {val_err}")
    except Exception as e:
         print(f"\nAn unexpected error occurred: {e}")
         import traceback
         traceback.print_exc()
