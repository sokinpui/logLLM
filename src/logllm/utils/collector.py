# src/logllm/utils/collector.py

import hashlib  # <--- Added import
import os
from abc import ABC, abstractmethod
from datetime import datetime

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError

from ..config import config as cfg
from . import data_struct  # Redundant if LogFile, Event are imported directly below
from .data_struct import Event, LogFile
from .database import Database, ElasticsearchDatabase
from .logger import Logger

## data structure used in database


class Collector:
    def __init__(self, dir: str):
        self._logger = Logger()
        self._dir = dir
        self.collected_files = self.collect_logs(dir)

        _db = ElasticsearchDatabase()
        groups = self.group_files(self.collected_files)
        self.insert_group_to_db(groups, _db)

    def insert_group_to_db(self, groups: dict[str, list[str]], db: Database):
        ## delete the index
        db.instance.indices.delete(index=cfg.INDEX_GROUP_INFOS, ignore=[400, 404])
        id_counter = (
            0  # Use a local counter for document _id if needed, or let ES auto-generate
        )
        for group, files in groups.items():
            # print(group) # Original print
            self._logger.info(f"Updating group info for: {group}")
            # The 'id' field here is for the document in INDEX_GROUP_INFOS, not related to LogFile.id
            doc = {"group": group, "files": files, "id": id_counter}
            id_counter += 1
            db.insert(doc, cfg.INDEX_GROUP_INFOS)

    def group_files(self, files: list[LogFile]) -> dict[str, list[str]]:
        """
        group files by their parent directory
        """
        group = {}
        for file in files:
            if file.belongs_to in group:
                group[file.belongs_to].append(file.path)
            else:
                group[file.belongs_to] = [file.path]

        return group

    def collect_logs(self, directory: str) -> list[LogFile]:
        # remove the tailing slash
        directory = directory.rstrip("/")

        log_files = []

        for item in os.listdir(directory):
            if item.startswith("."):
                continue

            item_path = os.path.join(directory, item)

            if os.path.isfile(item_path):
                # Consider only log files, not all files. Adjust extensions if needed.
                if item.lower().endswith(
                    (".log", ".txt", ".gz")
                ):  # Consistent with analyze-structure
                    # item_path = os.path.abspath(item_path) # path is already absolute via LogFile constructor
                    log_file = LogFile(item_path, os.path.basename(directory))
                    log_files.append(log_file)
                continue  # Go to next item in directory

            # If item_path is a directory, walk through it
            for root, dirs, files_in_subdir in os.walk(item_path):
                dirs[:] = [d for d in dirs if not d.startswith(".")]  # Skip hidden dirs

                for log_filename in files_in_subdir:
                    # Consider only log files. Adjust extensions if needed.
                    if log_filename.lower().endswith((".log", ".txt", ".gz")):
                        try:
                            full_log_path = os.path.join(root, log_filename)
                            # full_log_path = os.path.abspath(path) # path is already absolute via LogFile constructor

                            # belongs_to is the top-level subdirectory under the initial 'directory'
                            log_file = LogFile(
                                full_log_path, os.path.basename(item_path)
                            )
                            log_files.append(log_file)
                        except Exception as e:
                            self._logger.error(
                                f"Error collecting log file {log_filename}: {e}"
                            )
                            # Decide if to exit or continue: exit(1) might be too harsh
                            # For now, let's log and continue with other files.
                            print(f"Error collecting log file {log_filename}: {e}")

        return log_files

    def collect_events(self, file: str) -> list[Event]:
        events = []

        with open(file, "r") as f:
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
        # Add last event if file doesn't end with empty line
        if event_description:
            event = Event(description=event_description)
            events.append(event)

        return events

    def insert_events_to_db(self, db: Database, events: list[Event]):
        # clear old record
        try:
            db.instance.indices.delete(
                index=cfg.INDEX_EVENTS_STORAGE, ignore=[400, 404]
            )
        except Exception as e:
            self._logger.error(f"Error deleting events index: {e}")
            print(
                "Please check if the index exists and the connection to the Elasticsearch"
            )
            # exit(1) # Might be too harsh
            return

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
                self._logger.info(
                    f"Error getting last line read for log file {log.path}: {e}"  # Changed log.name to log.path
                )
                last_line_read = 0

            with open(log.path, "r") as f:  # Changed log.name to log.path
                file_lines = f.readlines()

            if last_line_read > len(file_lines):  # This could happen if file shrunk
                self._logger.warning(
                    f"File {log.path} seems to have shrunk. Resetting last_line_read to 0."
                )
                last_line_read = 0

            for i in range(last_line_read, len(file_lines)):
                line = file_lines[i]
                line_of_log = data_struct.LineOfLogFile(
                    content=line,
                    line_number=i,  # This is 0-indexed line number
                    name=log.path,  # Changed log.name to log.path
                    id=log.id,  # This is the stable LogFile ID
                    ingestion_timestamp=datetime.now(),
                )
                db.insert(
                    line_of_log.to_dict(), cfg.get_log_storage_index(log.belongs_to)
                )
            self._save_last_line_read(
                log, db, len(file_lines)
            )  # Save total lines processed

            self._logger.info(
                f"collector: Inserted {len(file_lines) - last_line_read} lines of {log.path}, range: {last_line_read} - {len(file_lines)}"
            )

    def insert_very_large_logs_into_db(
        self, db: ElasticsearchDatabase, files: list[LogFile]
    ):
        """
        support for file append more line later,
        but don't support modified line being recorded
        """
        from elasticsearch import helpers

        for (
            file_obj
        ) in files:  # Renamed file to file_obj to avoid conflict with open's file
            batch_size = 1000  # number of lines insert at once
            actions = []

            try:
                count = 0  # This will be the 0-indexed line number from the start of the file

                with open(
                    file_obj.path, "r", errors="ignore"
                ) as f:  # Use errors='ignore' for robustness
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

                    # If file shrunk, reset last_line_read
                    # This check is harder here as we don't know total lines upfront without reading all
                    # However, if last_line_read seems too high, it's safer to reset.
                    # For now, we'll rely on the loop logic. If `count` never reaches `last_line_read`
                    # because the file is shorter, nothing new will be read, which is fine.

                    for line_content in f:
                        # skip lines read before
                        if count < last_line_read:
                            count += 1
                            continue

                        # Now `count` is >= `last_line_read`, so this is a new line
                        line_of_log = data_struct.LineOfLogFile(
                            content=line_content,  # Changed line to line_content
                            line_number=count,  # current 0-indexed line number
                            name=file_obj.path,
                            id=file_obj.id,  # Stable LogFile ID
                            ingestion_timestamp=datetime.now(),
                        )

                        action = {
                            "_index": cfg.get_log_storage_index(
                                file_obj.belongs_to
                            ),  # <--- Use config function
                            "_source": line_of_log.to_dict(),
                        }
                        actions.append(action)

                        # if the number of actions reaches the batch size, insert them into the database
                        if len(actions) >= batch_size:
                            helpers.bulk(db.instance, actions)
                            self._logger.debug(
                                f"Bulk inserted {len(actions)} lines for {file_obj.path}"
                            )
                            actions = []  # clear the actions list

                        count += 1  # Increment after processing the line (count becomes total lines read so far)

                # insert any remaining actions
                if actions:
                    helpers.bulk(db.instance, actions)
                    self._logger.debug(
                        f"Bulk inserted remaining {len(actions)} lines for {file_obj.path}"
                    )

                # total_lines_processed_in_this_run refers to lines actually sent to ES
                total_lines_processed_in_this_run = count - last_line_read
                if (
                    total_lines_processed_in_this_run > 0
                ):  # Log only if new lines were processed
                    self._logger.info(
                        f"collector: Inserted {total_lines_processed_in_this_run} new lines from {file_obj.path} (ID: {file_obj.id}). Total lines now: {count}. Prev read: {last_line_read}."
                    )
                elif total_lines_processed_in_this_run == 0 and count >= last_line_read:
                    self._logger.info(
                        f"collector: No new lines found in {file_obj.path} (ID: {file_obj.id}) since last read ({last_line_read} lines). Current total: {count}."
                    )
                elif count < last_line_read:  # File shrunk
                    self._logger.warning(
                        f"File {file_obj.path} (ID: {file_obj.id}) appears to have shrunk (current: {count} lines, prev read: {last_line_read}). Resetting last_line_read to current line count."
                    )
                    self._save_last_line_read(
                        file_obj, db, count
                    )  # Save the new, smaller line count
                    # No new lines inserted.

                # Always save the current total line count as the next starting point
                # unless file shrunk and already handled
                if count >= last_line_read:
                    self._save_last_line_read(file_obj, db, count)

            except FileNotFoundError:
                self._logger.error(f"File not found during insertion: {file_obj.path}")
                # Decide if to exit or continue
            except Exception as e:
                self._logger.error(
                    f"Error inserting lines of {file_obj.path}: {e}", exc_info=True
                )
                # exit(1) # Might be too harsh

    def _get_last_line_read(self, log_file: LogFile, db: Database) -> int:
        # The document ID in INDEX_LAST_LINE_STATUS is log_file.id (which is now a hash)
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
            return 0  # Fallback to 0 on other errors

    def _save_last_line_read(self, log_file: LogFile, db: Database, line_number: int):
        # line_number is the total number of lines processed/seen in the file so far.
        # It's the count of lines (0-indexed line_number + 1).
        last_line_status = data_struct.LastLineRead(
            last_line_read=line_number, id=log_file.id, name=log_file.path
        )
        # Document ID for update is log_file.id (the hash)
        update_data = {"doc": last_line_status.to_dict(), "doc_as_upsert": True}

        try:
            db.instance.update(
                index=cfg.INDEX_LAST_LINE_STATUS, id=log_file.id, body=update_data
            )
            self._logger.debug(
                f"Saved last_line_read for {log_file.path} (ID: {log_file.id}) as {line_number}."
            )
        # NotFoundError should be handled by upsert, but catchall for other issues
        except Exception as e:
            self._logger.error(
                f"Error updating last line read for log file {log_file.path} (ID: {log_file.id}): {e}",
                exc_info=True,
            )
            # exit(1) # Potentially too harsh

    def _clear_records(self, db: Database):
        """
        prepare for interface later to change if file is being modified
        """
        try:
            # This method clears ALL log data and ALL last_line_status, which is very destructive.
            # It should probably be more targeted or used with extreme caution.
            # For now, keeping original behavior.
            self._logger.warning(
                "Clearing ALL log file storage and last line statuses."
            )

            # Delete all log storage indices (requires knowing all group names or using a pattern)
            # This is complex. For now, let's assume cfg.INDEX_LOG_FILES_STORAGE was a generic pattern
            # or a single index. The current code does not use cfg.INDEX_LOG_FILES_STORAGE for actual data.
            # Instead, it uses dynamic indices like "log_<group_name>".
            # A more robust clear would list indices matching "log_*" or "parsed_log_*", etc.
            # db.instance.indices.delete(index=cfg.INDEX_LOG_FILES_STORAGE, ignore=[400, 404]) # This was likely a placeholder

            db.instance.indices.delete(
                index=cfg.INDEX_LAST_LINE_STATUS, ignore=[400, 404]
            )
            self._logger.info(f"Cleared index: {cfg.INDEX_LAST_LINE_STATUS}")

            # To clear all collected log data indices:
            # response = db.instance.indices.get_alias(name="log_*") # Or whatever pattern your indices follow
            # for index_name in response.keys():
            #     db.instance.indices.delete(index=index_name, ignore=[400,404])
            #     self._logger.info(f"Cleared data index: {index_name}")

        except Exception as e:
            self._logger.error(f"Error deleting log files index: {e}")
            print(
                "Please check if the index exists and the connection to the Elasticsearch"
            )
            # exit(1) # Potentially too harsh


def main():
    es_db = ElasticsearchDatabase()

    dir = "../log/"  # Ensure this path is correct relative to where you run the script
    collector = Collector(dir)

    # collector.insert_logs_to_db(db=es_db, files=collector.log_files)
    collector.insert_very_large_logs_into_db(db=es_db, files=collector.collected_files)


if __name__ == "__main__":
    main()
