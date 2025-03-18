# utils/prompts_manager.py
import os
import ast
import json
import argparse
import re
import inspect

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

    def update_prompt_store(self, dir):
        """Scan directory and update prompts.json, returning updated keys."""
        dir_basename = os.path.basename(os.path.normpath(dir))
        updated_prompts = self.prompts.copy()
        updated_keys = []

        if dir_basename not in updated_prompts:
            updated_prompts[dir_basename] = {}
            updated_keys.append(dir_basename)

        for filename in os.listdir(dir):
            if filename.endswith(".py") and filename != "__init__.py":
                sub_module_name = filename[:-3]
                file_path = os.path.join(dir, filename)

                if sub_module_name not in updated_prompts[dir_basename]:
                    updated_prompts[dir_basename][sub_module_name] = {}
                    updated_keys.append(f"{dir_basename}.{sub_module_name}")

                with open(file_path, "r") as f:
                    tree = ast.parse(f.read())

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        class_name = node.name
                        if class_name not in updated_prompts[dir_basename][sub_module_name]:
                            updated_prompts[dir_basename][sub_module_name][class_name] = {}
                            updated_keys.append(f"{dir_basename}.{sub_module_name}.{class_name}")

                        for class_node in node.body:
                            if isinstance(class_node, ast.FunctionDef):
                                function_name = class_node.name
                                if function_name.startswith("__"):
                                    continue
                                full_key = f"{dir_basename}.{sub_module_name}.{class_name}.{function_name}"
                                if function_name not in updated_prompts[dir_basename][sub_module_name][class_name]:
                                    updated_prompts[dir_basename][sub_module_name][class_name][function_name] = "no prompts"
                                    updated_keys.append(full_key)

        self.prompts = updated_prompts
        self._save_prompts()
        return updated_keys

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

    def get_prompt(self, metadata: str = None, **variables: str) -> str:
        """Retrieve a prompt using runtime-resolved or user-provided metadata."""
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
        except (KeyError, TypeError) as e:
            class_name, function_name = parts[-2], parts[-1]
            for dir_name, dir_data in self.prompts.items():
                for sub_module, sub_module_data in dir_data.items():
                    if class_name in sub_module_data and function_name in sub_module_data[class_name]:
                        prompt_template = sub_module_data[class_name][function_name]
                        full_path = f"{dir_name}.{sub_module}.{class_name}.{function_name}"
                        break
                if prompt_template:
                    break
            else:
                raise KeyError(f"Prompt for '{metadata}' (or '{class_name}.{function_name}') not found in prompts.json") from e

        if not isinstance(prompt_template, str):
            raise ValueError(f"Value at '{metadata}' is not a string prompt: {prompt_template}")

        placeholders = set(re.findall(r"\{(\w+)\}", prompt_template))
        missing_vars = placeholders - set(variables.keys())
        if missing_vars:
            raise ValueError(f"Missing variables for prompt '{metadata}': {missing_vars}")

        extra_vars = set(variables.keys()) - placeholders
        if extra_vars:
            raise ValueError(f"Extra variables provided for prompt '{metadata}' not in template: {extra_vars}")

        return prompt_template.format(**variables)

def main():
    parser = argparse.ArgumentParser(
        description="Manage prompts in prompts.json by scanning directories or deleting keys."
    )
    parser.add_argument(
        "-d", "--directory",
        type=str,
        help="Directory to scan and add to prompts.json (e.g., agents/)"
    )
    parser.add_argument(
        "--delete",
        nargs="+",
        help="Keys to delete from prompts.json in dot notation (e.g., 'agents agents.reasoning_agent')"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print the full PROMPTS dictionary"
    )

    args = parser.parse_args()
    prompts_manager = PromptsManager()

    if args.verbose:
        import json

        # Print the header message
        print("Initial PROMPTS:")

        # Pretty-print the dictionary using json.dumps()
        print(json.dumps(prompts_manager.prompts, indent=4))

    if args.directory:
        if not os.path.isdir(args.directory):
            print(f"Error: '{args.directory}' is not a valid directory")
            return
        updated_keys = prompts_manager.update_prompt_store(args.directory)
        if updated_keys:
            print(f"Updated keys in prompts.json from {args.directory}:")
            for key in updated_keys:
                print(f"  - {key}")
        else:
            print(f"No new keys added from {args.directory}")

    if args.delete:
        deleted_keys = prompts_manager.delete_keys(args.delete)
        if deleted_keys:
            print("Deleted keys from prompts.json:")
            for key in deleted_keys:
                print(f"  - {key}")
        else:
            print("No keys were deleted (none found or already absent)")

    if not args.directory and not args.delete:
        parser.print_help()

if __name__ == "__main__":
    main()
