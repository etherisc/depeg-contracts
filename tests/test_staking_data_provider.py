import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    chain,
    GifStaking,
    DIP,
    USD1
)

from scripts.setup import create_bundle

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


def test_staking_data_provider_minimal(
    instance,
    instanceOperator,
    investor,
    riskpool,
    instanceService,
    gifStaking: GifStaking,
    staker,
    staker2,
    usd1: USD1,
    dip: DIP,
):
    print('--- link gif staking to gif instance ---')
    instanceId = instanceService.getInstanceId()
    bundleId = create_bundle(instance, instanceOperator, investor, riskpool)

    gifStaking.updateBundleState(instanceId, bundleId)

    print('--- setup token exchange rate ---')
    chainId = instanceService.getChainId()
    leverageFactor = 0.1
    stakingRate = leverageFactor * gifStaking.getDipToTokenParityLevel() # 1 dip unlocks 10 cents (usd1)
    usd1Decimals = 1 # just dummy value, real value will be picked up on-chain
    
    gifStaking.setDipContract(dip.address, {'from': instanceOperator})
    gifStaking.setDipStakingRate(
        chainId, 
        usd1.address, 
        usd1Decimals,
        stakingRate,
        {'from': instanceOperator})

    print('--- add bundle stakes ---')
    amountInUnits = 10**5
    stakingAmount = amountInUnits * 10**dip.decimals()
    gifStaking.stake(instanceId, bundleId, stakingAmount, {'from': staker})
    gifStaking.stake(instanceId, bundleId, stakingAmount, {'from': staker2})

    print('--- check result via IStakingDataProvider api ---')
    expectedSupportedCapitalAmount = 2 * amountInUnits * 10**usd1.decimals() * leverageFactor

    assert gifStaking.getBundleStakes(instanceId, bundleId) == 2 * stakingAmount
    assert gifStaking.getSupportedCapitalAmount(instanceId, bundleId, usd1) == expectedSupportedCapitalAmount
