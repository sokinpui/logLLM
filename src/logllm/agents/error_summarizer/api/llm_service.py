# src/logllm/agents/error_summarizer/api/llm_service.py
import json
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, ValidationError

from ....utils.llm_model import LLMModel
from ....utils.logger import Logger
from ..states import LogClusterSummaryOutput


class LLMService:
    def __init__(self, llm_model_instance: LLMModel, logger: Optional[Logger] = None):
        self.llm_model = llm_model_instance
        self._logger = logger or Logger()

    def _build_cluster_summary_prompt(
        self,
        cluster_size: int,
        unique_message_count: int,
        time_range_start: Optional[str],
        time_range_end: Optional[str],
        sample_log_lines: List[str],
        most_frequent_message: Optional[str] = None,
        most_frequent_count: int = 0,
        group_name: Optional[str] = None,
    ) -> str:
        sample_lines_str = "\n".join([f"- {line.strip()}" for line in sample_log_lines])

        time_range_str = "N/A"
        if time_range_start and time_range_end:
            time_range_str = f"{time_range_start} to {time_range_end}"
        elif time_range_start:
            time_range_str = f"Since {time_range_start}"
        elif time_range_end:
            time_range_str = f"Until {time_range_end}"

        prompt = f"""You are an expert log analysis assistant.
Analyze the following log entries, which form a cluster of similar errors from log group '{group_name or 'unknown'}'.

Cluster Information:
- Total logs in this cluster: {cluster_size}
- Number of unique message variations in this cluster: {unique_message_count}
- Time range of logs in this cluster: {time_range_str}
"""
        if most_frequent_message and most_frequent_count > 0:
            prompt += f'- Most frequent message (occurred {most_frequent_count} times):\n  "{most_frequent_message.strip()}"\n'

        prompt += f"""
Sample Log Lines (up to {len(sample_log_lines)} distinct samples provided):
{sample_lines_str}

Your Task:
Based *only* on the provided information and sample log lines, perform the following:
1.  **Summary**: Write a concise, one or two sentence summary describing the core error or issue represented by this cluster.
2.  **Potential Cause**: If possible to infer from the samples, suggest a brief potential root cause. If not clear, state "Undetermined".
3.  **Keywords**: Provide 3-5 relevant keywords or tags that categorize this error cluster (e.g., "authentication_failure", "database_connection", "null_pointer_exception", "resource_limit").
4.  **Representative Log Line**: Select one single log line from the samples that you believe is most representative of the core issue. If multiple are equally good, pick the shortest one that still captures the essence.

Return your analysis STRICTLY in the following JSON format. Do not add any text before or after the JSON object.
{{
  "summary": "Your summary here.",
  "potential_cause": "Your potential cause here, or 'Undetermined'.",
  "keywords": ["keyword1", "keyword2", "keyword3"],
  "representative_log_line": "The single most representative log line from the samples."
}}
"""
        return prompt

    def generate_structured_summary(
        self,
        cluster_info: Dict[str, Any],
        group_name: Optional[str] = None,
    ) -> Optional[LogClusterSummaryOutput]:

        prompt = self._build_cluster_summary_prompt(
            cluster_size=cluster_info.get("size", 0),
            unique_message_count=cluster_info.get("unique_message_count", 0),
            time_range_start=cluster_info.get("time_range_start"),
            time_range_end=cluster_info.get("time_range_end"),
            sample_log_lines=cluster_info.get("sampled_logs_content", []),
            most_frequent_message=cluster_info.get("most_frequent_message"),
            most_frequent_count=cluster_info.get("most_frequent_count", 0),
            group_name=group_name,
        )
        self._logger.debug(
            f"Generated LLM prompt for cluster summary (first 500 chars):\n{prompt[:500]}..."
        )

        try:
            response = self.llm_model.generate(prompt, schema=LogClusterSummaryOutput)

            if isinstance(response, LogClusterSummaryOutput):
                self._logger.info(
                    f"Successfully generated and validated structured summary for cluster."
                )
                return response
            elif isinstance(response, str):
                self._logger.warning(
                    "LLM returned a string instead of structured LogClusterSummaryOutput. Attempting to parse as JSON."
                )
                try:
                    clean_response = response.strip()
                    if clean_response.startswith("```json"):
                        clean_response = clean_response[7:]
                    if clean_response.endswith("```"):
                        clean_response = clean_response[:-3]

                    data = json.loads(clean_response)
                    validated_response = LogClusterSummaryOutput.model_validate(data)
                    self._logger.info(
                        "Successfully parsed and validated string response as LogClusterSummaryOutput."
                    )
                    return validated_response
                except (
                    json.JSONDecodeError,
                    ValidationError,
                ) as e:
                    self._logger.error(
                        f"Failed to parse or validate LLM string response as JSON: {e}. Response: {response[:500]}"
                    )
                    return None
            elif response is None:
                self._logger.warning(
                    "LLM generation returned None (e.g. content blocked or empty)."
                )
                return None
            else:
                self._logger.error(
                    f"LLM generation returned unexpected type: {type(response)}. Response: {str(response)[:200]}"
                )
                return None
        except Exception as e:
            self._logger.error(
                f"Error during LLM summary generation: {e}", exc_info=True
            )
            return None
