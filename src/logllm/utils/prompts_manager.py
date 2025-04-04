import os
import ast
import json
import argparse
import re
import inspect
import subprocess
from typing import Dict, Any, List
from datetime import datetime

class PromptsManager:
    def __init__(self, json_file="prompts/prompts.json"):
        self.json_file = json_file
        self.prompts = self._load_prompts()
        self._ensure_git_repo()

    def _ensure_git_repo(self):
        """Ensure the directory containing the JSON file is a Git repository."""
        json_dir = os.path.dirname(self.json_file) or "."
        if not os.path.exists(os.path.join(json_dir, ".git")):
            subprocess.run(["git", "init"], cwd=json_dir, check=True, capture_output=True)
            # Initial commit if no file exists yet
            if not os.path.exists(self.json_file):
                self._save_prompts()  # Creates an empty JSON file
                subprocess.run(["git", "add", os.path.basename(self.json_file)], cwd=json_dir, check=True)
                subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=json_dir, check=True)

    def _load_prompts(self):
        """Load existing prompts from the JSON file, or return an empty dict if it doesn't exist."""
        if os.path.exists(self.json_file):
            with open(self.json_file, "r") as f:
                return json.load(f)
        return {}

    def _save_prompts(self, commit_message: str = None):
        """Save the current prompts to the JSON file and commit to Git with a custom or default message."""
        os.makedirs(os.path.dirname(self.json_file) or ".", exist_ok=True)
        with open(self.json_file, "w") as f:
            json.dump(self.prompts, f, indent=4)

        json_dir = os.path.dirname(self.json_file) or "."
        json_base = os.path.basename(self.json_file)
        subprocess.run(["git", "add", json_base], cwd=json_dir, check=True)

        if commit_message is None:
            # Default commit message with timestamp
            readable_time = datetime.now().strftime("%b %d, %Y %I:%M %p")
            commit_msg = f"Update {json_base} at {readable_time}"
            subprocess.run(["git", "commit", "-m", commit_msg], cwd=json_dir, check=False)
        elif commit_message == "":
            # Open default editor (e.g., vim) for interactive commit message
            subprocess.run(["git", "commit"], cwd=json_dir, check=True)
        else:
            # Use provided commit message
            subprocess.run(["git", "commit", "-m", commit_message], cwd=json_dir, check=False)

    def _update_prompt_store(self, dir: str, commit_message: str = None):
        """Scan the top-level directory, update prompts.json, and return updated keys."""
        updated_prompts = self.prompts.copy()
        updated_keys = []
        dir_name = os.path.basename(os.path.normpath(dir))

        if dir_name not in updated_prompts:
            updated_prompts[dir_name] = {}
            updated_keys.append(dir_name)

        for filename in os.listdir(dir):
            if filename.endswith(".py") and filename != "__init__.py":
                sub_module_name = filename[:-3]
                file_path = os.path.join(dir, filename)

                if sub_module_name not in updated_prompts[dir_name]:
                    updated_prompts[dir_name][sub_module_name] = {}
                    updated_keys.append(f"{dir_name}.{sub_module_name}")

                with open(file_path, "r") as f:
                    tree = ast.parse(f.read())

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        class_name = node.name
                        if class_name not in updated_prompts[dir_name][sub_module_name]:
                            updated_prompts[dir_name][sub_module_name][class_name] = {}
                            updated_keys.append(f"{dir_name}.{sub_module_name}.{class_name}")

                        for class_node in node.body:
                            if isinstance(class_node, ast.FunctionDef):
                                function_name = class_node.name
                                if function_name.startswith("__"):
                                    continue
                                full_key = f"{dir_name}.{sub_module_name}.{class_name}.{function_name}"
                                if function_name not in updated_prompts[dir_name][sub_module_name][class_name]:
                                    updated_prompts[dir_name][sub_module_name][class_name][function_name] = "no prompts"
                                    updated_keys.append(full_key)

        self.prompts = updated_prompts
        self._save_prompts(commit_message)
        return updated_keys

    def _update_prompt_store_recursive(self, dir: str, commit_message: str = None, current_dict: Dict[str, Any] = None, base_path: str = "") -> list[str]:
        """Recursively scan all subdirectories and update prompts.json with proper nesting."""
        if current_dict is None:
            current_dict = self.prompts
        updated_keys = []
        dir_path = os.path.normpath(dir)
        dir_name = os.path.basename(dir_path)

        if dir_name not in current_dict:
            current_dict[dir_name] = {}
            updated_keys.append(dir_name if not base_path else f"{base_path}.{dir_name}")

        current_level = current_dict[dir_name]

        for filename in os.listdir(dir_path):
            if filename.endswith(".py") and filename != "__init__.py":
                sub_module_name = filename[:-3]
                file_path = os.path.join(dir_path, filename)

                if sub_module_name not in current_level:
                    current_level[sub_module_name] = {}
                    full_key = f"{dir_name}.{sub_module_name}" if not base_path else f"{base_path}.{dir_name}.{sub_module_name}"
                    updated_keys.append(full_key)

                with open(file_path, "r") as f:
                    tree = ast.parse(f.read())

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        class_name = node.name
                        if class_name not in current_level[sub_module_name]:
                            current_level[sub_module_name][class_name] = {}
                            full_key = f"{dir_name}.{sub_module_name}.{class_name}" if not base_path else f"{base_path}.{dir_name}.{sub_module_name}.{class_name}"
                            updated_keys.append(full_key)

                        for class_node in node.body:
                            if isinstance(class_node, ast.FunctionDef):
                                function_name = class_node.name
                                if function_name.startswith("__"):
                                    continue
                                full_key = f"{dir_name}.{sub_module_name}.{class_name}.{function_name}" if not base_path else f"{base_path}.{dir_name}.{sub_module_name}.{class_name}.{function_name}"
                                if function_name not in current_level[sub_module_name][class_name]:
                                    current_level[sub_module_name][class_name][function_name] = "no prompts"
                                    updated_keys.append(full_key)

        for subdir in os.listdir(dir_path):
            subdir_path = os.path.join(dir_path, subdir)
            if (os.path.isdir(subdir_path) and
                not subdir.startswith('.') and
                subdir != '__pycache__'):
                new_base_path = dir_name if not base_path else f"{base_path}.{dir_name}"
                sub_keys = self._update_prompt_store_recursive(subdir_path, commit_message, current_level, new_base_path)
                updated_keys.extend(sub_keys)

        self.prompts = current_dict if base_path else current_dict
        self._save_prompts(commit_message)
        return updated_keys

    def _hard_update_prompt_store(self, dir: str, commit_message: str = None) -> list[str]:
        """Hard update: Update only the given top-level dir, keeping existing values, removing non-existent."""
        updated_prompts = self.prompts.copy()
        updated_keys = []
        dir_name = os.path.basename(os.path.normpath(dir))

        if dir_name not in updated_prompts:
            updated_prompts[dir_name] = {}
            updated_keys.append(dir_name)

        new_level = {}
        for filename in os.listdir(dir):
            if filename.endswith(".py") and filename != "__init__.py":
                sub_module_name = filename[:-3]
                file_path = os.path.join(dir, filename)

                new_level[sub_module_name] = {}
                full_key = f"{dir_name}.{sub_module_name}"
                updated_keys.append(full_key)

                with open(file_path, "r") as f:
                    tree = ast.parse(f.read())

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        class_name = node.name
                        new_level[sub_module_name][class_name] = {}
                        full_key = f"{dir_name}.{sub_module_name}.{class_name}"
                        updated_keys.append(full_key)

                        for class_node in node.body:
                            if isinstance(class_node, ast.FunctionDef):
                                function_name = class_node.name
                                if function_name.startswith("__"):
                                    continue
                                full_key = f"{dir_name}.{sub_module_name}.{class_name}.{function_name}"
                                old_value = self._get_nested_value(updated_prompts, full_key.split("."))
                                new_level[sub_module_name][class_name][function_name] = old_value if old_value is not None else "no prompts"
                                updated_keys.append(full_key)

        updated_prompts[dir_name] = new_level
        self.prompts = updated_prompts
        self._save_prompts(commit_message)
        return updated_keys

    def _hard_update_prompt_store_recursive(self, dir: str, commit_message: str = None, current_dict: Dict[str, Any] = None, base_path: str = "") -> list[str]:
        """Hard update: Update only the given dir recursively, keeping existing values, removing non-existent."""
        if current_dict is None:
            current_dict = self.prompts.copy()
        updated_keys = []
        dir_path = os.path.normpath(dir)
        dir_name = os.path.basename(dir_path)

        if dir_name not in current_dict:
            current_dict[dir_name] = {}
            updated_keys.append(dir_name if not base_path else f"{base_path}.{dir_name}")

        new_level = {}
        for filename in os.listdir(dir_path):
            if filename.endswith(".py") and filename != "__init__.py":
                sub_module_name = filename[:-3]
                file_path = os.path.join(dir_path, filename)

                new_level[sub_module_name] = {}
                full_key = f"{dir_name}.{sub_module_name}" if not base_path else f"{base_path}.{dir_name}.{sub_module_name}"
                updated_keys.append(full_key)

                with open(file_path, "r") as f:
                    tree = ast.parse(f.read())

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        class_name = node.name
                        new_level[sub_module_name][class_name] = {}
                        full_key = f"{dir_name}.{sub_module_name}.{class_name}" if not base_path else f"{base_path}.{dir_name}.{sub_module_name}.{class_name}"
                        updated_keys.append(full_key)

                        for class_node in node.body:
                            if isinstance(class_node, ast.FunctionDef):
                                function_name = class_node.name
                                if function_name.startswith("__"):
                                    continue
                                full_key = f"{dir_name}.{sub_module_name}.{class_name}.{function_name}" if not base_path else f"{base_path}.{dir_name}.{sub_module_name}.{class_name}.{function_name}"
                                old_value = self._get_nested_value(self.prompts, full_key.split("."))
                                new_level[sub_module_name][class_name][function_name] = old_value if old_value is not None else "no prompts"
                                updated_keys.append(full_key)

        for subdir in os.listdir(dir_path):
            subdir_path = os.path.join(dir_path, subdir)
            if (os.path.isdir(subdir_path) and
                not subdir.startswith('.') and
                subdir != '__pycache__'):
                new_base_path = dir_name if not base_path else f"{base_path}.{dir_name}"
                sub_keys = self._hard_update_prompt_store_recursive(subdir_path, commit_message, new_level, new_base_path)
                updated_keys.extend(sub_keys)

        current_dict[dir_name] = new_level
        if not base_path:
            self.prompts = current_dict
        self._save_prompts(commit_message)
        return updated_keys

    def _get_nested_value(self, d: Dict[str, Any], keys: List[str]) -> Any:
        """Helper to get a nested value from a dictionary using a list of keys."""
        current = d
        for key in keys:
            try:
                current = current[key]
            except (KeyError, TypeError):
                return None
        return current

    def _set_nested_value(self, d: Dict[str, Any], keys: List[str], value: str) -> bool:
        """Helper to set a nested value in a dictionary using a list of keys."""
        current = d
        for key in keys[:-1]:
            if key not in current or not isinstance(current[key], dict):
                return False
            current = current[key]
        final_key = keys[-1]
        if final_key in current and isinstance(current[final_key], str):
            current[final_key] = value
            return True
        return False

    def list_prompts(self, only_prompts: bool = False) -> List[List[str]]:
        """List all keys in prompts.json (or only those with prompts if only_prompts=True)."""
        def recurse_dict(d: Dict[str, Any], current_path: List[str], key_list: List[List[str]]):
            for key, value in d.items():
                new_path = current_path + [key]
                if isinstance(value, str):
                    if only_prompts or not only_prompts:
                        key_list.append(new_path)
                elif isinstance(value, dict):
                    if not only_prompts:
                        key_list.append(new_path)
                    recurse_dict(value, new_path, key_list)

        key_list = []
        recurse_dict(self.prompts, [], key_list)

        if key_list:
            print(f"Keys in prompts.json{' (prompts only)' if only_prompts else ''}:")
            for keys in key_list:
                print(f"  - {'.'.join(keys)}")
        else:
            print(f"No keys{' with prompts' if only_prompts else ''} found in prompts.json")

        return key_list

    def add_prompt(self, key: str, value: str, commit_message: str = None) -> bool:
        """Add or update a prompt for an existing key with a string value."""
        updated_prompts = self.prompts.copy()
        keys = key.split(".")
        if self._set_nested_value(updated_prompts, keys, value):
            self.prompts = updated_prompts
            self._save_prompts(commit_message)
            print(f"Added/Updated prompt for '{key}': '{value}'")
            return True
        else:
            print(f"Error: Key '{key}' does not exist or is not a prompt field")
            return False

    def delete_keys(self, keys: list[str], commit_message: str = None):
        """Delete keys from prompts.json, returning deleted keys."""
        updated_prompts = self.prompts.copy()
        deleted_keys = []

        for key in keys:
            current = updated_prompts
            parts = key.split(".")
            try:
                for i, part in enumerate(parts[:-1]):
                    if part not in current:
                        print(f"Warning: Intermediate key '{'.'.join(parts[:i+1])}' not found in prompts")
                        break
                    current = current[part]
                else:
                    final_key = parts[-1]
                    if final_key in current:
                        del current[final_key]
                        deleted_keys.append(key)
                        print(f"Deleted '{key}' from prompts")
                    else:
                        print(f"Warning: Key '{key}' not found in prompts")
            except TypeError:
                print(f"Error: Invalid key path '{key}' - part of the path is not a dictionary")

        self.prompts = updated_prompts
        self._save_prompts(commit_message)
        return deleted_keys

    def _search_prompt_recursive(self, prompts: Dict[str, Any], class_name: str, function_name: str, current_path: str = "") -> tuple[str, str] | None:
        """Recursively search prompts dictionary for a class.function match."""
        for key, value in prompts.items():
            new_path = f"{current_path}.{key}" if current_path else key
            if isinstance(value, dict):
                if key == class_name and function_name in value:
                    return new_path, value[function_name]
                result = self._search_prompt_recursive(value, class_name, function_name, new_path)
                if result:
                    return result
        return None

    def get_prompt(self, metadata: str = None, **variables: str) -> str:
        """Retrieve a prompt using provided metadata or dynamically resolved metadata."""
        if metadata is None:
            caller_frame = inspect.currentframe().f_back
            if not caller_frame:
                raise RuntimeError("Unable to determine caller context for metadata resolution")

            function_name = caller_frame.f_code.co_name
            caller_locals = caller_frame.f_locals
            if "self" not in caller_locals:
                raise RuntimeError("get_prompt must be called from an instance method (no 'self' found)")
            class_name = caller_locals["self"].__class__.__name__

            file_path = os.path.normpath(caller_frame.f_code.co_filename)
            base_dir = os.getcwd()
            rel_path = os.path.relpath(file_path, base_dir)
            dir_name, file_name = os.path.split(rel_path)
            sub_module = os.path.splitext(file_name)[0]
            metadata = f"{dir_name}.{sub_module}.{class_name}.{function_name}".replace(os.sep, ".")

        current = self.prompts
        parts = metadata.split(".")
        try:
            for part in parts:
                current = current[part]
            prompt_template = current
            full_path = metadata
        except (KeyError, TypeError):
            class_name, function_name = parts[-2], parts[-1]
            result = self._search_prompt_recursive(self.prompts, class_name, function_name)
            if result:
                full_path, prompt_template = result
            else:
                raise KeyError(f"Prompt for '{metadata}' (or '{class_name}.{function_name}') not found in prompts.json")

        if not isinstance(prompt_template, str):
            raise ValueError(f"Value at '{full_path}' is not a string prompt: {prompt_template}")

        placeholders = set(re.findall(r"\{(\w+)\}", prompt_template))
        missing_vars = placeholders - set(variables.keys())
        if missing_vars:
            raise ValueError(f"Missing variables for prompt '{full_path}': {missing_vars}")

        extra_vars = set(variables.keys()) - placeholders
        if extra_vars:
            raise ValueError(f"Extra variables provided for prompt '{full_path}' not in template: {extra_vars}")

        return prompt_template.format(**variables)

    def list_versions(self, key: str = None, verbose: int = 50, tail: int = -1, free: bool = False) -> List[Dict[str, str]]:
        """List commit history for a specific key or the entire file, sorted by time, limited by tail, with optional free-form output."""
        json_dir = os.path.dirname(self.json_file) or "."
        json_base = os.path.basename(self.json_file)

        result = subprocess.run(
            ["git", "log", "--pretty=format:%H %ct %s", json_base],
            cwd=json_dir,
            capture_output=True,
            text=True,
            check=True
        )
        commits = result.stdout.strip().split("\n")
        if not commits or commits == [""]:
            print(f"No version history found for {self.json_file}")
            return []

        history = []
        for commit in commits:
            if not commit:
                continue
            commit_hash, timestamp, message = commit.split(" ", 2)
            timestamp = datetime.fromtimestamp(int(timestamp)).isoformat()

            content = subprocess.run(
                ["git", "show", f"{commit_hash}:{json_base}"],
                cwd=json_dir,
                capture_output=True,
                text=True,
                check=False
            )
            if content.returncode != 0:
                continue

            try:
                past_prompts = json.loads(content.stdout)
                if key:
                    keys = key.split(".")
                    value = self._get_nested_value(past_prompts, keys)
                    if value is not None and isinstance(value, str):
                        history.append({
                            "commit": commit_hash,
                            "timestamp": timestamp,
                            "message": message,
                            "prompt": value
                        })
                else:
                    history.append({
                        "commit": commit_hash,
                        "timestamp": timestamp,
                        "message": message,
                        "prompt": None
                    })
            except json.JSONDecodeError:
                continue

        if key and not history:
            print(f"No version history found for key '{key}' in {self.json_file}")
        elif not key:
            print(f"Version history for {self.json_file}:")
        else:
            print(f"Version history for '{key}' in {self.json_file}:")

        # Sort by timestamp (descending) and apply tail limit
        sorted_history = sorted(history, key=lambda x: x["timestamp"], reverse=True)
        sorted_history = sorted_history[:tail]

        if free:
            # Free-form output with full commit messages and prompts
            for entry in sorted_history:
                if key and entry["prompt"]:
                    prompt_display = entry["prompt"] if verbose == -1 else entry["prompt"][:verbose]
                    print(f"| {entry['commit'][:8]} | {entry['message']} | Prompt: {prompt_display}")
                else:
                    print(f"| {entry['commit'][:8]} | {entry['message']}")
        else:
            # Pretty boxed output with fixed-width columns and collapsed prompts
            commit_width = 8  # Fixed width for commit hash
            default_msg = f"Update {json_base} at {datetime.now().strftime('%b %d, %Y %I:%M %p')}"
            msg_width = len(default_msg)
            separator = " | "

            # Calculate total width for separators
            total_width = commit_width + len(separator) + msg_width + (len(separator))
            print("-" * total_width)

            for entry in sorted_history:
                commit_display = entry["commit"][:8].ljust(commit_width)
                if len(entry["message"]) > msg_width:
                    msg_display = entry["message"][:msg_width-3] + "..."
                else:
                    msg_display = entry["message"].ljust(msg_width)
                if key and entry["prompt"]:
                    # Take the first line, truncate if needed, and remove any newlines
                    prompt_lines = entry["prompt"].split("\n")
                    first_line = prompt_lines[0][:verbose] if verbose != -1 else prompt_lines[0]
                    prompt_display = f"Prompt: {first_line}"
                    if (verbose != -1 and len(prompt_lines[0]) > verbose) or len(prompt_lines) > 1:
                        prompt_display += "..."
                    print(f"| {commit_display} | {msg_display} | {prompt_display}")
                else:
                    print(f"| {commit_display} | {msg_display}")

            print("-" * total_width)

        return sorted_history

    def revert_version(self, commit_hash: str, key: str = None, commit_message: str = None, verbose: int = 50):
        """Revert to a specific commit, optionally for a single key."""
        json_dir = os.path.dirname(self.json_file) or "."
        json_base = os.path.basename(self.json_file)

        content = subprocess.run(
            ["git", "show", f"{commit_hash}:{json_base}"],
            cwd=json_dir,
            capture_output=True,
            text=True,
            check=True
        )
        past_prompts = json.loads(content.stdout)

        if key:
            keys = key.split(".")
            old_value = self._get_nested_value(past_prompts, keys)
            if old_value is None or not isinstance(old_value, str):
                print(f"Error: Key '{key}' not found or not a prompt in commit {commit_hash}")
                return False
            if self._set_nested_value(self.prompts, keys, old_value):
                self._save_prompts(commit_message)
                prompt_display = old_value if verbose == -1 else old_value[:verbose]
                print(f"Reverted '{key}' to version from commit {commit_hash}: '{prompt_display}'")
                return True
            else:
                print(f"Error: Could not revert '{key}' - key not found in current structure")
                return False
        else:
            self.prompts = past_prompts
            self._save_prompts(commit_message)
            print(f"Reverted entire {self.json_file} to commit {commit_hash}")
            return True

    def show_diff(self, commit1: str, commit2: str, key: str = None, verbose: int = 50):
        """Show a readable diff between two commits for the JSON file or a specific key."""
        json_dir = os.path.dirname(self.json_file) or "."
        json_base = os.path.basename(self.json_file)
        json_file = self.json_file

        # Get the content of the JSON file at commit1
        result1 = subprocess.run(
            ["git", "show", f"{commit1}:{json_base}"],
            cwd=json_dir,
            capture_output=True,
            text=True,
            check=False
        )
        if result1.returncode != 0:
            print(f"Error: Could not retrieve {json_file} at commit {commit1}")
            return

        # Get the content of the JSON file at commit2
        result2 = subprocess.run(
            ["git", "show", f"{commit2}:{json_base}"],
            cwd=json_dir,
            capture_output=True,
            text=True,
            check=False
        )
        if result2.returncode != 0:
            print(f"Error: Could not retrieve {json_file} at commit {commit2}")
            return

        try:
            content1 = json.loads(result1.stdout)
            content2 = json.loads(result2.stdout)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in one or both commits ({commit1}, {commit2}): {e}")
            return

        if key:
            # Extract the prompt for the specific key
            keys = key.split(".")
            prompt1 = self._get_nested_value(content1, keys)
            prompt2 = self._get_nested_value(content2, keys)

            if prompt1 is None and prompt2 is None:
                print(f"Key '{key}' not found in either {commit1} or {commit2}")
                return
            elif prompt1 == prompt2:
                print(f"No difference found for key '{key}' between {commit1} and {commit2}")
                return

            # Apply verbose truncation if applicable
            display_prompt1 = prompt1 if verbose == -1 or prompt1 is None else prompt1[:verbose]
            display_prompt2 = prompt2 if verbose == -1 or prompt2 is None else prompt2[:verbose]

            print(f"Diff for key '{key}' between {commit1} and {commit2} in {json_file}:")
            print(f"{commit1}:\n{display_prompt1}")
            print()
            print(f"{commit2}:\n{display_prompt2}")
        else:
            # Compare the entire file
            if content1 == content2:
                print(f"No differences found between {commit1} and {commit2} for {json_file}")
                return

            print(f"Diff between {commit1} and {commit2} for {json_file}:")
            # For simplicity, show full JSON content with truncation for readability
            display_content1 = json.dumps(content1, indent=4) if verbose == -1 else json.dumps(content1, indent=4)[:verbose]
            display_content2 = json.dumps(content2, indent=4) if verbose == -1 else json.dumps(content2, indent=4)[:verbose]
            print(f"{commit1}:\n{display_content1}")
            print()
            print(f"{commit2}:\n{display_content2}")
