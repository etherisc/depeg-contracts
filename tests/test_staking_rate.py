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
    gifStaking.registerToken(usd1.address, {'from': instanceOperator})
    gifStaking.setDipStakingRate(
        usd1.address, 
        web3.chain_id, 
        stakingRate,
        {'from': instanceOperator})
    
    # set staking rate for usd3
    gifStaking.registerToken(usd3.address, {'from': instanceOperator})
    gifStaking.setDipStakingRate(
        usd3.address, 
        web3.chain_id, 
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


def test_conversion_calculation_usd1(
    instanceOperator,
    gifStaking: GifStaking,
    dip: DIP,
    usd1: USD1
):
    gifStaking.setDipContract(dip.address, {'from': instanceOperator})

    parity_level = gifStaking.getDipToTokenParityLevel()
    staking_rate = parity_level / 10 # 1 dip unlocks 10 cents (usd1)
    
    # set staking rate for usd1
    gifStaking.registerToken(usd1.address, {'from': instanceOperator})
    gifStaking.setDipStakingRate(
        usd1.address, 
        web3.chain_id, 
        staking_rate,
        {'from': instanceOperator})
    
    # calculate dips needed to support 25 usd1
    mult_usd1 = 10**usd1.decimals() 
    target_usd1 = 25
    target_amount = target_usd1 * mult_usd1
    rerquired_dip = gifStaking.calculateRequiredStakingAmount(
        web3.chain_id, 
        usd1.address, 
        target_amount)
    
    supported_usd1 = gifStaking.calculateTokenAmountFromStaking(
        rerquired_dip, 
        web3.chain_id, 
        usd1.address);

    print('staking_rate {} target_usd1 {} rerquired_dip {} supported_usd1 {}'.format(
        staking_rate,
        target_usd1,
        rerquired_dip,
        supported_usd1))
    
    assert target_amount == supported_usd1


def test_conversion_calculation_usd3(
    instanceOperator,
    gifStaking: GifStaking,
    dip: DIP,
    usd3: USD1
):
    gifStaking.setDipContract(dip.address, {'from': instanceOperator})

    parity_level = gifStaking.getDipToTokenParityLevel()
    staking_rate = parity_level / 4 # 1 dip unlocks 25 cents (usd3)
    
    # set staking rate for usd1
    gifStaking.registerToken(usd3.address, {'from': instanceOperator})
    gifStaking.setDipStakingRate(
        usd3.address, 
        web3.chain_id, 
        staking_rate,
        {'from': instanceOperator})
    
    # calculate dips needed to support 25 usd1
    mult_usd3 = 10**usd3.decimals() 
    target_usd3 = 39
    target_amount = target_usd3 * mult_usd3

    rerquired_dip = gifStaking.calculateRequiredStakingAmount(
        web3.chain_id, 
        usd3.address, 
        target_amount)
    
    supported_usd3 = gifStaking.calculateTokenAmountFromStaking(
        rerquired_dip, 
        web3.chain_id, 
        usd3.address);

    print('staking_rate {} target_usd3 {} rerquired_dip {} supported_usd3 {}'.format(
        staking_rate,
        target_usd3,
        rerquired_dip,
        target_amount))
    
    assert target_amount == supported_usd3
