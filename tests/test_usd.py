import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    USD1,
    USD2,
)

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass

def test_usd1(
    instanceOperator: Account,
    usd1: USD1,
):
    assert usd1.symbol() == 'USDC'
    assert usd1.balanceOf(instanceOperator) == 1000000000000000000000000


def test_usd2(
    instanceOperator: Account,
    usd2: USD2,
):
    assert usd2.symbol() == 'USDT'
    assert usd2.balanceOf(instanceOperator) == 1000000000000000000000000
