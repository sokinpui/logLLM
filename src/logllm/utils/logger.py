import logging

from ..config import config as cfg

class Logger:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Logger, cls).__new__(cls)
        return cls._instance

    def __init__(self, name: str = cfg.LOGGER_NAME, log_file: str = cfg.LOG_FILE):

        # check if logger is already initialized
        if not hasattr(self, 'logger'):

            self.logger = logging.getLogger(name)
            self.logger.setLevel(logging.DEBUG)

            file_handler = logging.FileHandler(log_file)
            console_handler = logging.StreamHandler()

            file_handler.setLevel(logging.DEBUG)
            console_handler.setLevel(logging.INFO)

            formatter = logging.Formatter('%(levelname)s - %(asctime)s - %(message)s')
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)

            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)

    def info(self, message : str) -> None:
        self.logger.info(message)

    def debug(self, message : str) -> None:
        self.logger.debug(message)

    def warning(self, message : str) -> None:
        self.logger.warning(message)

    def error(self, message : str) -> None:
        self.logger.error(message)

    def critical(self, message : str) -> None:
        self.logger.critical(message)

def main():
    logger = Logger("test", "test.log")
    logger.info("info message")
    logger.debug("debug message")
    logger.warning("warning message")
    logger.error("error message")
    logger.critical("critical message")

if __name__ == "__main__":
    main()
