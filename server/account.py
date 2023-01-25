from brownie.network.account import Account
from brownie.network.account import Accounts
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


    def get_account_with_offset(self, mnemonic:str, offset:int) -> Account:
        return Accounts().from_mnemonic(
            mnemonic,
            count=1,
            offset=offset)
