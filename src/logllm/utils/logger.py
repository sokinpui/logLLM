import logging
import logging.handlers # Import handlers for rotation
import os # Needed for RotatingFileHandler path joining

# Assuming config is accessible as cfg relative to this file's execution context
# If running as a module, relative imports are fine.
# Adjust if necessary based on your project structure.
try:
    from ..config import config as cfg
except ImportError:
    # Fallback for running the script directly or if structure changes
    import sys
    # Add project root to path if necessary - adjust '..' level as needed
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
    from src.logllm.config import config as cfg


class Logger:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Logger, cls).__new__(cls)
        return cls._instance

    def __init__(self, name: str = cfg.LOGGER_NAME, log_file: str = cfg.LOG_FILE):
        # Initialization guard: Prevents re-initializing if instance already exists
        if hasattr(self, '_initialized') and self._initialized:
            return

        self.logger = logging.getLogger(name)
        # Prevent adding handlers multiple times if getLogger retrieves existing logger
        if not self.logger.handlers:
            self.logger.setLevel(logging.DEBUG) # Set level on the logger itself

            # --- Enhanced Formatter ---
            # Include timestamp, level, module, function, line number, and message
            log_format = '%(levelname)s - %(asctime)s - [%(module)s:%(funcName)s:%(lineno)d] - %(message)s'
            formatter = logging.Formatter(log_format)

            # --- Console Handler ---
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO) # Set level for this handler
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

            # --- Rotating File Handler ---
            # Example: Rotate logs when they reach 5MB, keep 3 backup files
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                 os.makedirs(log_dir) # Create log directory if it doesn't exist

            # Use RotatingFileHandler
            # You might want to add maxBytes and backupCount to your config.py
            max_bytes = 5 * 1024 * 1024 # 5 MB
            backup_count = 3
            file_handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG) # Set level for this handler
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

        self._initialized = True # Mark as initialized

    # --- Updated Wrapper Methods ---
    # Accept *args and **kwargs and pass them through

    def info(self, message: str, *args, **kwargs) -> None:
        """Logs a message with level INFO."""
        self.logger.info(message, *args, **kwargs)

    def debug(self, message: str, *args, **kwargs) -> None:
        """Logs a message with level DEBUG."""
        self.logger.debug(message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs) -> None:
        """Logs a message with level WARNING."""
        self.logger.warning(message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs) -> None:
        """Logs a message with level ERROR. Use exc_info=True to log exception info."""
        self.logger.error(message, *args, **kwargs)

    def critical(self, message: str, *args, **kwargs) -> None:
        """Logs a message with level CRITICAL."""
        self.logger.critical(message, *args, **kwargs)

    def exception(self, message: str, *args, **kwargs) -> None:
        """
        Logs a message with level ERROR including exception information.
        Convenience method: Call this from an except block.
        """
        # exc_info=True is implicitly added by logger.exception
        self.logger.exception(message, *args, **kwargs)


# Keep the main block for basic testing if desired
def main():
    # Test basic logging
    logger = Logger("test_logger", "test_app.log") # Use different name/file for test
    logger.info("Info message from main")
    logger.debug("Debug message from main (will go to file, not console by default)")
    logger.warning("Warning message from main")

    # Test exception logging
    try:
        result = 1 / 0
    except ZeroDivisionError:
        logger.error("An error occurred during division.", exc_info=True) # Using error
        logger.exception("Same error logged using logger.exception().") # Using exception

    # Test argument formatting
    user = "Alice"
    logger.info("User %s logged in.", user)


if __name__ == "__main__":
    main()
