from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional


from datetime import datetime
from database import ElasticsearchDatabase as eldb
import config as cfg

@dataclass
class BaseData:
    def to_dict(self):
        return asdict(self)

@dataclass
class LineOfLogFile(BaseData):
    content: str
    line_number: int
    name: str
    id: int
    timestamp: datetime

    def to_dict(self):
        data = asdict(self)
        # Convert datetime objects to strings
        if isinstance(data['timestamp'], datetime):
            data['timestamp'] = data['timestamp'].isoformat()  # Convert to ISO 8601 format
        return data

@dataclass
class LastLineRead(BaseData):
    last_line_read: int
    id: int
    name: str

class LogFile:

    file_id = 0

    def __init__(self, filename : str, parent: str):
        LogFile.file_id += 1
        self.id = LogFile.file_id

        self.belongs_to = parent
        self.name = filename
        self.description = ""
        self.related_events = []

    def add_file_description(self, description: str):
        description.strip()
        self.description = description

    def to_dict(self) -> dict:
        return self.__dict__

    def get_total_lines(self, db: eldb) -> int:
        search_query = {
        "query": {
            "term": {
                "id": self.id
                }
            }
        }

        count_response = db.instance.search(index=cfg.INDEX_LOG_FILES_STORAGE, body=search_query, size=0)

        return count_response['hits']['total']['value']

    def get_snapshot(self, id: int, earliest_timestamp: datetime, start: int, size: int, db: eldb) -> str | None:

        """
        Get a snapshot of the log file from the database
        can return random snapshot, by providing random start and well defined size
        """

        query = {
            "size": 1000,  # Fetch in chunks
            "query": {
                "bool": {
                    "must": [
                        {"range": {"timestamp": {"gt": earliest_timestamp.strftime("%Y-%m-%dT%H:%M:%S")}}},
                        {"match": {"id": id}}
                    ]
                }
            },
            "sort": [{"line_number": "asc"}],  # Sort by line number instead of timestamp
            "_source": ["line_number", "content"]  # Only fetch necessary fields
        }

        # use scroll api to fetch all lines
        response = db.instance.search(
                index=cfg.INDEX_LOG_FILES_STORAGE,
                body=query,
                scroll="2m"
                )
        scroll_id = response["_scroll_id"]
        scroll_size = len(response["hits"]["hits"])

        log_data = {}

        while scroll_size > 0:
            for hit in response["hits"]["hits"]:
                log_data[hit["_source"]["line_number"]] = hit["_source"]["content"]
            response = db.instance.scroll(scroll_id=scroll_id, scroll="2m")
            scroll_id = response["_scroll_id"]
            scroll_size = len(response["hits"]["hits"])

        # Clear the scroll context in Elasticsearch
        db.instance.clear_scroll(scroll_id=scroll_id)

        def to_string(log_data: dict) -> str | None:
            log_string = ""
            for line_number, content in log_data.items():
                log_string += f"{line_number}: {content}"

            return log_string

        # If there's not enough data, return all available logs
        if len(log_data) <= (size):
            return to_string(log_data)

        snapshot = {}
        for i in range(start, start + size):
            snapshot[i] = log_data[i]

        return to_string(snapshot)

class Event:

    event_id = 0

    def __init__(self, description : str):
        Event.event_id += 1
        self.id = Event.event_id
        self.description = description
        self.related_files = []


    def to_dict(self) -> dict:
        return self.__dict__

def main():
    pass


if __name__ == "__main__":
    main()

