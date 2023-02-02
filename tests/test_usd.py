import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    chain,
    web3,
    USD1,
    USD2,
    DIP
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


def test_usd1_transfer(
    instanceOperator: Account,
    usd1: USD1,
    customer: Account,
    investor: Account
):
    block_number = web3.eth.block_number

    chain.mine(3)
    balance0 = usd1.balanceOf(customer)
    assert balance0 == 0

    # LogUsd1Transfer(from, to, amount, block.timestamp, block.number);
    amount1 = 987 * 10 ** usd1.decimals()
    amount2 = 200 * 10 ** usd1.decimals()
    amount3 = 1

    tx1 = usd1.transfer(customer, amount1, {'from':instanceOperator})
    balance1 = usd1.balanceOf(customer)
    assert balance1 == amount1

    assert 'LogUsd1TransferFrom' in tx1.events
    assert tx1.events['LogUsd1TransferFrom']['from'] == instanceOperator
    assert tx1.events['LogUsd1TransferFrom']['to'] == customer
    assert tx1.events['LogUsd1TransferFrom']['amount'] == amount1
    assert tx1.events['LogUsd1TransferFrom']['blockNumber'] == block_number + 3 + 1
    block_number += 4

    chain.sleep(10)
    chain.mine(1)

    tx2 = usd1.transfer(investor, amount2, {'from':customer})
    balance2 = usd1.balanceOf(customer)
    assert balance2 == amount1 - amount2

    assert 'LogUsd1TransferFrom' in tx2.events
    assert tx2.events['LogUsd1TransferFrom']['from'] == customer
    assert tx2.events['LogUsd1TransferFrom']['to'] == investor
    assert tx2.events['LogUsd1TransferFrom']['amount'] == amount2
    assert tx2.events['LogUsd1TransferFrom']['blockNumber'] == block_number + 1 + 1
    block_number += 2

    chain.sleep(10)
    chain.mine(5)

    tx3 = usd1.transfer(customer, amount3, {'from':investor})
    balance3 = usd1.balanceOf(customer)
    assert balance3 == amount1 - amount2 + amount3

    assert 'LogUsd1TransferFrom' in tx3.events
    assert tx3.events['LogUsd1TransferFrom']['from'] == investor
    assert tx3.events['LogUsd1TransferFrom']['to'] == customer
    assert tx3.events['LogUsd1TransferFrom']['amount'] == amount3
    assert tx3.events['LogUsd1TransferFrom']['blockNumber'] == block_number + 5 + 1
    block_number += 6


def test_usd2(
    instanceOperator: Account,
    usd2: USD2,
):
    assert usd2.symbol() == 'USDT'
    assert usd2.balanceOf(instanceOperator) == 1000000000000000000000000


def test_dip(
    instanceOperator: Account,
    dip: DIP,
):
    assert dip.symbol() == 'DIP'
    assert dip.decimals() == 18
    assert dip.balanceOf(instanceOperator) == 10**9 * 10**18
