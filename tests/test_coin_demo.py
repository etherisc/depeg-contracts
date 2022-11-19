import brownie
import pytest

from brownie.network.account import Account

def test_test_coin(
    instanceOperator: Account,
    testCoin,
):
    assert testCoin.symbol() == 'TDY'
    assert testCoin.balanceOf(instanceOperator) == 1000000000000000000000000
