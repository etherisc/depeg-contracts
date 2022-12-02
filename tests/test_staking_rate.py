import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    web3,
    GifStaking,
    DIP,
    USD1,
    USD3
)

from scripts.setup import create_bundle

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


def test_happy_case(
    instanceOperator,
    gifStaking: GifStaking,
    dip: DIP,
    usd1: USD1,
    usd3: USD3
):
    gifStaking.setDipContract(dip.address, {'from': instanceOperator})

    parityLevel = gifStaking.getDipToTokenParityLevel()
    stakingRate = parityLevel / 10 # 1 dip unlocks 10 cents (usd1)
    
    # set staking rate for usd1
    gifStaking.setDipStakingRate(
        web3.chain_id, 
        usd1.address, 
        1,
        stakingRate,
        {'from': instanceOperator})
    
    # set staking rate for usd3
    gifStaking.setDipStakingRate(
        web3.chain_id, 
        usd3.address, 
        1,
        stakingRate,
        {'from': instanceOperator})

    oneDip = 10**dip.decimals()
    oneUsd1 = 10**usd1.decimals()
    oneUsd3 = 10**usd3.decimals()

    assert oneUsd1 != oneUsd3

    usd1Amount = gifStaking.calculateTokenAmountFromStaking(10 * oneDip, web3.chain_id, usd1.address)
    usd3Amount = gifStaking.calculateTokenAmountFromStaking(10 * oneDip, web3.chain_id, usd3.address)

    assert usd1Amount == oneUsd1
    assert usd3Amount == oneUsd3
