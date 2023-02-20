
from loguru import logger
from brownie import project

from scripts.util import get_package

BROWNIE_PROJECT = 'Project'
GIF = 'gif-contracts'

gif = None

def setup_brownie() -> None:
    global gif

    """loads brownie configuration from file $PWD/brownie-config.yaml"""

    p = project.load('.', name=BROWNIE_PROJECT)
    p.load_config()
    logger.info("brownie project config loaded for 'brownie.project.{}'", BROWNIE_PROJECT)

    gif = get_package(GIF)


