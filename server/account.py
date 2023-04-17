import os

from brownie.network.account import Account
from brownie.network.account import Accounts
from loguru import logger
from pydantic import BaseModel


MNEMONIC_DEFAULT = 'candy maple cake sugar pudding cream honey rich smooth crumble sweet treat'
OFFSET_DEFAULT = 0


class BrownieAccount(BaseModel):

    mnemonic:str = MNEMONIC_DEFAULT
    offset:int = OFFSET_DEFAULT


    # TODO cleanup
    # def get_address(self) -> str:
    #     return self.get_account_with_offset(
    #         self.mnemonic,
    #         self.offset).address


    # def get_balance(self) -> str:
    #     return self.get_account_with_offset(
    #         self.mnemonic,
    #         self.offset).balance()

    def get_account(self) -> Account:
        return self.get_account_with_offset(
            self.mnemonic,
            self.offset)


    @classmethod
    def create_via_env(self, env_variable_mnemonic, env_variable_offset=None):
        logger.info('creating accoung using env variable {} ...'.format(env_variable))
        mnemonic = os.getenv(env_variable_mnemonic)
        offset = 0

        if env_variable_offset:
            offset = int(os.getenv(env_variable_offset))

        if mnemonic: 
            return BrownieAccount(mnemonic=mnemonic, offset=offset) 
        else: 
            return BrownieAccount(offset=offset)


    def get_account_with_offset(self, mnemonic:str, offset:int) -> Account:
        try:
            logger.info('creating account ...')
            return Accounts().from_mnemonic(
                mnemonic,
                count=1,
                offset=offset)
        except Exception as ex:
            logger.warning('failed to create account. check MONITOR_MNEMONIC.')
