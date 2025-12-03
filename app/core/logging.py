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

    # Dedicated error handler to stderr with human-readable format
    err_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.ERROR)
    stderr_handler.setFormatter(err_fmt)

    # File handler for easier post-mortem inspection
    try:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(fmt)
    except Exception:
        file_handler = None

    # Replace default handlers and also attach to uvicorn loggers
    logger.handlers = []
    logger.addHandler(stream_handler)
    logger.addHandler(stderr_handler)
    if file_handler:
        logger.addHandler(file_handler)

    uv_err = logging.getLogger("uvicorn.error")
    uv_err.setLevel(level)
    uv_err.handlers = []
    uv_err.addHandler(stream_handler)
    uv_err.addHandler(stderr_handler)
    if file_handler:
        uv_err.addHandler(file_handler)

    uv_access = logging.getLogger("uvicorn.access")
    uv_access.setLevel(level)
    uv_access.propagate = False

    # Suppress watchfiles noisy INFO logs
    logging.getLogger("watchfiles").setLevel(logging.ERROR)
    logging.getLogger("watchfiles.main").setLevel(logging.ERROR)
    logging.getLogger("watchfiles").propagate = False
    logging.getLogger("watchfiles.main").propagate = False
