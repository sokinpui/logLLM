# src/logllm/agents/static_grok_parser/api/grok_parsing_service.py
from pygrok import Grok  # type: ignore
from typing import Optional, Dict, Any

# Logger can be added if specific logging is needed within this service
# from ....utils.logger import Logger


class GrokParsingService:
    # _logger = Logger() # Optional: if you need logging here

    def parse_line(
        self, line_content: str, grok_instance: Grok
    ) -> Optional[Dict[str, Any]]:
        if not line_content or not grok_instance:
            # self._logger.debug("parse_line: Empty content or no Grok instance.")
            return None
        try:
            parsed_fields = grok_instance.match(
                str(line_content)
            )  # Ensure line_content is string
            return parsed_fields  # Returns dict if match, None otherwise
        except Exception as e:
            # self._logger.error(f"Grok match error on line '{str(line_content)[:100]}...': {e}", exc_info=False) # Be careful with logging potentially sensitive data
            return None
