import logging

from pydantic import (
    BaseModel,
    BaseSettings,
)

from server.node import BrownieNode

ENV_FILE = 'server/.env'
INTERVAL = 5

# setup logger
logger = logging.getLogger(__name__)


class Settings(BaseSettings):

    demo: str
    node: BrownieNode = BrownieNode()
    interval: int = INTERVAL 


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info("(re)load settings from '%s'", ENV_FILE)


    class Config:
        case_sensitive = False
        env_nested_delimiter = '__'

        # enables reading env variables from .env file
        env_file = ENV_FILE
        env_file_encoding = 'utf-8'
