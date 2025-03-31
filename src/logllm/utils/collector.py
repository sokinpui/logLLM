from abc import ABC, abstractmethod
from elasticsearch import Elasticsearch
import os
from elasticsearch.exceptions import NotFoundError
from datetime import datetime

from logllm.config import config as cfg
from . import data_struct
from .database import Database, ElasticsearchDatabase
from .logger import Logger
from .data_struct import LogFile, Event


## data structure used in database


class Collector:

    def __init__(self, dir: str):
        self._logger = Logger()
        self._dir = dir
        self.collected_files = self.collect_logs(dir)

    def collect_logs(self, directory: str) -> list[LogFile]:

        # remove the tailing slash
        directory = directory.rstrip('/')

        log_files = []

        for item in os.listdir(directory):

            if item.startswith('.'):
                continue

            item_path = os.path.join(directory, item)

            if os.path.isfile(item_path):
                item_path = os.path.abspath(item_path)
                log_file = LogFile(item_path, os.path.basename(directory))
                log_files.append(log_file)
                continue

            for root, dirs, files in os.walk(item_path):
                dirs[:] = [d for d in dirs if not d.startswith('.')]

                for log in files:

                    try:
                        path = os.path.join(root, log)
                        log_path = os.path.abspath(path)

                        log_file = LogFile(log_path, os.path.basename(item_path))
                        log_files.append(log_file)
                    except Exception as e:
                        self._logger.error(f"Error collecting log file {log}: {e}")
                        exit(1)

        return log_files

    def collect_events(self, file: str) -> list[Event]:
        events = []

        with open(file, 'r') as f:
            lines = f.readlines()

        # grouping lines into events, split by empty line
        event_description = ""

        for line in lines:
            if line.strip():
                event_description += line.strip()
            else:
                if event_description:
                    event = Event(description=event_description)
                    events.append(event)
                    event_description = ""

        return events

    def insert_events_to_db(self, db: Database, events: list[Event]):
        # clear old record
        try:
            db.instance.indices.delete(index=cfg.INDEX_EVENTS_STORAGE, ignore=[400, 404])
        except Exception as e:
            self._logger.error(f"Error deleting events index: {e}")
            print("Please check if the index exists and the connection to the Elasticsearch")
            exit(1)

        for event in events:
            db.insert(event.to_dict(), cfg.INDEX_EVENTS_STORAGE)
            self._logger.info(f"collector: Inserted event {event.to_dict()}")

    def insert_logs_to_db(self, db: Database, files: list):
        """
        load the entire log file into memory
        be careful this may cause memory overflow if the log file is too large
        """
        for log in files:
            try:
                last_line_read = self._get_last_line_read(log, db)
            except Exception as e:
                self._logger.info(f"Error getting last line read for log file {log.name}: {e}")
                last_line_read = 0

            with open(log.name, 'r') as f:
                file_lines = f.readlines()

            if last_line_read > len(file_lines):
                last_line_read = 0

            for i in range(last_line_read, len(file_lines)):
                line = file_lines[i]
                line_of_log = data_struct.LineOfLogFile(
                        content=line,
                        line_number=i,
                        name=log.name,
                        id=log.id,
                        timestamp=datetime.now()
                )
                db.insert(line_of_log.to_dict(), cfg.get_log_stroage_index(log.belongs_to))
            self._save_last_line_read(log, db, len(file_lines))

            self._logger.info(f"collector: Inserted {len(file_lines) - last_line_read} lines of {log.name}, range: {last_line_read} - {len(file_lines)}")

    def insert_very_large_logs_into_db(self, db: ElasticsearchDatabase, files: list[LogFile]):
        """
        support for file append more line later,
        but don't support modified line being recorded
        """
        from elasticsearch import helpers

        for file in files:
            batch_size = 1000 # number of lines insert at once
            actions = []

            try:
                count = 0

                with open(file.name, 'r') as f:

                    try:
                        last_line_read = self._get_last_line_read(file, db)
                    except Exception as e:
                        self._logger.info(f"Error getting last line read for log file {file.name}: {e}")
                        last_line_read = 0

                    for line in f:

                        # skip lines read before
                        if count < last_line_read:
                            count += 1
                            continue

                        line_of_log = data_struct.LineOfLogFile(
                                content=line,
                                line_number=count,
                                name=file.name,
                                id=file.id,
                                timestamp=datetime.now()
                        )

                        action = {
                            "_index": "log_" + file.belongs_to,
                            "_source": line_of_log.to_dict()

                        }
                        actions.append(action)

                        # if the number of actions reaches the batch size, insert them into the database
                        if len(actions) >= batch_size:
                            helpers.bulk(db.instance, actions)
                            actions = [] # clear the actions list

                        count += 1

                # insert any remaining actions
                if actions:
                    helpers.bulk(db.instance, actions)

                total_lines_procced = count - last_line_read
                if total_lines_procced > 0:
                    self._logger.info(f"collector: Inserted {total_lines_procced} lines of {file.name}:id {file.id}, range: {last_line_read} - {count}")

                self._save_last_line_read(file, db, count)

            except Exception as e:
                self._logger.error(f"Error inserting lines of {file.name}: {e}")
                exit(1)



    def _get_last_line_read(self, log_file: LogFile, db: Database) -> int:
        query = {
            "query": {
                "match": {
                    "id": log_file.id
                }
            },
            "_source": ["last_line_read"]
        }
        last_line_status = db.single_search(query=query, index=cfg.INDEX_LAST_LINE_STATUS)
        if last_line_status:
            return last_line_status[0]['_source']['last_line_read']
        else:
            return 0

    def _save_last_line_read(self, log_file: LogFile, db: Database, line_number: int):
        last_line_status = data_struct.LastLineRead(
                last_line_read=line_number,
                id=log_file.id,
                name=log_file.name
        )
        update_data = {
            "doc": last_line_status.to_dict(),
            "doc_as_upsert": True
        }

        try:
            db.update(
                    index=cfg.INDEX_LAST_LINE_STATUS,
                    id=log_file.id,
                    data=update_data
                    )
        except NotFoundError:
            db.insert(data=last_line_status.to_dict(), index=cfg.INDEX_LAST_LINE_STATUS)
        except Exception as e:
            self._logger.error(f"Error updating last line read for log file {log_file.name}: {e}")
            exit(1)

    def _clear_records(self, db: Database):
        """
        prepare for interface later to change if file is being modified
        """
        try:
            db.instance.indices.delete(index=cfg.INDEX_LOG_FILES_STORAGE, ignore=[400, 404])
            db.instance.indices.delete(index=cfg.INDEX_LAST_LINE_STATUS, ignore=[400, 404])
        except Exception as e:
            self._logger.error(f"Error deleting log files index: {e}")
            print("Please check if the index exists and the connection to the Elasticsearch")
            exit(1)

def main():


    es_db = ElasticsearchDatabase()

    dir = "../log/"
    collector = Collector(dir)

    # collector.insert_logs_to_db(db=es_db, files=collector.log_files)
    collector.insert_very_large_logs_into_db(db=es_db, files=collector.collected_files)

    # import random
    # random_snapshot_size = 2
    #
    # # random snapshot
    # for file in collector.log_files:
    #     start = random.randint(0, file.get_total_lines(db=es_db)-random_snapshot_size)
    #     size = random_snapshot_size
    #
    #     snapshot = file.get_snapshot(
    #             id=file.id,
    #             earliest_timestamp=datetime(2021, 1, 1),
    #             start=start,
    #             size=size,
    #             db=es_db
    #     )
    #
    #     print(f"Snapshot of {file.name} from line {start} to {size}, total lines: {file.get_total_lines(db=es_db)}")
    #     print(snapshot)

    # from llm_model import GeminiModel
    # from llm_bot import LLMBot
    #
    # model = GeminiModel()
    # events_file = "./prompt/events.txt"
    # events = collector.collect_events(file=events_file)
    #
    # bot = LLMBot(model=model, db=es_db)
    # events = bot.naming_events(events)
    #
    # collector.insert_events_to_db(db=es_db, events=events)


if __name__ == "__main__":
    main()
