# src/logllm/utils/collector.py

import hashlib
import os
from abc import ABC, abstractmethod
from datetime import datetime  # Still needed for fallback timestamps elsewhere

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError

from ..config import config as cfg
from . import data_struct
from .data_struct import (
    Event,
    LineOfLogFile,
    LogFile,
)
from .database import Database, ElasticsearchDatabase
from .logger import Logger

## data structure used in database


class Collector:
    def __init__(self, dir: str):
        self._logger = Logger()
        self._base_directory = os.path.abspath(os.path.normpath(dir))
        self._logger.info(
            f"Collector initialized with base directory: {self._base_directory}"
        )

        self._dir = self._base_directory
        self.collected_files = self.collect_logs(self._dir)

        _db = ElasticsearchDatabase()
        groups = self.group_files(self.collected_files)
        self.insert_group_to_db(groups, _db)

    def insert_group_to_db(self, groups: dict[str, list[str]], db: Database):
        db.instance.indices.delete(index=cfg.INDEX_GROUP_INFOS, ignore=[400, 404])
        id_counter = 0
        for group, files in groups.items():
            self._logger.info(f"Updating group info for: {group}")
            relative_file_paths = [
                os.path.relpath(f, self._base_directory) for f in files
            ]
            doc = {"group": group, "files": relative_file_paths, "id": id_counter}
            id_counter += 1
            db.insert(doc, cfg.INDEX_GROUP_INFOS)

    def group_files(self, files: list[LogFile]) -> dict[str, list[str]]:
        group = {}
        for file in files:
            if file.belongs_to in group:
                group[file.belongs_to].append(file.path)
            else:
                group[file.belongs_to] = [file.path]
        return group

    def collect_logs(self, directory: str) -> list[LogFile]:
        log_files = []
        self._logger.info(f"Collecting logs from: {directory}")

        for item in os.listdir(directory):
            if item.startswith("."):
                continue
            item_path = os.path.join(directory, item)
            if os.path.isfile(item_path):
                if item.lower().endswith((".log", ".txt", ".gz")):
                    log_file = LogFile(item_path, os.path.basename(directory))
                    log_files.append(log_file)
                continue
            if os.path.isdir(item_path):
                for root, dirs, files_in_subdir in os.walk(item_path):
                    dirs[:] = [d for d in dirs if not d.startswith(".")]
                    for log_filename in files_in_subdir:
                        if log_filename.lower().endswith((".log", ".txt", ".gz")):
                            try:
                                full_log_path = os.path.join(root, log_filename)
                                log_file = LogFile(
                                    full_log_path, os.path.basename(item_path)
                                )
                                log_files.append(log_file)
                            except Exception as e:
                                self._logger.error(
                                    f"Error collecting log file {log_filename}: {e}"
                                )
                                print(f"Error collecting log file {log_filename}: {e}")
        self._logger.info(f"Collected {len(log_files)} log files.")
        return log_files

    def collect_events(self, file: str) -> list[Event]:
        events = []
        abs_file_path = os.path.abspath(os.path.normpath(file))
        with open(abs_file_path, "r") as f:
            lines = f.readlines()
        event_description = ""
        for line in lines:
            if line.strip():
                event_description += line.strip()
            else:
                if event_description:
                    event = Event(description=event_description)
                    events.append(event)
                    event_description = ""
        if event_description:
            event = Event(description=event_description)
            events.append(event)
        return events

    def insert_events_to_db(self, db: Database, events: list[Event]):
        try:
            db.instance.indices.delete(
                index=cfg.INDEX_EVENTS_STORAGE, ignore=[400, 404]
            )
        except Exception as e:
            self._logger.error(f"Error deleting events index: {e}")
            print(
                "Please check if the index exists and the connection to the Elasticsearch"
            )
            return
        for event in events:
            db.insert(event.to_dict(), cfg.INDEX_EVENTS_STORAGE)
            self._logger.info(f"collector: Inserted event {event.to_dict()}")

    def insert_logs_to_db(self, db: Database, files: list[LogFile]):
        for log_file_obj in files:
            try:
                last_line_read = self._get_last_line_read(log_file_obj, db)
            except Exception as e:
                self._logger.info(
                    f"Error getting last line read for log file {log_file_obj.path}: {e}"
                )
                last_line_read = 0
            with open(log_file_obj.path, "r") as f:
                file_lines = f.readlines()
            if last_line_read > len(file_lines):
                self._logger.warning(
                    f"File {log_file_obj.path} seems to have shrunk. Resetting last_line_read to 0."
                )
                last_line_read = 0
            for i in range(last_line_read, len(file_lines)):
                line = file_lines[i]
                relative_log_path = os.path.relpath(
                    log_file_obj.path, self._base_directory
                )
                line_of_log = data_struct.LineOfLogFile(
                    content=line,
                    line_number=i,
                    name=relative_log_path,
                    id=log_file_obj.id,
                    # ingestion_timestamp=datetime.now(), # REMOVED
                )
                db.insert(
                    line_of_log.to_dict(),
                    cfg.get_log_storage_index(log_file_obj.belongs_to),
                )
            self._save_last_line_read(log_file_obj, db, len(file_lines))
            self._logger.info(
                f"collector: Inserted {len(file_lines) - last_line_read} lines of {log_file_obj.path}, range: {last_line_read} - {len(file_lines)}"
            )

    def insert_very_large_logs_into_db(
        self, db: ElasticsearchDatabase, files: list[LogFile]
    ):
        from elasticsearch import helpers

        for file_obj in files:
            batch_size = 1000
            actions = []
            count = 0
            try:
                with open(file_obj.path, "r", errors="ignore") as f:
                    try:
                        last_line_read = self._get_last_line_read(file_obj, db)
                        self._logger.debug(
                            f"For file {file_obj.path} (ID: {file_obj.id}), last_line_read: {last_line_read}"
                        )
                    except Exception as e:
                        self._logger.warning(
                            f"Error getting last line read for log file {file_obj.path}: {e}. Defaulting to 0."
                        )
                        last_line_read = 0

                    relative_log_path = os.path.relpath(
                        file_obj.path, self._base_directory
                    )
                    for line_content in f:
                        if count < last_line_read:
                            count += 1
                            continue
                        line_of_log = data_struct.LineOfLogFile(
                            content=line_content,
                            line_number=count,
                            name=relative_log_path,
                            id=file_obj.id,
                            # ingestion_timestamp=datetime.now(), # REMOVED
                        )
                        action = {
                            "_index": cfg.get_log_storage_index(file_obj.belongs_to),
                            "_source": line_of_log.to_dict(),
                        }
                        actions.append(action)
                        if len(actions) >= batch_size:
                            helpers.bulk(db.instance, actions)
                            self._logger.debug(
                                f"Bulk inserted {len(actions)} lines for {file_obj.path}"
                            )
                            actions = []
                        count += 1
                if actions:
                    helpers.bulk(db.instance, actions)
                    self._logger.debug(
                        f"Bulk inserted remaining {len(actions)} lines for {file_obj.path}"
                    )
                total_lines_processed_in_this_run = count - last_line_read
                if total_lines_processed_in_this_run > 0:
                    self._logger.info(
                        f"collector: Inserted {total_lines_processed_in_this_run} new lines from {file_obj.path} (ID: {file_obj.id}). Total lines now: {count}. Prev read: {last_line_read}."
                    )
                elif total_lines_processed_in_this_run == 0 and count >= last_line_read:
                    self._logger.info(
                        f"collector: No new lines found in {file_obj.path} (ID: {file_obj.id}) since last read ({last_line_read} lines). Current total: {count}."
                    )
                elif count < last_line_read:
                    self._logger.warning(
                        f"File {file_obj.path} (ID: {file_obj.id}) appears to have shrunk (current: {count} lines, prev read: {last_line_read}). Resetting last_line_read to current line count."
                    )
                    self._save_last_line_read(file_obj, db, count)
                if count >= last_line_read:
                    self._save_last_line_read(file_obj, db, count)
            except FileNotFoundError:
                self._logger.error(f"File not found during insertion: {file_obj.path}")
            except Exception as e:
                self._logger.error(
                    f"Error inserting lines of {file_obj.path}: {e}", exc_info=True
                )

    def _get_last_line_read(self, log_file: LogFile, db: Database) -> int:
        try:
            doc = db.instance.get(index=cfg.INDEX_LAST_LINE_STATUS, id=log_file.id)
            return doc["_source"]["last_line_read"]
        except NotFoundError:
            self._logger.debug(
                f"No last_line_read status found for {log_file.path} (ID: {log_file.id}). Returning 0."
            )
            return 0
        except Exception as e:
            self._logger.error(
                f"Error fetching last_line_read for {log_file.path} (ID: {log_file.id}): {e}",
                exc_info=True,
            )
            return 0

    def _save_last_line_read(self, log_file: LogFile, db: Database, line_number: int):
        relative_log_path = os.path.relpath(log_file.path, self._base_directory)
        last_line_status = data_struct.LastLineRead(
            last_line_read=line_number,
            id=log_file.id,
            name=relative_log_path,
        )
        update_data = {"doc": last_line_status.to_dict(), "doc_as_upsert": True}
        try:
            db.instance.update(
                index=cfg.INDEX_LAST_LINE_STATUS, id=log_file.id, body=update_data
            )
            self._logger.debug(
                f"Saved last_line_read for {log_file.path} (ID: {log_file.id}) as {line_number} with name {relative_log_path}."
            )
        except Exception as e:
            self._logger.error(
                f"Error updating last line read for log file {log_file.path} (ID: {log_file.id}): {e}",
                exc_info=True,
            )

    def _clear_records(self, db: Database):
        self._logger.warning("Clearing ALL log file storage and last line statuses.")
        try:
            db.instance.indices.delete(
                index=cfg.INDEX_LAST_LINE_STATUS, ignore=[400, 404]
            )
            self._logger.info(f"Cleared index: {cfg.INDEX_LAST_LINE_STATUS}")
        except Exception as e:
            self._logger.error(f"Error deleting log files index: {e}")
            print(
                "Please check if the index exists and the connection to the Elasticsearch"
            )


def main():
    es_db = ElasticsearchDatabase()
    if es_db.instance is None:
        print("Failed to connect to Elasticsearch. Aborting main test.")
        return

    script_dir = os.path.dirname(__file__)
    project_root = os.path.dirname(os.path.dirname(script_dir))
    test_log_dir = os.path.join(project_root, "logs")

    if not os.path.isdir(test_log_dir):
        print(
            f"Test directory '{test_log_dir}' not found. Please create it and add sample log files for testing."
        )
        return

    print(f"Using test log directory: {test_log_dir}")
    collector = Collector(test_log_dir)

    if collector.collected_files:
        print(f"Collector found {len(collector.collected_files)} files.")
        collector.insert_very_large_logs_into_db(
            db=es_db, files=collector.collected_files
        )
        print("Finished inserting logs. Check Elasticsearch and logs for details.")
    else:
        print("No log files collected. Check the test directory and collector logic.")


if __name__ == "__main__":
    main()
