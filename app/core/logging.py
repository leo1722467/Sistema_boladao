import logging
import sys
from pythonjsonlogger import jsonlogger

REQUEST_ID_KEY = "x_request_id"

def setup_logging(level: int = logging.INFO, log_file: str = "app-debug.log") -> None:
    logger = logging.getLogger()
    logger.setLevel(level)

    fmt = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s %(pathname)s %(lineno)d"
    )

    # Stream handler to stdout
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)

    # File handler for easier post-mortem inspection
    try:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(fmt)
    except Exception:
        file_handler = None

    # Replace default handlers (uvicorn installs its own)
    logger.handlers = []
    logger.addHandler(stream_handler)
    if file_handler:
        logger.addHandler(file_handler)
