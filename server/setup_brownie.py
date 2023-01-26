
from loguru import logger
from brownie import project

BROWNIE_PROJECT = 'Project'

def setup_brownie() -> None:
    """loads brownie configuration from file $PWD/brownie-config.yaml"""

    p = project.load('.', name=BROWNIE_PROJECT)
    p.load_config()
    logger.info("brownie project config loaded for 'brownie.project.{}'", BROWNIE_PROJECT)
