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

    def get_account(self) -> Account:
        return self.get_account_with_offset(
            self.mnemonic,
            self.offset)


    @classmethod
    def create_via_env(self, env_variable_mnemonic, env_variable_offset=None):
        logger.info('creating accoung using env variable {}/{}'.format(env_variable_mnemonic, env_variable_offset))

        account = None
        mnemonic = os.getenv(env_variable_mnemonic)
        offset = 0

        if env_variable_offset:
            offset = int(os.getenv(env_variable_offset, '0'))

        if mnemonic: 
            account = BrownieAccount(mnemonic=mnemonic, offset=offset) 
        else: 
            account = BrownieAccount(offset=offset)
        
        logger.info('account created: {}'.format(account.get_account()))

        return account


    def get_account_with_offset(self, mnemonic:str, offset:int) -> Account:
        try:
            return Accounts().from_mnemonic(
                mnemonic,
                count=1,
                offset=offset)
        except Exception as ex:
            logger.warning('failed to create account. check MONITOR_MNEMONIC.')
