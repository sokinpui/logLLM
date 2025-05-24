# src/logllm/agents/static_grok_parser/api/grok_pattern_service.py
import os
from typing import Any, Dict, Optional

import yaml
from pygrok import Grok

# Adjust import path for Logger relative to this file's location if running standalone
# For integration, the main agent's instantiation of services will handle this.
try:
    from ....utils.logger import Logger
except ImportError:  # Fallback for direct execution or different project structure
    # This is a simplified fallback, consider a more robust solution if needed
    import logging

    Logger = lambda: logging.getLogger(__name__)


class GrokPatternService:
    def __init__(self, grok_patterns_yaml_path: str = "grok_patterns.yaml"):
        self._logger = Logger()
        self.grok_patterns_config: Dict[str, Any] = self._load_grok_patterns_from_yaml(
            grok_patterns_yaml_path
        )
        self._compiled_grok_instances: Dict[str, Optional[Grok]] = {}  # Cache
        if not self.grok_patterns_config:
            self._logger.warning(
                f"Grok patterns YAML '{grok_patterns_yaml_path}' was empty or not found. Service may not provide patterns."
            )

    def _load_grok_patterns_from_yaml(self, yaml_path: str) -> Dict[str, Any]:
        self._logger.info(f"Loading Grok patterns from YAML: {yaml_path}")
        if not os.path.exists(yaml_path):
            self._logger.error(f"Grok patterns YAML file not found at {yaml_path}")
            return {}
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                patterns = yaml.safe_load(f)
                if patterns is None:
                    self._logger.warning(
                        f"Grok patterns YAML file is empty: {yaml_path}"
                    )
                    return {}
                self._logger.info(
                    f"Successfully loaded {len(patterns)} top-level Grok pattern configurations."
                )
                return patterns
        except yaml.YAMLError as e:
            self._logger.error(
                f"Error parsing Grok patterns YAML file {yaml_path}: {e}", exc_info=True
            )
            return {}
        except Exception as e:
            self._logger.error(
                f"Unexpected error loading Grok patterns YAML {yaml_path}: {e}",
                exc_info=True,
            )
            return {}

    def get_grok_pattern_string_for_group(self, group_name: str) -> Optional[str]:
        pattern_config = self.grok_patterns_config.get(group_name)
        if not pattern_config or "grok_pattern" not in pattern_config:
            self._logger.debug(
                f"No Grok pattern configuration string found for group: {group_name}"
            )
            return None

        raw_pattern = pattern_config["grok_pattern"]
        if raw_pattern is None:  # Handle case where grok_pattern key exists but is null
            self._logger.debug(
                f"Grok pattern for group '{group_name}' is explicitly null."
            )
            return None

        # Ensure it's a string and strip leading/trailing whitespace (including newlines)
        return str(raw_pattern).strip()

    def get_derived_field_definitions_for_group(
        self, group_name: str
    ) -> Optional[Dict[str, str]]:
        """
        Retrieves the 'derived_fields' definitions for a given group.
        Returns a dictionary like {'new_field_name': 'format_string', ...} or None.
        """
        group_config = self.grok_patterns_config.get(group_name)
        if not group_config:
            self._logger.debug(
                f"No full configuration found for group: {group_name} when looking for derived fields."
            )
            return None

        derived_definitions = group_config.get("derived_fields")
        if derived_definitions is None:
            self._logger.debug(
                f"No 'derived_fields' section defined for group: {group_name}"
            )
            return None

        if not isinstance(derived_definitions, dict):
            self._logger.warning(
                f"'derived_fields' for group '{group_name}' is not a dictionary. Skipping derived fields for this group."
            )
            return None

        valid_definitions: Dict[str, str] = {}
        for key, value in derived_definitions.items():
            if isinstance(value, str):
                valid_definitions[key] = value
            else:
                self._logger.warning(
                    f"Invalid format string for derived field '{key}' in group '{group_name}'. Expected string, got {type(value)}. Skipping this derived field definition."
                )

        if not valid_definitions:  # If all definitions were invalid
            return None
        return valid_definitions

    def get_compiled_grok_instance(
        self, group_name_for_caching: str, pattern_string: str
    ) -> Optional[Grok]:
        """
        Compiles a given pattern string. Uses group_name_for_caching for the cache key.
        """
        if not pattern_string:
            self._logger.warning(
                f"Cannot compile Grok instance for '{group_name_for_caching}': No pattern string provided."
            )
            return None

        # Check cache using group_name_for_caching AND pattern_string to handle dynamic patterns if ever needed
        cache_key = f"{group_name_for_caching}_{hash(pattern_string)}"
        if cache_key in self._compiled_grok_instances:
            return self._compiled_grok_instances[cache_key]

        try:
            grok_instance = Grok(pattern_string)
            self._logger.info(
                f"Successfully compiled Grok pattern for '{group_name_for_caching}'."
            )
            self._compiled_grok_instances[cache_key] = grok_instance
            return grok_instance
        except Exception as e:
            self._logger.error(
                f"Failed to compile Grok pattern string '{pattern_string}' (for cache key '{group_name_for_caching}'). Error: {e}",
                exc_info=True,
            )
            self._compiled_grok_instances[cache_key] = None  # Cache failure
            return None
