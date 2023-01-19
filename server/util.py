from datetime import datetime

from brownie import Contract
from web3 import Web3


def s2b(text: str):
    return '{:0<66}'.format(Web3.toHex(text.encode('ascii')))[:66]


def get_block_time():
    dt = datetime.now()
    return int(dt.timestamp())


def contract_from_address(contract_class, contract_address):
    return Contract.from_abi(
        contract_class._name,
        contract_address,
        contract_class.abi)

