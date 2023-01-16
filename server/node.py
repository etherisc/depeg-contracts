import logging

from brownie import network
from brownie.network.account import Account
from pydantic import BaseModel

from server.account import BrownieAccount


NETWORK_DEFAULT = 'ganache'
ACCOUNT_DEFAULT = BrownieAccount()


# setup logger
logger = logging.getLogger(__name__)


class BrownieNode(BaseModel):

    network_id:str = NETWORK_DEFAULT
    account:BrownieAccount = ACCOUNT_DEFAULT


    def is_connected(self) -> bool:
        return network.is_connected()


    def connect(self) -> None:
        if network.is_connected():
            logger.info("already connected to network '%s'", self.network_id)
            return

        logger.info("connecting to network '%s'", self.network_id)
        network.connect(self.network_id)
        logger.info("successfully connected")


    def disconnect(self) -> None:
        logger.info("disconnecting from network '%s'", self.network_id)
        network.disconnect(self.network_id)
        logger.info("successfully disconnected")


    def get_status(self) -> dict:
        return {
            'network': self.network_id,
            'connected': self.is_connected(),
            'account': self.get_account().address
        }

    def get_brownie_account(self) -> BrownieAccount:
        return self.account

    def get_account(self) -> Account:
        return self.account.get_account()
