# src/logllm/utils/data_struct.py
import hashlib  # Added import
import os  # Added import
from dataclasses import asdict, dataclass
from datetime import datetime

from ..config import config as cfg
from .database import (
    ElasticsearchDatabase as eldb,  # Assuming eldb is still needed here for LogFile methods
)


@dataclass
class BaseData:
    def to_dict(self):
        return asdict(self)


@dataclass
class LineOfLogFile(BaseData):
    content: str
    line_number: int  # 0-indexed line number in the file
    name: str  # Full path of the log file
    id: str  # Stable ID of the LogFile (hash of its path)
    # ingestion_timestamp: datetime  # Timestamp of when this line was processed/inserted


@dataclass
class LastLineRead(BaseData):
    last_line_read: int  # The number of lines read previously (i.e., next line to read is 0-indexed last_line_read)
    id: str  # Stable ID of the LogFile (hash of its path)
    name: str  # Full path of the log file


class LogFile:
    # file_id = 0 # Class variable for auto-incrementing ID is removed

    def __init__(self, filename: str, parent: str):
        # Ensure path is absolute and normalized for consistent hashing and storage
        self.path: str = os.path.abspath(os.path.normpath(filename))

        # Create a stable ID based on the file path
        self.id: str = hashlib.md5(self.path.encode("utf-8")).hexdigest()

        self.belongs_to: str = parent
        self.description: str = ""
        self.related_events: list = []  # Initialize as list

    def add_file_description(self, description: str):
        description = description.strip()  # Ensure description is stripped
        self.description = description

    def to_dict(self) -> dict:
        # Only include relevant fields for storage if LogFile itself is stored
        return {
            "id": self.id,
            "path": self.path,
            "belongs_to": self.belongs_to,
            "description": self.description,
            # related_events might be complex; decide if/how to store
        }

    def get_total_lines(self, db: eldb) -> int:
        # This counts documents in ES, which might not be the physical line count
        # if some lines were skipped or if there are multiple entries per line number (not typical).
        # It's more like "total processed log entries for this file ID".
        search_query = {
            "query": {"term": {"id.keyword": self.id}}
        }  # Assuming 'id' is mapped as keyword for term query

        try:
            count_response = db.instance.count(  # Using count API directly
                index=cfg.get_log_storage_index(
                    self.belongs_to
                ),  # Query the correct data index
                body=search_query.get(
                    "query"
                ),  # Pass only the query part to body of count
            )
            return count_response["count"]
        except Exception as e:
            # logger instance would be good here
            print(f"Error getting total lines for {self.path} (ID: {self.id}): {e}")
            return 0

    def get_snapshot(
        self,
        earliest_timestamp: datetime,
        start: int,
        size: int,
        db: eldb,  # Removed id param, use self.id
    ) -> str | None:
        """
        Get a snapshot of the log file from the database
        can return random snapshot, by providing random start and well defined size
        """

        query = {
            "size": size,  # Fetch only the required 'size'
            "from": start,  # Start from the 'start' line number (if 0-indexed)
            "query": {
                "bool": {
                    "must": [
                        # { # Timestamp filter might not be what's desired for a direct line number snapshot
                        #     "range": {
                        #         "timestamp": { # This is processing timestamp, not log's internal timestamp
                        #             "gt": earliest_timestamp.strftime(
                        #                 "%Y-%m-%dT%H:%M:%S"
                        #             )
                        #         }
                        #     }
                        # },
                        {
                            "match": {"id.keyword": self.id}
                        },  # Match on the LogFile ID (hash)
                    ]
                }
            },
            "sort": [{"line_number": "asc"}],  # Sort by actual line_number field
            "_source": ["line_number", "content"],
        }

        log_lines = []
        try:
            # Simpler search as we expect 'size' to be manageable for a snapshot
            response = db.instance.search(
                index=cfg.get_log_storage_index(self.belongs_to), body=query
            )

            for hit in response["hits"]["hits"]:
                log_lines.append(
                    f"{hit['_source']['line_number']}: {hit['_source']['content']}"
                )

        except Exception as e:
            # logger instance useful here
            print(f"Error getting snapshot for {self.path} (ID: {self.id}): {e}")
            return None

        return "".join(log_lines) if log_lines else None


class Event:
    event_id_counter = 0  # Use a more descriptive name

    def __init__(self, description: str):
        Event.event_id_counter += 1
        self.id: int = (
            Event.event_id_counter
        )  # This ID is for events, separate from LogFile.id
        self.description: str = description
        self.related_files: list = []  # Initialize as list

    def to_dict(self) -> dict:
        return self.__dict__


def main():
    pass


if __name__ == "__main__":
    main()
