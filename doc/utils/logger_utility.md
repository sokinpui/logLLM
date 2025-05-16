# Logger Utility (`logger.py`)

## File: `src/logllm/utils/logger.py`

### Overview

Provides a singleton `Logger` class for consistent logging across the application.

### Class: `Logger`

- **Purpose**: Singleton logger setup using Python's `logging` module. Configures handlers for console output (INFO level) and rotating file output (DEBUG level).
- **`**new**(cls, \*args, **kwargs)`\*\*: Ensures only one instance of the logger is created (Singleton pattern).
- **`__init__(self, name: str = cfg.LOGGER_NAME, log_file: str = cfg.LOG_FILE)`**: Initializes the logger (only runs once per instance). Sets up a `StreamHandler` (console) and `RotatingFileHandler` (file) with a detailed formatter. Creates log directory if needed.
- **Logging Methods** (`info`, `debug`, `warning`, `error`, `critical`, `exception`): Wrapper methods that call the corresponding methods on the underlying `logging.Logger` instance. They accept `*args` and `**kwargs` for flexible message formatting and logging options (like `exc_info=True`).
