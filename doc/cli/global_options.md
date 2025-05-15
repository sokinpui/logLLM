# logLLM CLI: Global Options

These global options can be used with any `logLLM` command (e.g., `db`, `collect`, `pm`) and **must be placed _before_ the main command name** in your command line invocation.

## `--verbose`

Enables detailed, application-wide logging output. This affects both the console output and the messages written to the log file (default: `movelook.log`). It's useful for debugging and understanding the internal operations of the system.

**Usage:**

```bash
python -m src.logllm --verbose <command> [command_options]
```

**Example:**

```bash
python -m src.logllm --verbose collect -d ./logs
```

This will show more granular log messages from the `Collector` and `ElasticsearchDatabase` utilities during the collection process.

## `--test`

Instructs `logLLM` to use a specific test prompt file, `prompts/test.json`, for any command that interacts with the `PromptsManager` class. This typically includes commands like `pm` (all actions), `parse` (when generating Grok patterns for single files), and `es-parse` (when generating Grok patterns).

This option is useful for experimenting with prompt changes or testing new prompt structures without affecting your primary production prompt file (`prompts/prompts.json`).

**Note:** The `--test` option is overridden if the `-j`/`--json` option is also used.

**Usage:**

```bash
python -m src.logllm --test <command_using_prompts> [command_options]
```

**Example:**

```bash
# List prompts from prompts/test.json
python -m src.logllm --test pm list

# Run Elasticsearch-based parsing using prompts from prompts/test.json
python -m src.logllm --test es-parse run -g apache
```

## `-j PATH`, `--json PATH`

Allows you to specify a custom JSON file path to be used by the `PromptsManager`. This provides maximum flexibility for managing different sets of prompts for various projects or experiments.

- The directory containing the custom JSON file must exist.
- The `PromptsManager` will attempt to use this file and its directory for Git-based version control, just like the default file.
- This option overrides both the default prompt file (`prompts/prompts.json`) and the `--test` option if present.

**Usage:**

```bash
python -m src.logllm -j /path/to/your/custom_prompts.json <command_using_prompts> [command_options]
```

or

```bash
python -m src.logllm --json ./project_specific_prompts/prompts_v2.json <command_using_prompts> [command_options]
```

**Example:**

```bash
# Scan agents directory and update prompts in 'my_experimental_prompts.json'
python -m src.logllm -j ./my_experimental_prompts.json pm scan -d src/logllm/agents -r
```
