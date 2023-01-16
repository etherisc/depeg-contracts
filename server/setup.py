import logging

from logging import config # 
from brownie import project

LOGGING_CONF = 'server/logging.conf'
BROWNIE_PROJECT = 'Project'

# setup logger
logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """loads logging configuration from file LOGGING_CONF"""
    logging.config.fileConfig(LOGGING_CONF, disable_existing_loggers=False)
    logger.info("logging config loaded from '%s'", LOGGING_CONF)


def setup_brownie() -> None:
    """loads brownie configuration from file $PWD/brownie-config.yaml"""
    p = project.load('.', name=BROWNIE_PROJECT)
    p.load_config()
    logger.info("brownie project config loaded for 'brownie.project.%s'", BROWNIE_PROJECT)
