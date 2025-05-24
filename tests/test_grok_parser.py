import json
import os
from typing import Any, Dict, Optional

import yaml
from pygrok import Grok  # type: ignore

# --- Configuration for the test script ---
GROK_PATTERNS_YAML_PATH = "grok_patterns.yaml"  # Path to your YAML file

# --- Sample Log Lines to Test (Replace these with actual lines from your failing logs) ---
# Example: If your group 'apache' is failing
SAMPLE_LOGS_TO_TEST = {
    "apache": [
        "[Mon Feb 27 17:32:59 2006] [error] [client 136.159.45.9] Directory index forbidden by rule: /var/www/html/",
        "[Mon Feb 27 17:44:14 2006] [error] [client 216.187.87.166] Directory index forbidden by rule: /var/www/html/",
        "[Mon Feb 27 18:01:24 2006] [error] [client 219.95.66.42] Directory index forbidden by rule: /var/www/html/",
        "[Mon Feb 27 18:43:18 2006] [error] [client 24.70.5.136] Directory index forbidden by rule: /var/www/html/",
        "[Mon Feb 27 21:17:17 2006] [error] [client 136.142.64.221] Directory index forbidden by rule: /var/www/html/",
        "[Mon Feb 27 21:56:11 2006] [error] [client 220.225.166.39] Directory index forbidden by rule: /var/www/html/",
        "[Tue Feb 28 00:45:58 2006] [error] [client 206.125.60.10] Directory index forbidden by rule: /var/www/html/",
        "[Tue Feb 28 00:46:47 2006] [error] [client 203.186.238.253] Directory index forbidden by rule: /var/www/html/",
        "[Tue Feb 28 03:04:53 2006] [error] [client 69.39.5.163] Directory index forbidden by rule: /var/www/html/",
        "[Tue Feb 28 03:49:01 2006] [error] [client 218.22.153.242] Directory index forbidden by rule: /var/www/html/%",
    ],
    # "hadoop_java_common": [
    #     "2015-10-17 18:12:48,870 INFO [main] org.apache.hadoop.mapred.MapTask: Spilling map output",
    #     "2015-10-17 18:12:48,870 INFO [main] org.apache.hadoop.mapred.MapTask: bufstart = 66980545; bufend = 10374147; bufvoid = 104857600",
    #     "2015-10-17 18:12:48,870 INFO [main] org.apache.hadoop.mapred.MapTask: kvstart = 16745132(66980528); kvend = 7836420(31345680); length = 8908713/6553600",
    #     "2015-10-17 18:12:48,870 INFO [main] org.apache.hadoop.mapred.MapTask: (EQUATOR) 19442899 kvi 4860720(19442880)",
    #     "2015-10-17 18:13:32,373 INFO [SpillThread] org.apache.hadoop.mapred.MapTask: Finished spill 3",
    #     "2015-10-17 18:13:32,716 INFO [main] org.apache.hadoop.mapred.MapTask: (RESET) equator 19442899 kv 4860720(19442880) kvi 2660780(10643120)",
    #     "2015-10-17 18:13:44,561 INFO [main] org.apache.hadoop.mapred.MapTask: Spilling map output",
    #     "2015-10-17 18:13:44,561 INFO [main] org.apache.hadoop.mapred.MapTask: bufstart = 19442899; bufend = 67657921; bufvoid = 104857600",
    #     "2015-10-17 18:13:44,561 INFO [main] org.apache.hadoop.mapred.MapTask: kvstart = 4860720(19442880); kvend = 22157356(88629424); length = 8917765/6553600",
    #     "2015-10-17 18:13:44,561 INFO [main] org.apache.hadoop.mapred.MapTask: (EQUATOR) 76726657 kvi 19181660(76726640)",
    # ],
}  # --- Helper Functions (from your GrokPatternService) ---


def load_grok_patterns_from_yaml(yaml_path: str) -> Dict[str, Any]:
    print(f"Attempting to load Grok patterns from YAML: {yaml_path}")
    if not os.path.exists(yaml_path):
        print(f"ERROR: Grok patterns YAML file not found at {yaml_path}")
        return {}
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            patterns = yaml.safe_load(f)
            if patterns is None:
                print(f"WARNING: Grok patterns YAML file is empty: {yaml_path}")
                return {}
            print(
                f"Successfully loaded {len(patterns)} top-level Grok pattern configurations."
            )
            return patterns
    except yaml.YAMLError as e:
        print(f"ERROR: Parsing Grok patterns YAML file {yaml_path}: {e}")
        return {}
    except Exception as e:
        print(f"ERROR: Unexpected error loading Grok patterns YAML {yaml_path}: {e}")
        return {}


def get_grok_pattern_string_for_group(
    grok_patterns_config: Dict, group_name: str
) -> Optional[str]:
    pattern_config = grok_patterns_config.get(group_name)
    if not pattern_config or "grok_pattern" not in pattern_config:
        print(
            f"DEBUG: No Grok pattern configuration string found for group: {group_name}"
        )
        return None
    return str(pattern_config["grok_pattern"])


def compile_grok_instance(
    group_name_for_caching: str, pattern_string: str
) -> Optional[Grok]:
    if not pattern_string:
        print(
            f"WARNING: Cannot compile Grok instance for '{group_name_for_caching}': No pattern string provided."
        )
        return None
    try:
        # You can add custom pattern directories if your Grok patterns in YAML
        # reference custom pattern definitions not built into pygrok.
        # Example: Grok(pattern_string, custom_patterns_dir='./my_custom_patterns')
        grok_instance = Grok(pattern_string)
        print(
            f"DEBUG: Successfully compiled Grok pattern for '{group_name_for_caching}'."
        )
        return grok_instance
    except Exception as e:
        print(
            f"ERROR: Failed to compile Grok pattern string '{pattern_string}' (for group '{group_name_for_caching}'). Error: {e}"
        )
        return None


# --- Main Test Logic ---
def main_test():
    grok_patterns_config = load_grok_patterns_from_yaml(GROK_PATTERNS_YAML_PATH)
    if not grok_patterns_config:
        print("Exiting due to failure in loading Grok patterns.")
        return

    print("\n--- Starting Grok Pattern Test ---")

    for group_name, log_lines in SAMPLE_LOGS_TO_TEST.items():
        print(f"\n--- Testing Group: '{group_name}' ---")

        pattern_string = get_grok_pattern_string_for_group(
            grok_patterns_config, group_name
        )

        if not pattern_string:
            print(f"SKIPPED: No pattern string found for group '{group_name}' in YAML.")
            for i, line in enumerate(log_lines):
                print(f"  Line {i+1}: (No Pattern Attempted) '{line}'")
            continue

        print(f"  Using Pattern: |{pattern_string.strip()}|")
        grok_instance = compile_grok_instance(group_name, pattern_string)

        if not grok_instance:
            print(f"SKIPPED: Failed to compile Grok pattern for group '{group_name}'.")
            for i, line in enumerate(log_lines):
                print(f"  Line {i+1}: (Compilation Failed) '{line}'")
            continue

        for i, line in enumerate(log_lines):
            print(f"  Line {i+1}: '{line}'")
            parsed_result = grok_instance.match(line)  # This is the raw dictionary
            if parsed_result:
                # Pretty print the JSON structure of the parsed result
                print(f"    PARSED  :\n{json.dumps(parsed_result, indent=4)}")
            else:
                print(f"    UNPARSED: No match found.")
        print("--- End of Group Test ---")


if __name__ == "__main__":
    main_test()
