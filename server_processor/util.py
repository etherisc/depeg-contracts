from datetime import datetime

from brownie import Contract
from web3 import Web3


def s2b(text: str):
    return '{:0<66}'.format(Web3.toHex(text.encode('ascii')))[:66]


def get_block_time() -> int:
    return get_unix_time()


def get_unix_time() -> int:
    """get current unix time (in seconds)"""
    dt = datetime.now()
    return int(dt.timestamp())


def contract_from_address(contract_class, contract_address):
    return Contract.from_abi(
        contract_class._name,
        contract_address,
        contract_class.abi)


def get_package(substring: str):
    for dependency in config[CONFIG_DEPENDENCIES]:
        if substring in dependency:
            print("using package '{}' for '{}'".format(
                dependency,
                substring))
            
            return project.load(dependency, raise_if_loaded=False)
    
    print("no package for substring '{}' found".format(substring))
    return None
