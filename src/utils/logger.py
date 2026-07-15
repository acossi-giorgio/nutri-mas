import logging
from datetime import datetime
from pathlib import Path

LOGS_DIR = Path(__file__).parent.parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)
_RUN_TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
_LOG_FILEPATH = LOGS_DIR / f"{_RUN_TIMESTAMP}.log"


def get_logger(agent_name: str) -> logging.Logger:
    """Return the file logger shared by the current run."""
    logger = logging.getLogger(agent_name)
    logger.setLevel(logging.DEBUG)
    for handler in logger.handlers:
        if getattr(handler, "_nutri_agent_handler", False):
            return logger
    file_handler = logging.FileHandler(_LOG_FILEPATH, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler._nutri_agent_handler = True
    formatter = logging.Formatter(
        fmt=f"[{agent_name}] %(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.propagate = False
    return logger
