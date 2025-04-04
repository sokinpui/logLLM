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

# --- Worker Function for Parallel Processing ---
# (This remains the same as the previous version - it correctly passes show_progress down)
def _parse_file_worker(file_path: str, group_format: Optional[str], show_progress: bool) -> Tuple[str, Optional[str]]:
    """
    Worker function to parse a single file. Initializes its own dependencies.
    Returns a tuple: (original_file_path, output_csv_path or None on failure)
    """
    worker_logger = Logger()
    try:
        worker_model = GeminiModel() # Ensure API keys accessible via env
        worker_agent = SimpleDrainLogParserAgent(model=worker_model)
        initial_state: SimpleDrainLogParserState = {
            "log_file_path": file_path, "log_format": group_format,
            "output_csv_path": "", "sample_logs": ""
        }
        # Pass the flag correctly
        result_state = worker_agent.run(initial_state, show_progress=show_progress)

        # Optional Fallback Logic
        if not result_state.get("output_csv_path") and group_format:
             worker_logger.warning(f"Group format failed for {os.path.basename(file_path)}. Trying file-specific.")
             fallback_state = initial_state.copy(); fallback_state["log_format"] = None
             fallback_result_state = worker_agent.run(fallback_state, show_progress=show_progress)
             output_path = fallback_result_state.get("output_csv_path") or None
             # Log success/failure of fallback
             return file_path, output_path
        else:
             return file_path, result_state.get("output_csv_path") or None
    except Exception as e:
        worker_logger.error(f"Error in worker for {os.path.basename(file_path)}: {e}", exc_info=True)
        print(f"[File ???] ERROR (Worker): {os.path.basename(file_path)} - {e}")
        return file_path, None

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
        self._model_instance_for_sequential = model # Used for threads=1 or pre-determination

    def fetch_groups(self) -> Optional[Dict[str, List[str]]]:
        """Fetch group information from Elasticsearch."""
        # (This method remains the same as the previous version)
        try:
            query = {"query": {"match_all": {}}}
            groups_index = cfg.INDEX_GROUP_INFOS
            self._logger.info(f"Fetching groups from index: {groups_index}")
            groups_data = self._db.scroll_search(query=query, index=groups_index)
            if not groups_data:
                 self._logger.warning(f"No group info found in index '{groups_index}'. Run 'collect'?")
                 return None
            groups = {doc["_source"]["group"]: doc["_source"]["files"] for doc in groups_data}
            self._logger.info(f"Fetched {len(groups)} groups.")
            return groups
        except Exception as e:
            self._logger.error(f"Failed to fetch groups from index '{groups_index}': {e}", exc_info=True)
            return None

    def parse_all_logs(self, groups: Dict[str, List[str]], num_threads: int, show_progress: bool) -> Dict[str, List[str]]:
        """Parse logs sequentially or in parallel, respecting show_progress flag."""
        if not groups: return {}

        tasks: List[Tuple[str, str]] = []
        group_formats: Dict[str, Optional[str]] = {}
        total_files = 0
        format_agent: Optional[SimpleDrainLogParserAgent] = None

        # Attempt to pre-determine formats only if running in parallel
        if num_threads > 1:
             try:
                 format_agent = SimpleDrainLogParserAgent(self._model_instance_for_sequential)
                 print("Attempting to determine initial log formats for groups...")
             except Exception as model_init_err:
                  self._logger.error(f"Failed init for format pre-determination: {model_init_err}")
                  format_agent = None

        for group, files in groups.items():
            group_format = None
            first_file_in_group = next((f for f in files if os.path.isfile(f)), None)
            if first_file_in_group and format_agent:
                try:
                    group_format = format_agent._generate_log_format(first_file_in_group)
                    # Log result, don't print here to avoid clutter if suppressed later
                    if group_format: self._logger.info(f"Pre-determined format for '{group}': OK")
                    else: self._logger.warning(f"Could not pre-determine format for group '{group}'.")
                except Exception as format_e:
                     self._logger.error(f"Error pre-determining format for '{group}': {format_e}")
            group_formats[group] = group_format

            # Build task list with only existing files
            valid_files = [f for f in files if os.path.isfile(f)]
            tasks.extend([(group, file_path) for file_path in valid_files])
            if len(valid_files) < len(files):
                 self._logger.warning(f"Group '{group}': Found {len(files) - len(valid_files)} missing files.")
            total_files += len(valid_files)

        if total_files == 0:
            self._logger.warning("No existing log files found in any group.")
            return {}

        self._logger.info(f"Prepared {total_files} files for parsing using {num_threads} worker(s).")
        print(f"\n=== Starting Group Log Parsing ({total_files} files using {num_threads} worker(s)) ===")

        progress: Dict[str, List[str]] = {group: [] for group in groups}
        processed_files = 0

        # --- Conditional Execution ---
        if num_threads <= 1:
            # --- Sequential ---
            self._logger.info("Running in sequential mode.")
            sequential_agent = SimpleDrainLogParserAgent(self._model_instance_for_sequential)
            # Determine if the overwriting progress bar should be used
            use_progress_bar = not show_progress

            for group, file_path in tasks:
                processed_files += 1
                base_name = os.path.basename(file_path)
                if use_progress_bar: self._update_progress_bar(processed_files, total_files, current_file=base_name)
                else: print(f"\n[File {processed_files}/{total_files}] Processing: {base_name} (Group: {group})")

                try:
                    initial_format = group_formats.get(group)
                    state: SimpleDrainLogParserState = {
                        "log_file_path": file_path, "log_format": initial_format,
                        "output_csv_path": "", "sample_logs": ""
                    }
                    # Pass the show_progress flag correctly
                    result = sequential_agent.run(state, show_progress=show_progress)

                    # Report success/failure only if not using progress bar
                    if result.get("output_csv_path"):
                        progress[group].append(result["output_csv_path"])
                        if not use_progress_bar: print(f"[File {processed_files}/{total_files}] SUCCESS: {base_name}")
                    elif not use_progress_bar: print(f"[File {processed_files}/{total_files}] FAILED: {base_name}")
                except Exception as e:
                    self._logger.error(f"Sequential run failed for {base_name}: {e}", exc_info=True)
                    if not use_progress_bar: print(f"[File {processed_files}/{total_files}] ERROR (Agent): {base_name} - {e}")

            if use_progress_bar: self._update_progress_bar(total_files, total_files, force_newline=True)

        else:
            # --- Parallel ---
            self._logger.info(f"Running in parallel mode (threads={num_threads}).")
            # Always use simple prints for parallel progress, regardless of show_progress flag
            effective_show_progress_for_print = True
            if not show_progress:
                 print("NOTE: Detailed progress bar disabled in parallel mode. Drain output suppressed.")

            with concurrent.futures.ProcessPoolExecutor(max_workers=num_threads) as executor:
                future_to_task = {
                    executor.submit(_parse_file_worker, file_path, group_formats.get(group), show_progress): (group, file_path)
                    for group, file_path in tasks # Uses pre-filtered tasks
                }
                for future in concurrent.futures.as_completed(future_to_task):
                    original_group, original_file_path = future_to_task[future]
                    base_name = os.path.basename(original_file_path)
                    processed_files += 1
                    try:
                        _, output_path = future.result() # Unpack result from worker
                        # Always use simple print for progress in parallel mode
                        if output_path:
                            print(f"[File {processed_files}/{total_files}] SUCCESS: {base_name} (Group: {original_group})", flush=True)
                            progress[original_group].append(output_path)
                        else:
                            print(f"[File {processed_files}/{total_files}] FAILED: {base_name} (Group: {original_group})", flush=True)
                    except Exception as e:
                        self._logger.error(f"Error processing future for {base_name}: {e}", exc_info=True)
                        print(f"[File {processed_files}/{total_files}] ERROR (Future): {base_name} - {e}", flush=True)

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
        """Fetches groups and initiates parsing respecting flags."""
        groups = self.fetch_groups()
        if groups is None: self._logger.error("Cannot proceed without groups."); return {}
        if num_threads < 1: num_threads = 1
        return self.parse_all_logs(groups, num_threads=num_threads, show_progress=show_progress)


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
