import csv
import tempfile

from datetime import datetime

from loguru import logger

from brownie import (
    project,
    Contract
)

from web3 import Web3

PROJECT_NAME = 'WorkspaceProject'

depeg_project = None


def get_project():
    global depeg_project

    if depeg_project:
        return depeg_project

    loaded_projects = project.get_loaded_projects()
    for loaded_project in loaded_projects:
        if loaded_project._name == PROJECT_NAME:
            depeg_project = loaded_project

    if not depeg_project:
        depeg_project = project.load('.', name=PROJECT_NAME)

    return depeg_project


def get_contracts(product_address:str):
    dp = get_project()

    product = contract_from_address(dp.DepegProduct, product_address)
    instance_registry = contract_from_address(dp.interface.IRegistry, product.getRegistry())
    instance_service = contract_from_address(dp.interface.IInstanceService, instance_registry.getContract(s2b('InstanceService')))

    riskpool = contract_from_address(dp.DepegRiskpool, instance_service.getComponent(product.getRiskpoolId()))
    staking = contract_from_address(dp.interface.IStakingFacadeExt, riskpool.getStaking())
    registry = contract_from_address(dp.interface.IChainRegistryFacadeExt, staking.getRegistry())

    return (
        product,
        riskpool,
        instance_service,
        registry,
        staking
    )


def s2b(text: str):
    return '{:0<66}'.format(Web3.toHex(text.encode('ascii')))[:66]

def b2s(b32: bytes):
    return b32.decode().split('\x00')[0]

def get_block_time() -> int:
    return get_unix_time()


def get_unix_time() -> int:
    """get current unix time (in seconds)"""
    dt = datetime.now()
    return int(dt.timestamp())


def timestamp_to_iso_date(timestamp:int) -> str:
    if timestamp == 0:
        return None

    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d")


def contract_from_address(contract_class, contract_address):
    return Contract.from_abi(
        contract_class._name,
        contract_address,
        contract_class.abi)


def write_csv_temp_file(data:dict, field_names:list[str]=None) -> str:
    if not field_names or len(field_names) == 0:
        keys = list(data.keys())
        if len(keys) >= 1:
            row_id = keys[0]
            row = data[row_id]
            logger.info('row_id: {}, row: {}'.format(row_id, row))

            field_names = list(row.keys())

    logger.info('csv field names: {}'.format(field_names))

    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp_file:
        temp_file_path = temp_file.name

    logger.info('csv file name: {}'.format(temp_file_path))

    with open(temp_file_path, 'w', newline='') as f:
        csv_writer = csv.DictWriter(f, field_names)
        csv_writer.writeheader()

        for key in data.keys():
            csv_writer.writerow(data[key])

    return temp_file_path
