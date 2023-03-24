import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    USD1,
    USD2,
)

from scripts.util import b2s
from scripts.depeg_product import (
    GifDepegProduct,
    GifDepegRiskpool,
)

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass

def test_gif_product(
    gifDepegProduct: GifDepegProduct,
    riskpoolWallet: Account,
    usd1: USD1,
):
    gifDepegRiskpool = gifDepegProduct.getRiskpool()

    print('gifDepegProduct {}'.format(gifDepegProduct))
    print('gifDepegRiskpool {}'.format(gifDepegRiskpool))
    print('riskpoolWallet {}'.format(riskpoolWallet))
    print('getToken() {}'.format(gifDepegProduct.getToken()))
    print('usd1 {}'.format(usd1))

    product = gifDepegProduct.getContract()
    riskpool = gifDepegRiskpool.getContract()

    print('product {} id {} name {}'.format(
        product,
        product.getId(),
        b2s(product.getName())
    ))

    print('riskpool {} id {} name {}'.format(
        riskpool,
        riskpool.getId(),
        b2s(riskpool.getName())
    ))


def test_product_deploy(
    instanceService,
    instanceOperator,
    productOwner,
    riskpoolKeeper,
    product,
    usdc_feeder,
    riskpool,
    riskpoolWallet: Account,
    usd1: USD1,
    usd2: USD2,
):
    # check role assignements
    poRole = instanceService.getProductOwnerRole()
    rkRole = instanceService.getRiskpoolKeeperRole()

    assert instanceService.getInstanceOperator() == instanceOperator
    assert instanceService.hasRole(poRole, productOwner)
    assert instanceService.hasRole(rkRole, riskpoolKeeper)

    # check deployed product, oracle
    assert instanceService.products() == 1
    assert instanceService.oracles() == 0
    assert instanceService.riskpools() == 1

    assert instanceService.getComponent(product.getId()) == product 
    assert instanceService.getComponent(riskpool.getId()) == riskpool 

    # check token
    assert usdc_feeder.getToken() == usd1
    assert usd1.symbol() == 'USDC'
    assert usd2.symbol() == 'USDT'

    # check product
    assert product.getPriceDataProvider() == usdc_feeder
    assert product.getProtectedToken() == usd1 # usdc
    assert product.getToken() == usd2 # usdt
    assert product.getRiskpoolId() == riskpool.getId()

    # check riskpool
    assert riskpool.getWallet() == riskpoolWallet
    assert riskpool.getErc20Token() == usd2 # usdt
    assert riskpool.getSumInsuredPercentage() == 100

    # sum insured % checks
    percentage = 100
    target_price = product.getTargetPrice()
    protected_price = ((100 - percentage) * target_price) / 100
    protected_balance = 5000 * 10 ** usd1.decimals()
    sum_insured = (percentage * protected_balance) / 100

    assert target_price == 10 ** usdc_feeder.decimals()
    assert protected_balance == sum_insured
    assert protected_price == 0

    assert riskpool.getSumInsuredPercentage() == percentage
    assert riskpool.calculateSumInsured(protected_balance) == sum_insured
    assert riskpool.getProtectedMinDepegPrice(target_price) == protected_price

    assert riskpool.depegPriceIsBelowProtectedDepegPrice(protected_price + 1, target_price) is False
    assert riskpool.depegPriceIsBelowProtectedDepegPrice(protected_price + 0, target_price) is False
    # check negative number not allowed
