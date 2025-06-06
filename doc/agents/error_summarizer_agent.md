# Error Summarizer Agent (`error_summarizer_agent.py`)

## File: `src/logllm/agents/error_summarizer_agent.py`

### Overview

The `ErrorSummarizerAgent` takes a list of sampled error `LogDocument` objects (which typically represent a single error cluster or a batch of unclustered errors) and uses a Large Language Model (LLM) to generate a structured summary. This summary adheres to the `ErrorSummarySchema`.

For a general overview of the error analysis pipeline, related configurations, and data structures, see [../error_analysis_overview.md](../error_analysis_overview.md).

### Core Logic

1.  **Formats Input**: The provided `LogDocument` samples are formatted into a text block suitable for an LLM prompt. This usually includes the timestamp and the error message for each sample.
2.  **Constructs Prompt**: A detailed prompt is constructed using templates managed by `PromptsManager`.
    - The prompt includes the formatted log samples, the number of samples, and contextual information (like `group_name`).
    - If the samples come from a cluster (indicated by `cluster_context`), additional details like the cluster's representative message, total count, and overall first/last occurrence times are included in the prompt variables.
    - Different prompt templates can be used for summarizing clustered errors versus a general batch of unclustered errors (e.g., keys like `"error_analysis.summarize_clustered_error"` and `"error_analysis.summarize_unclustered_error"` in `prompts.json`).
3.  **LLM Interaction**: Calls the `generate` method of the provided `LLMModel` (e.g., `GeminiModel`), instructing it to use the `ErrorSummarySchema` for structured JSON output.
4.  **Processes Output**:
    - If the LLM returns a valid response that successfully validates against the `ErrorSummarySchema` (Pydantic model), the agent proceeds.
    - The agent then augments this Pydantic object with some metadata not directly generated by the LLM but relevant to the summary, such as the `group_name`, the actual number of input examples (`num_examples_in_summary_input`), the original cluster count (if applicable), and the first/last occurrence timestamps from the input samples.
    - The `analysis_timestamp` is automatically generated.
5.  **Returns Summary**: The completed `ErrorSummarySchema` object is returned.

### Key Methods

- **`__init__(self, llm_model: LLMModel, prompts_manager: PromptsManager)`**

  - Initializes the agent with an `LLMModel` instance for text generation and a `PromptsManager` instance for retrieving prompt templates.

- **`run(self, group_name: str, log_samples_docs: List[LogDocument], cluster_context: Optional[Dict[str, Any]] = None) -> Optional[ErrorSummarySchema]`**

  - **Description**: The main execution method for generating a summary.
  - **Parameters**:
    - `group_name` (str): The name of the log group these errors belong to.
    - `log_samples_docs` (List[LogDocument]): A list of `LogDocument` objects to be summarized.
    - `cluster_context` (Optional[Dict[str, Any]]): If the samples are from a distinct cluster, this dictionary provides additional context. Expected keys include:
      - `representative_message` (str): A sample message typifying the cluster.
      - `count` (int): The total number of logs in the original cluster.
      - `first_occurrence_ts` (Optional[str]): ISO timestamp of the earliest log in the cluster.
      - `last_occurrence_ts` (Optional[str]): ISO timestamp of the latest log in the cluster.
  - **Returns**: (Optional[ErrorSummarySchema]): A Pydantic `ErrorSummarySchema` object containing the structured summary if successful, or `None` if summarization fails or no samples are provided.

- **`_format_log_samples_for_prompt(self, log_docs: List[LogDocument]) -> str`**
  - **Description**: An internal helper method to convert a list of `LogDocument` objects into a single formatted string block for inclusion in the LLM prompt.
  - **Returns**: (str): The formatted string of log samples.

### Data Structures & Prompts

- **`ErrorSummarySchema`**: Defined in `src/logllm/data_schemas/error_analysis.py`. This Pydantic model dictates the structure of the LLM's output. See [../error_analysis_overview.md](../error_analysis_overview.md) for details.
- **Prompts**: The agent relies on prompt templates stored in the JSON file managed by `PromptsManager` (e.g., `prompts/prompts.json`). Example prompt keys might be:
  - `src.logllm.agents.error_summarizer_agent.ErrorSummarizerAgent.summarize_clustered`
  - `src.logllm.agents.error_summarizer_agent.ErrorSummarizerAgent.summarize_unclustered`
    These prompts should guide the LLM to provide information matching the fields in `ErrorSummarySchema` and utilize variables like `{log_extracts}`, `{num_examples}`, `{group_name}`, `{error_type_description}`, `{total_occurrences}`, `{first_occurrence}`, and `{last_occurrence}`.
