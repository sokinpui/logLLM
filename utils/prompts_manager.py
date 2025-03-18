import os
import ast
import json
import argparse

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

    def _update_prompt_store(self, dir):
        """
        Scan the directory for Python files, add new structures under dir -> sub_module -> class -> function
        without overwriting existing entries, and update prompts.json. Excludes __functions.

        Args:
            dir (str): Directory to scan (e.g., "agents/").
        """
        dir_basename = os.path.basename(os.path.normpath(dir))
        updated_prompts = self.prompts.copy()

        if dir_basename not in updated_prompts:
            updated_prompts[dir_basename] = {}

        for filename in os.listdir(dir):
            if filename.endswith(".py") and filename != "__init__.py":
                sub_module_name = filename[:-3]
                file_path = os.path.join(dir, filename)

                if sub_module_name not in updated_prompts[dir_basename]:
                    updated_prompts[dir_basename][sub_module_name] = {}

                with open(file_path, "r") as f:
                    tree = ast.parse(f.read())

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        class_name = node.name
                        if class_name not in updated_prompts[dir_basename][sub_module_name]:
                            updated_prompts[dir_basename][sub_module_name][class_name] = {}

                        for class_node in node.body:
                            if isinstance(class_node, ast.FunctionDef):
                                function_name = class_node.name
                                if function_name.startswith("__"):
                                    continue
                                if function_name not in updated_prompts[dir_basename][sub_module_name][class_name]:
                                    updated_prompts[dir_basename][sub_module_name][class_name][function_name] = "no prompts"

        self.prompts = updated_prompts
        self._save_prompts()

    def delete_keys(self, keys):
        """
        Delete specified keys and their values from the prompts dictionary using dot notation.

        Args:
            keys (list): List of keys in dot notation (e.g., ["agents", "agents.reasoning_agent.ReasoningAgent"]).
        """
        updated_prompts = self.prompts.copy()

        for key in keys:
            current = updated_prompts
            parts = key.split(".")
            try:
                # Navigate to the parent of the key to be deleted
                for i, part in enumerate(parts[:-1]):  # Exclude the last part
                    if part not in current:
                        print(f"Warning: Intermediate key '{'.'.join(parts[:i+1])}' not found in prompts")
                        break
                    current = current[part]
                else:
                    # Delete the final key if it exists
                    final_key = parts[-1]
                    if final_key in current:
                        del current[final_key]
                        print(f"Deleted '{key}' from prompts")
                    else:
                        print(f"Warning: Key '{key}' not found in prompts")
            except TypeError:
                print(f"Error: Invalid key path '{key}' - part of the path is not a dictionary")

        self.prompts = updated_prompts
        self._save_prompts()

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

    args = parser.parse_args()
    prompts_manager = PromptsManager()

    if args.directory:
        if not os.path.isdir(args.directory):
            print(f"Error: '{args.directory}' is not a valid directory")
            return
        prompts_manager._update_prompt_store(args.directory)
        print(f"prompts.json updated with new structures from {args.directory}")

    if args.delete:
        prompts_manager.delete_keys(args.delete)
        print(f"Deleted keys {args.delete} from prompts.json")

    if not args.directory and not args.delete:
        parser.print_help()

if __name__ == "__main__":
    main()
