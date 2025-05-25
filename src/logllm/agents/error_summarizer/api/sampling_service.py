# src/logllm/agents/error_summarizer/api/sampling_service.py
import random
from collections import Counter
from typing import Any, Dict, List, Optional

from ....utils.logger import Logger


class LogSamplingService:
    def __init__(self, logger: Optional[Logger] = None):
        self._logger = logger or Logger()

    def get_cluster_metadata_and_samples(
        self,
        logs_in_cluster: List[Dict[str, Any]],  # List of original log dicts
        log_messages_in_cluster: List[str],  # Corresponding messages
        log_timestamps_in_cluster: List[str],  # Corresponding timestamps
        max_samples: int = 5,
        content_field: str = "message",
    ) -> Dict[str, Any]:
        """
        Analyzes a cluster of logs to extract metadata and samples.
        """
        if not logs_in_cluster:
            return {
                "size": 0,
                "unique_message_count": 0,
                "time_range_start": None,
                "time_range_end": None,
                "sampled_logs_content": [],
                "sampled_logs_full": [],
                "most_frequent_message": None,
                "most_frequent_count": 0,
            }

        # Time range
        sorted_timestamps = sorted([ts for ts in log_timestamps_in_cluster if ts])
        time_range_start = sorted_timestamps[0] if sorted_timestamps else None
        time_range_end = sorted_timestamps[-1] if sorted_timestamps else None

        # Unique messages
        message_counts = Counter(log_messages_in_cluster)
        unique_message_count = len(message_counts)
        most_frequent = message_counts.most_common(1)
        most_frequent_message = most_frequent[0][0] if most_frequent else None
        most_frequent_count = most_frequent[0][1] if most_frequent else 0

        # Sampling: Prioritize unique messages, then random if more samples needed
        sampled_logs_content: List[str] = []
        sampled_logs_full: List[Dict[str, Any]] = []

        unique_logs_for_sampling = []
        seen_messages_for_sampling = set()
        for i, log_doc in enumerate(logs_in_cluster):
            msg = log_messages_in_cluster[i]
            if msg not in seen_messages_for_sampling:
                unique_logs_for_sampling.append(log_doc)
                seen_messages_for_sampling.add(msg)

        # Shuffle unique logs to get diverse samples if there are many unique ones
        random.shuffle(unique_logs_for_sampling)

        for log_doc in unique_logs_for_sampling:
            if len(sampled_logs_content) < max_samples:
                sampled_logs_content.append(log_doc.get(content_field, ""))
                sampled_logs_full.append(log_doc)
            else:
                break

        # If more samples are needed and we have more logs than samples taken, pick randomly from remaining
        if len(sampled_logs_content) < max_samples and len(logs_in_cluster) > len(
            sampled_logs_content
        ):
            remaining_logs_to_sample_from = [
                log
                for log in logs_in_cluster
                if log not in sampled_logs_full  # Avoid re-sampling same doc obj
            ]
            num_more_samples_needed = max_samples - len(sampled_logs_content)
            if remaining_logs_to_sample_from:
                additional_samples_full = random.sample(
                    remaining_logs_to_sample_from,
                    min(num_more_samples_needed, len(remaining_logs_to_sample_from)),
                )
                sampled_logs_full.extend(additional_samples_full)
                sampled_logs_content.extend(
                    [s.get(content_field, "") for s in additional_samples_full]
                )

        return {
            "size": len(logs_in_cluster),
            "unique_message_count": unique_message_count,
            "time_range_start": time_range_start,
            "time_range_end": time_range_end,
            "sampled_logs_content": sampled_logs_content,
            "sampled_logs_full": sampled_logs_full,  # For potential deeper inspection later
            "most_frequent_message": most_frequent_message,
            "most_frequent_count": most_frequent_count,
        }
