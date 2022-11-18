import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    USD1,
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


def test_product(
    gifDepegProduct: GifDepegProduct,
    gifDepegRiskpool: GifDepegRiskpool,
    riskpoolWallet: Account,
    usd1: USD1,
):

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

    assert product.getRiskpoolId() == riskpool.getId()
    assert product.getToken() == usd1

    assert riskpool.getWallet() == riskpoolWallet
    assert riskpool.getErc20Token() == usd1
