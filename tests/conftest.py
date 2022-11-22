import pytest

from brownie import (
    Wei,
    Contract, 
    USD1,
    USD2,
    DepegProduct,
    DepegRiskpool,
    GifStaking,
    DIP
)

from brownie.network import accounts
from brownie.network.account import Account

from scripts.const import ACCOUNTS_MNEMONIC

from scripts.util import (
    get_account,
    get_package,
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

def get_filled_account(accounts, account_no, funding) -> Account:
    owner = get_account(ACCOUNTS_MNEMONIC, account_no)
    accounts[account_no].transfer(owner, funding)
    return owner

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

#=== actor account fixtures  ===========================================#

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

#=== access to gif-contracts contract classes  =======================#

@pytest.fixture(scope="module")
def gifi(): return get_package('gif-interface')

@pytest.fixture(scope="module")
def gif(): return get_package('gif-contracts')

#=== stable coin fixtures ============================================#

@pytest.fixture(scope="module")
def usd1(instanceOperator) -> USD1: return USD1.deploy({'from': instanceOperator})

@pytest.fixture(scope="module")
def usd2(instanceOperator) -> USD2: return USD2.deploy({'from': instanceOperator})

@pytest.fixture(scope="module")
def dip(instanceOperator) -> DIP: return DIP.deploy({'from': instanceOperator})

@pytest.fixture(scope="module")
def testCoin(instanceOperator, gif) -> Contract: return gif.TestCoin.deploy({'from':instanceOperator})

#=== gif instance fixtures ====================================================#

@pytest.fixture(scope="module")
def registry(instanceOperator, gif) -> GifRegistry: return GifRegistry(instanceOperator, gif)

@pytest.fixture(scope="module")
def instance(instanceOperator, instanceWallet, gif) -> GifInstance: return GifInstance(instanceOperator, instanceWallet, gif)

@pytest.fixture(scope="module")
def instanceService(instance): return instance.getInstanceService()

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
def gifDepegProduct(gifDepegDeploy) -> GifDepegProduct: return gifDepegDeploy.getProduct()

@pytest.fixture(scope="module")
def product(gifDepegProduct) -> DepegProduct: return gifDepegProduct.getContract()

@pytest.fixture(scope="module")
def riskpool(gifDepegProduct) -> DepegRiskpool: return gifDepegProduct.getRiskpool().getContract()


#=== staking contract fixtures ====================================================#


@pytest.fixture(scope="module")
def gifStakingEmpty(
    instance,
    instanceService,
    instanceOperator,
    dip
) -> GifStaking: 
    return GifStaking.deploy(dip, {'from': instanceOperator})


@pytest.fixture(scope="module")
def gifStaking(
    instance,
    instanceService,
    instanceOperator,
    dip
) -> GifStaking: 
    staking = GifStaking.deploy(dip, {'from': instanceOperator})
    staking.registerGifInstance(
        instanceService.getInstanceId(),
        instanceService.getChainId(),
        instance.getRegistry()
    )

    return staking

