# utils/prompts_manager.py
import os
import ast
import json
import argparse
import re
import inspect
from typing import Dict, Any, List

class PromptsManager:
    def __init__(self, json_file="prompts/prompts.json"):
        self.json_file = json_file
        self.prompts = self._load_prompts()

    def _load_prompts(self):
        """Load existing prompts from the JSON file, or return an empty dict if it doesn't exist."""
        if os.path.exists(self.json_file):
            with open(self.json_file, "r") as f:
                return json.load(f)
        return {}

    def _save_prompts(self):
        """Save the current prompts to the JSON file."""
        os.makedirs("prompts", exist_ok=True)
        with open(self.json_file, "w") as f:
            json.dump(self.prompts, f, indent=4)

    def _update_prompt_store(self, dir: str):
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
        self._save_prompts()
        return updated_keys

    def _update_prompt_store_recursive(self, dir: str, current_dict: Dict[str, Any] = None, base_path: str = "") -> list[str]:
        """Truly recursive function to scan all subdirectories and update prompts.json with proper nesting."""
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
                sub_keys = self._update_prompt_store_recursive(subdir_path, current_level, new_base_path)
                updated_keys.extend(sub_keys)

        self.prompts = current_dict if base_path else current_dict
        self._save_prompts()
        return updated_keys

    def _hard_update_prompt_store(self, dir: str) -> list[str]:
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
        self._save_prompts()
        return updated_keys

    def _hard_update_prompt_store_recursive(self, dir: str, current_dict: Dict[str, Any] = None, base_path: str = "") -> list[str]:
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
                sub_keys = self._hard_update_prompt_store_recursive(subdir_path, new_level, new_base_path)
                updated_keys.extend(sub_keys)

        current_dict[dir_name] = new_level
        if not base_path:
            self.prompts = current_dict
        self._save_prompts()
        return updated_keys

    def _get_nested_value(self, d: Dict[str, Any], keys: list[str]) -> Any:
        """Helper to get a nested value from a dictionary using a list of keys."""
        current = d
        for key in keys:
            try:
                current = current[key]
            except (KeyError, TypeError):
                return None
        return current

    def _set_nested_value(self, d: Dict[str, Any], keys: list[str], value: str) -> bool:
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
        """List all keys in prompts.json (or only those with prompts if only_prompts=True) and return them as a list of lists."""

        def recurse_dict(d: Dict[str, Any], current_path: List[str], key_list: List[List[str]]):
            for key, value in d.items():
                new_path = current_path + [key]
                if isinstance(value, str):  # Prompt key
                    if only_prompts or not only_prompts:  # Always add prompt keys when not filtering, or when filtering to prompts
                        key_list.append(new_path)
                elif isinstance(value, dict):  # Structural key
                    if not only_prompts:  # Add structural keys only when not filtering
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

    def add_prompt(self, key: str, value: str) -> bool:
        """Add or update a prompt for an existing key with a string value."""
        updated_prompts = self.prompts.copy()
        keys = key.split(".")
        if self._set_nested_value(updated_prompts, keys, value):
            self.prompts = updated_prompts
            self._save_prompts()
            print(f"Added/Updated prompt for '{key}': '{value}'")
            return True
        else:
            print(f"Error: Key '{key}' does not exist or is not a prompt field")
            return False

    def delete_keys(self, keys):
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
        self._save_prompts()
        return deleted_keys

    def _search_prompt_recursive(self, prompts: Dict[str, Any], class_name: str, function_name: str, current_path: str = "") -> tuple[str, str] | None:
        """Recursively search prompts dictionary for a class.function match, returning (full_path, prompt_template)."""
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
        """Retrieve a prompt using provided metadata or dynamically resolved metadata with recursive search."""
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

def main():
    parser = argparse.ArgumentParser(
        description="Manage prompts in a JSON file: scan directories, list keys, add prompts, or delete keys."
    )
    subparsers = parser.add_subparsers(dest="action", help="Action to perform")

    # 'scan' action
    scan_parser = subparsers.add_parser("scan", help="Scan a directory to update the prompt store")
    scan_parser.add_argument(
        "-d", "--directory",
        type=str,
        required=True,
        help="Directory to scan and add to the prompt store (e.g., tests/)"
    )
    scan_parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Recursively scan subdirectories, skipping hidden dirs and __pycache__"
    )
    scan_parser.add_argument(
        "--hard",
        action="store_true",
        help="Perform a hard update: clear non-existent objects within the given directory, keep existing values"
    )
    scan_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print the entire prompt store content after the operation"
    )

    # 'list' action
    list_parser = subparsers.add_parser("list", help="List keys in the prompt store")
    list_parser.add_argument(
        "-p", "--prompt",
        action="store_true",
        help="Only show keys with prompt strings"
    )
    list_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print the entire prompt store content after the operation"
    )

    # 'add' action
    add_parser = subparsers.add_parser("add", help="Add or update a prompt for an existing key")
    add_parser.add_argument(
        "-k", "--key",
        type=str,
        required=True,
        help="The key to update in dot notation (e.g., 'tests.t.TextClass.run')"
    )
    add_parser.add_argument(
        "-v", "--value",
        type=str,
        required=True,
        help="The string value to assign to the key"
    )
    add_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print the entire prompt store content after the operation"
    )

    # 'delete' action
    delete_parser = subparsers.add_parser("delete", help="Delete keys from the prompt store")
    delete_parser.add_argument(
        "-k", "--key",
        type=str,
        nargs="+",
        required=True,
        help="Keys to delete from the prompt store in dot notation (e.g., 'tests.t.TextClass.run')"
    )
    delete_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print the entire prompt store content after the operation"
    )

    # Top-level arguments
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print the entire prompt store content after the operation (if no action specified)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Use prompts/test.json instead of the default prompts/prompts.json (overridden by --json)"
    )
    parser.add_argument(
        "-j", "--json",
        type=str,
        help="Specify a custom JSON file path for the prompt store (overrides --test and default; directory must exist)"
    )

    args = parser.parse_args()
    # Determine JSON file: --json takes precedence, then --test, then default
    if args.json:
        json_dir = os.path.dirname(args.json)
        if json_dir and not os.path.exists(json_dir):
            print(f"Error: Directory '{json_dir}' for JSON file '{args.json}' does not exist")
            return
        json_file = args.json
    elif args.test:
        json_file = "prompts/test.json"
    else:
        json_file = "prompts/prompts.json"
    prompts_manager = PromptsManager(json_file=json_file)

    if args.action == "scan":
        if not os.path.isdir(args.directory):
            print(f"Error: '{args.directory}' is not a valid directory")
            return
        if args.hard:
            if args.recursive:
                updated_keys = prompts_manager._hard_update_prompt_store_recursive(args.directory)
            else:
                updated_keys = prompts_manager._hard_update_prompt_store(args.directory)
        else:
            if args.recursive:
                updated_keys = prompts_manager._update_prompt_store_recursive(args.directory)
            else:
                updated_keys = prompts_manager._update_prompt_store(args.directory)
        if updated_keys:
            print(f"Updated keys in {json_file} from {args.directory}:")
            for key in updated_keys:
                print(f"  - {key}")
        else:
            print(f"No new keys added from {args.directory}")
        if args.verbose:
            print(f"\nCurrent {json_file} content:")
            print(json.dumps(prompts_manager.prompts, indent=4))
        return

    if args.action == "list":
        prompts_manager.list_prompts(only_prompts=args.prompt)
        if args.verbose:
            print(f"\nCurrent {json_file} content:")
            print(json.dumps(prompts_manager.prompts, indent=4))
        return

    if args.action == "add":
        prompts_manager.add_prompt(args.key, args.value)
        if args.verbose:
            print(f"\nCurrent {json_file} content:")
            print(json.dumps(prompts_manager.prompts, indent=4))
        return

    if args.action == "delete":
        deleted_keys = prompts_manager.delete_keys(args.key)
        if deleted_keys:
            print(f"Deleted keys from {json_file}:")
            for key in deleted_keys:
                print(f"  - {key}")
        else:
            print("No keys were deleted (none found or already absent)")
        if args.verbose:
            print(f"\nCurrent {json_file} content:")
            print(json.dumps(prompts_manager.prompts, indent=4))
        return

    if not args.action:
        parser.print_help()

if __name__ == "__main__":
    main()
