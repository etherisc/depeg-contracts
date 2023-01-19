import logging

from pydantic import (
    BaseModel,
    BaseSettings,
)

from server.node import BrownieNode
from server.product import Product

ENV_FILE = 'server/.env'
FEEDER_INTERVAL = 5

# setup logger
logger = logging.getLogger(__name__)


class Settings(BaseSettings):

    node: BrownieNode = BrownieNode()
    product_contract_address: str = ''
    product_owner_id: int = -1
    feeder_interval: int = FEEDER_INTERVAL

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info("(re)load settings from '%s'", ENV_FILE)


    class Config:
        case_sensitive = False
        env_nested_delimiter = '__'

        # enables reading env variables from .env file
        env_file = ENV_FILE
        env_file_encoding = 'utf-8'
