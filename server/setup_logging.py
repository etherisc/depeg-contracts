# file mostly copied from https://gist.github.com/nkhitrov:
# https://gist.github.com/nkhitrov/a3e31cfcc1b19cba8e1b626276148c49
import logging
import sys
from pprint import pformat

# if you dont like imports of private modules
# you can move it to typing.py module
from loguru import logger
from loguru._defaults import LOGURU_FORMAT

from server.settings import Settings

LOGGING_DEBUG = 'DEBUG'
LOGGING_INFO = 'INFO'
LOGGING_WARNING = 'WARNING'
LOGGING_ERROR = 'ERROR'
LOGGING_CRITICAL = 'CRITICAL'

LOGGING_LEVEL = {
    LOGGING_DEBUG: logging.DEBUG,
    LOGGING_INFO: logging.INFO,
    LOGGING_WARNING: logging.WARNING,
    LOGGING_ERROR: logging.ERROR,
    LOGGING_CRITICAL: logging.CRITICAL
}

LOGGING_FORMAT = LOGURU_FORMAT
LOGGING_LEVEL_DEFAULT = logging.DEBUG


class InterceptHandler(logging.Handler):
    """
    Default handler from examples in loguru documentaion.
    See https://loguru.readthedocs.io/en/stable/overview.html#entirely-compatible-with-standard-logging
    """

    def emit(self, record: logging.LogRecord):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def format_record(record: dict) -> str:
    """
    Custom format for loguru loggers.
    Uses pformat for log any data like request/response body during debug.
    Works with logging if loguru handler it.

    Example:
    >>> payload = [{"users":[{"name": "Nick", "age": 87, "is_active": True}, {"name": "Alex", "age": 27, "is_active": True}], "count": 2}]
    >>> logger.bind(payload=).debug("users payload")
    >>> [   {   'count': 2,
    >>>         'users': [   {'age': 87, 'is_active': True, 'name': 'Nick'},
    >>>                      {'age': 27, 'is_active': True, 'name': 'Alex'}]}]
    """

    format_string = LOGGING_FORMAT
    if record["extra"].get("payload") is not None:
        record["extra"]["payload"] = pformat(
            record["extra"]["payload"], indent=4, compact=True, width=88
        )
        format_string += "\n<level>{extra[payload]}</level>"

    format_string += "{exception}\n"
    return format_string


def setup_logging(settings: Settings) -> None:
    """
    make uvicorn use loguru logging
    Replaces logging handlers with a handler for using the custom handler.
        
    WARNING!
    if you call the init_logging in startup event function, 
    then the first logs before the application start will be in the old format

    >>> app.add_event_handler("startup", init_logging)
    stdout:
    INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
    INFO:     Started reloader process [11528] using statreload
    INFO:     Started server process [6036]
    INFO:     Waiting for application startup.
    2020-07-25 02:19:21.357 | INFO     | uvicorn.lifespan.on:startup:34 - Application startup complete.
    """

    global LOGGING_FORMAT

    # disable handlers for specific uvicorn loggers
    # to redirect their output to the default uvicorn logger
    # works with uvicorn==0.11.6
    loggers = (
        logging.getLogger(name)
        for name in logging.root.manager.loggerDict
        if name.startswith("uvicorn.")
    )

    for uvicorn_logger in loggers:
        uvicorn_logger.handlers = []

    # change handler for default uvicorn logger
    intercept_handler = InterceptHandler()
    logging.getLogger("uvicorn").handlers = [intercept_handler]

    # update logging level from settings if available
    logging_level = LOGGING_LEVEL_DEFAULT

    if settings.logging_level and len(settings.logging_level) > 0:
        if settings.logging_level in LOGGING_LEVEL:
            logging_level = LOGGING_LEVEL[settings.logging_level]
            logger.info("setting logging level to {} ({})",
                settings.logging_level,
                logging_level)
        else:
            logger.warning("unsupported logging level '{}', using default instead", 
            settings.logging_level,
            logging_level)

    # update logging format from settings if available
    if settings.logging_format and len(settings.logging_format) > 0:
        logger.info('setting logging format to {}', settings.logging_format)
        LOGGING_FORMAT = settings.logging_format

    # set logs output, level and format
    logger.configure(
        handlers=[
            {
                "sink": sys.stdout,
                "level": logging_level,
                "format": format_record
            }
        ]
    )
