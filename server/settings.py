from loguru import logger
from pydantic import (
    BaseModel,
    BaseSettings,
)

from server.node import BrownieNode

ENV_FILE = 'server/.env'
SCHEDULER_INTERVAL = 5

FEEDER_INTERVAL = 15

class Settings(BaseSettings):

    application_title:str = None
    application_version:str = None
    application_description:str = None

    logging_format:str = None
    logging_level:str = None

    node: BrownieNode = BrownieNode()

    product_contract_address: str = ''
    product_owner_id: int = -1

    scheduler_interval: int = SCHEDULER_INTERVAL
    feeder_interval: int = FEEDER_INTERVAL

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info("(re)load settings from '{}'", ENV_FILE)


    class Config:
        case_sensitive = False
        env_nested_delimiter = '__'

        # enables reading env variables from .env file
        env_file = ENV_FILE
        env_file_encoding = 'utf-8'


settings = Settings()
