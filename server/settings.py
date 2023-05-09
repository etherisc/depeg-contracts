from loguru import logger
from pydantic import (
    BaseModel,
    BaseSettings,
)

from server.node import BrownieNode

TITLE = "Depeg API Monitoring"
VERSION = 1.1
DESCRIPTION = "API Server to monitor price feed data for the USDC depeg protection product"

ENV_FILE = 'server/.env'
SCHEDULER_INTERVAL = 5

CHECKER_INTERVAL = 10
FEEDER_INTERVAL = 15

class Settings(BaseSettings):

    application_title:str = None
    application_version:str = None
    application_description:str = None

    logging_format:str = None
    logging_level:str = None

    node: BrownieNode = BrownieNode()

    product_contract_address: str = ''

    scheduler_interval: int = SCHEDULER_INTERVAL
    checker_interval: int = CHECKER_INTERVAL
    feeder_interval: int = FEEDER_INTERVAL

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.application_title = TITLE
        self.application_version = VERSION
        self.application_description = DESCRIPTION

        logger.info("(re)load settings from '{}'", ENV_FILE)


    class Config:
        case_sensitive = False
        env_nested_delimiter = '__'

        # enables reading env variables from .env file
        env_file = ENV_FILE
        env_file_encoding = 'utf-8'


settings = Settings()
