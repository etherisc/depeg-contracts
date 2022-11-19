from web3 import Web3

from brownie import Contract
from brownie.convert import to_bytes
from brownie.network import accounts
from brownie.network.account import Account

from brownie import (
    Wei,
    interface,    
    Contract, 
    PolicyController,
    OracleService,
    ComponentOwnerService,
    InstanceOperatorService,
    InstanceService,
)

from scripts.util import (
    get_account,
    contract_from_address,
    s2b32,
)

from scripts.instance import GifInstance


class GifComponent(object):

    def __init__(self, 
        componentAddress: Account, 
    ):
        self.component = contract_from_address(interface.IComponent, componentAddress)
        self.instance = GifInstance(registryAddress=self.component.getRegistry())

        instanceService = self.instance.getInstanceService()
        instanceOperatorService = self.instance.getInstanceOperatorService()
        componentOwnerService = self.instance.getComponentOwnerService()
        riskpoolService = self.instance.getRiskpoolService()

        self.component = contract_from_address(interface.IComponent, componentAddress)
        self.instance = GifInstance(registryAddress=self.component.getRegistry())