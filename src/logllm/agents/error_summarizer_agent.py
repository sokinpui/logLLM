# src/logllm/agents/error_summarizer_agent.py (NEW FILE)
from typing import List, Dict, Any, Optional

from ..utils.llm_model import LLMModel
from ..utils.prompts_manager import PromptsManager
from ..utils.logger import Logger
from ..data_schemas.error_analysis import (
    ErrorSummarySchema,
    LogDocument,
)  # Assuming new schema file


class ErrorSummarizerAgent:
    def __init__(self, llm_model: LLMModel, prompts_manager: PromptsManager):
        self.llm_model = llm_model
        self.prompts_manager = prompts_manager
        self.logger = Logger()

    def _format_log_samples_for_prompt(self, log_docs: List[LogDocument]) -> str:
        formatted_samples = []
        for i, doc in enumerate(log_docs):
            # Include timestamp and message, maybe other key fields if available
            ts = doc["_source"].get("@timestamp", "N/A")
            msg = doc["_source"].get("message", "Log message missing.")
            # You might want to add other fields like 'class_name', 'thread_name' if they exist
            # and are useful for the LLM's understanding.
            formatted_samples.append(f"Example {i+1} (Timestamp: {ts}):\n{msg}\n---")
        return "\n".join(formatted_samples)

    def run(
        self,
        group_name: str,
        log_samples_docs: List[LogDocument],
        cluster_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[ErrorSummarySchema]:
        """
        Generates a summary for a list of log document samples.
        cluster_context can contain: representative_message, count, first_occurrence_ts, last_occurrence_ts
        """
        if not log_samples_docs:
            self.logger.warning("No log samples provided to summarizer. Skipping.")
            return None

        num_samples = len(log_samples_docs)
        formatted_log_text = self._format_log_samples_for_prompt(log_samples_docs)

        first_ts_in_input = log_samples_docs[0]["_source"].get("@timestamp")
        last_ts_in_input = (
            log_samples_docs[-1]["_source"].get("@timestamp")
            if num_samples > 0
            else first_ts_in_input
        )

        prompt_variables = {
            "log_extracts": formatted_log_text,
            "num_examples": str(num_samples),
            "group_name": group_name,
        }

        is_clustered = False
        if cluster_context:
            is_clustered = True
            prompt_variables["error_type_description"] = cluster_context.get(
                "representative_message", "multiple related errors"
            )
            prompt_variables["total_occurrences"] = str(
                cluster_context.get("count", num_samples)
            )
            # Use cluster's overall first/last occurrence if available, else use sample's
            prompt_variables["first_occurrence"] = cluster_context.get(
                "first_occurrence_ts", first_ts_in_input
            )
            prompt_variables["last_occurrence"] = cluster_context.get(
                "last_occurrence_ts", last_ts_in_input
            )
        else:
            prompt_variables["error_type_description"] = "a batch of errors"
            prompt_variables["total_occurrences"] = str(
                num_samples
            )  # For unclustered, total is num_samples
            prompt_variables["first_occurrence"] = first_ts_in_input
            prompt_variables["last_occurrence"] = last_ts_in_input

        try:
            # Use a specific prompt key. You'll need to create this in your prompts.json
            # Example key: "agents.error_summarizer_agent.ErrorSummarizerAgent.run"
            # The prompt should guide the LLM to use the ErrorSummarySchema
            # and use variables like {log_extracts}, {num_examples}, {error_type_description}, {total_occurrences}
            prompt_template_name_key_part = (
                "run_clustered" if is_clustered else "run_unclustered"
            )
            # Adjust the key to match how PromptsManager resolves it.
            # This might require a specific metadata string if not calling from within this agent's method directly.
            # For simplicity, assuming a direct key for now.
            # e.g. self.prompts_manager.get_prompt(metadata=f"your_module_path.ErrorSummarizerAgent.{prompt_template_name_key_part}", **prompt_variables)
            # A simpler way is to have keys like:
            # "error_analysis.summarize_clustered_error"
            # "error_analysis.summarize_unclustered_error"
            prompt_key = f"error_analysis.summarize_{'clustered' if is_clustered else 'unclustered'}_error"

            # This call will use the PromptsManager's auto-resolution if called from a method named 'run_clustered' or 'run_unclustered'
            # Or, you explicitly provide metadata:
            # metadata_key = f"src.logllm.agents.error_summarizer_agent.ErrorSummarizerAgent.{'run_clustered' if is_clustered else 'run_unclustered'}"

            summary_prompt = self.prompts_manager.get_prompt(
                metadata=f"src.logllm.agents.error_summarizer_agent.ErrorSummarizerAgent.{'summarize_clustered' if is_clustered else 'summarize_unclustered'}",  # Adjust based on your structure
                **prompt_variables,
            )

            self.logger.info(
                f"Generating summary for {num_samples} samples. Clustered: {is_clustered}. Prompt key used: (auto-resolved or similar to {prompt_key})"
            )

            llm_response = self.llm_model.generate(
                summary_prompt, schema=ErrorSummarySchema
            )

            if isinstance(llm_response, ErrorSummarySchema):
                # Augment with details not directly from LLM if they were not part of schema
                llm_response.num_examples_in_summary_input = num_samples
                llm_response.original_cluster_count = (
                    cluster_context.get("count") if cluster_context else num_samples
                )
                llm_response.first_occurrence_in_input = first_ts_in_input
                llm_response.last_occurrence_in_input = last_ts_in_input
                llm_response.group_name = group_name
                self.logger.info(
                    f"Successfully generated and validated error summary for group '{group_name}'."
                )
                return llm_response
            else:
                self.logger.error(
                    f"LLM did not return a valid ErrorSummarySchema object. Response: {llm_response}"
                )
                return None
        except KeyError as e:
            self.logger.error(
                f"Prompt key error for summarization: {e}. Make sure the prompt exists in your prompts file.",
                exc_info=True,
            )
            return None
        except ValueError as e:  # Catches missing/extra vars for prompt
            self.logger.error(
                f"Prompt variable error during summarization: {e}", exc_info=True
            )
            return None
        except Exception as e:
            self.logger.error(f"Error during LLM summarization: {e}", exc_info=True)
            return None


# Example prompts to add to prompts/prompts.json (adjust keys as needed):
# "src.logllm.agents.error_summarizer_agent.ErrorSummarizerAgent.summarize_clustered":
# """You are an expert Log Analyst. Based on the following {num_examples} example log lines,
# which are representative of an error type described as '{error_type_description}'
# that occurred {total_occurrences} times between {first_occurrence} and {last_occurrence} in group '{group_name}',
# provide a structured summary. The raw log extracts are:
# {log_extracts}
#
# Output your analysis in the required JSON format.
# """,
# "src.logllm.agents.error_summarizer_agent.ErrorSummarizerAgent.summarize_unclustered":
# """You are an expert Log Analyst. Based on the following {num_examples} example error log lines
# from group '{group_name}', occurring between {first_occurrence} and {last_occurrence},
# provide a structured summary. The raw log extracts are:
# {log_extracts}
#
# Output your analysis in the required JSON format.
# """
