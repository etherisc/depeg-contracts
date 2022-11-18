import pytest
import web3

from typing import Dict

from brownie import (
    Wei,
    Contract, 
    USD1,
    USD2,
    DepegProduct,
    DepegRiskpool
)

from brownie.network import accounts
from brownie.network.account import Account
from brownie.network.state import Chain

from scripts.const import (
    ACCOUNTS_MNEMONIC,
)

from scripts.instance_test import (
    GifRegistry,
    GifInstance,
)

from scripts.depeg_product import (
    GifDepegProduct,
    GifDepegRiskpool,
    GifDepegProductComplete,
)

from scripts.util import (
    contract_from_address,
    get_account,
    encode_function_data,
    s2h,
    s2b32,
)

GIF_CONTRACTS_PACKAGE = 'etherisc/gif-contracts@0a64b7e'

def get_filled_account(accounts, account_no, funding) -> Account:
    owner = get_account(ACCOUNTS_MNEMONIC, account_no)
    accounts[account_no].transfer(owner, funding)
    return owner

def get_address(name):
    with open('gif_instance_address.txt') as file:
        for line in file:
            if line.startswith(name):
                t = line.split('=')[1].strip()
                print('found {} in gif_instance_address.txt: {}'.format(name, t))
                return t
    return None

# fixtures with `yield` execute the code that is placed before the `yield` as setup code
# and code after `yield` is teardown code. 
# See https://docs.pytest.org/en/7.1.x/how-to/fixtures.html#yield-fixtures-recommended
@pytest.fixture(autouse=True)
def run_around_tests():
    try:
        yield
        # after each test has finished, execute one trx and wait for it to finish. 
        # this is to ensure that the last transaction of the test is finished correctly. 
    finally:
        accounts[8].transfer(accounts[9], 1)
        # dummy_account = get_account(ACCOUNTS_MNEMONIC, 999)
        # execute_simple_incrementer_trx(dummy_account)

@pytest.fixture(scope="module")
def instanceOperator(accounts) -> Account:
    return get_filled_account(accounts, 0, "1 ether")

@pytest.fixture(scope="module")
def instanceWallet(accounts) -> Account:
    return get_filled_account(accounts, 1, "1 ether")

@pytest.fixture(scope="module")
def riskpoolKeeper(accounts) -> Account:
    return get_filled_account(accounts, 4, "1 ether")

@pytest.fixture(scope="module")
def riskpoolWallet(accounts) -> Account:
    return get_filled_account(accounts, 5, "1 ether")

@pytest.fixture(scope="module")
def investor(accounts) -> Account:
    return get_filled_account(accounts, 6, "1 ether")

@pytest.fixture(scope="module")
def productOwner(accounts) -> Account:
    return get_filled_account(accounts, 7, "1 ether")

@pytest.fixture(scope="module")
def customer(accounts) -> Account:
    return get_filled_account(accounts, 9, "1 ether")

@pytest.fixture(scope="module")
def customer2(accounts) -> Account:
    return get_filled_account(accounts, 10, "1 ether")

@pytest.fixture(scope="module")
def theOutsider(accounts) -> Account:
    return get_filled_account(accounts, 19, "1 ether")

# @pytest.fixture(scope="module")
# def instance(instanceOperator, instanceWallet) -> GifInstance:
#     instance = GifInstance(
#         instanceOperator, 
#         registryAddress=get_address('registry'), 
#         instanceWallet=instanceWallet)

#=== stable coin fixtures ============================================#

@pytest.fixture(scope="module")
def usd1(instanceOperator) -> Contract: return USD1.deploy()

#=== gif contract class fixtures ============================================#

@pytest.fixture(scope="module")
def coreProxy(pm) -> Contract: return pm(GIF_CONTRACTS_PACKAGE).CoreProxy

@pytest.fixture(scope="module")
def registryController(pm) -> Contract: return pm(GIF_CONTRACTS_PACKAGE).RegistryController

@pytest.fixture(scope="module")
def bundleToken(pm) -> Contract: return pm(GIF_CONTRACTS_PACKAGE).BundleToken

@pytest.fixture(scope="module")
def riskpoolToken(pm) -> Contract: return pm(GIF_CONTRACTS_PACKAGE).RiskpoolToken

@pytest.fixture(scope="module")
def accessController(pm) -> Contract: return pm(GIF_CONTRACTS_PACKAGE).AccessController

@pytest.fixture(scope="module")
def componentController(pm) -> Contract: return pm(GIF_CONTRACTS_PACKAGE).ComponentController

@pytest.fixture(scope="module")
def queryModule(pm) -> Contract: return pm(GIF_CONTRACTS_PACKAGE).QueryModule

@pytest.fixture(scope="module")
def licenseController(pm) -> Contract: return pm(GIF_CONTRACTS_PACKAGE).LicenseController

@pytest.fixture(scope="module")
def policyController(pm) -> Contract: return pm(GIF_CONTRACTS_PACKAGE).PolicyController

@pytest.fixture(scope="module")
def bundleController(pm) -> Contract: return pm(GIF_CONTRACTS_PACKAGE).BundleController

@pytest.fixture(scope="module")
def poolController(pm) -> Contract: return pm(GIF_CONTRACTS_PACKAGE).PoolController

@pytest.fixture(scope="module")
def treasuryModule(pm) -> Contract: return pm(GIF_CONTRACTS_PACKAGE).TreasuryModule

@pytest.fixture(scope="module")
def policyDefaultFlow(pm) -> Contract: return pm(GIF_CONTRACTS_PACKAGE).PolicyDefaultFlow

@pytest.fixture(scope="module")
def instanceService(pm) -> Contract: return pm(GIF_CONTRACTS_PACKAGE).InstanceService

@pytest.fixture(scope="module")
def componentOwnerService(pm) -> Contract: return pm(GIF_CONTRACTS_PACKAGE).ComponentOwnerService

@pytest.fixture(scope="module")
def oracleService(pm) -> Contract: return pm(GIF_CONTRACTS_PACKAGE).OracleService

@pytest.fixture(scope="module")
def riskpoolService(pm) -> Contract: return pm(GIF_CONTRACTS_PACKAGE).RiskpoolService

@pytest.fixture(scope="module")
def productService(pm) -> Contract: return pm(GIF_CONTRACTS_PACKAGE).ProductService

@pytest.fixture(scope="module")
def instanceOperatorService(pm) -> Contract: return pm(GIF_CONTRACTS_PACKAGE).InstanceOperatorService

#=== deployed stable coin contracts fixtures ========================================#

@pytest.fixture(scope="module")
def usd1(instanceOperator) -> USD1: return USD1.deploy({'from': instanceOperator})

@pytest.fixture(scope="module")
def usd2(instanceOperator) -> USD2: return USD2.deploy({'from': instanceOperator})

#=== gif deployed contracts fixtures ========================================#

@pytest.fixture(scope="module")
def registry(instanceOperator, coreProxy, registryController) -> GifRegistry:
    return GifRegistry(instanceOperator, coreProxy, registryController)

@pytest.fixture(scope="module")
def instance(
    instanceOperator, 
    instanceWallet, 
    coreProxy,
    registryController, 
    bundleToken,
    riskpoolToken,
    accessController,
    componentController,
    queryModule,
    licenseController,
    policyController,
    bundleController,
    poolController,
    treasuryModule,
    policyDefaultFlow,
    instanceService,
    componentOwnerService,
    oracleService,
    riskpoolService,
    productService,
    instanceOperatorService,
) -> GifInstance:
    return GifInstance(
        instanceOperator, 
        instanceWallet, 
        coreProxy,
        registryController, 
        bundleToken,
        riskpoolToken,
        accessController,
        componentController,
        queryModule,
        licenseController,
        policyController,
        bundleController,
        poolController,
        treasuryModule,
        policyDefaultFlow,
        instanceService,
        componentOwnerService,
        oracleService,
        riskpoolService,
        productService,
        instanceOperatorService,
        )


#=== depeg deployed contracts fixtures ========================================#

@pytest.fixture(scope="module")
def gifDepegDeploy(
    instance: GifInstance, 
    productOwner: Account, 
    investor: Account, 
    usd1: USD1,
    riskpoolKeeper: Account, 
    riskpoolWallet: Account
) -> GifDepegProductComplete:
    return GifDepegProductComplete(
        instance, 
        productOwner, 
        investor,
        usd1,
        riskpoolKeeper, 
        riskpoolWallet)

@pytest.fixture(scope="module")
def gifDepegProduct(gifDepegDeploy) -> GifDepegProduct:
    return gifDepegDeploy.getProduct()

@pytest.fixture(scope="module")
def gifDepegRiskpool(gifDepegDeploy) -> GifDepegRiskpool:
    return gifDepegDeploy.getRiskpool()
