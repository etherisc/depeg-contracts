import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    chain,
    GifStaking,
    DIP,
    USD2
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
    stakerWithDips,
    staker2WithDips,
    usd2: USD2,
    dip: DIP,
):
    print('--- link gif staking to gif instance ---')
    instanceId = instanceService.getInstanceId()
    bundleId = create_bundle(instance, instanceOperator, investor, riskpool)

    gifStaking.registerToken(riskpool.getErc20Token(), {'from': instanceOperator})
    gifStaking.updateBundleState(instanceId, bundleId)

    print('--- setup token exchange rate ---')
    chainId = instanceService.getChainId()
    leverageFactor = 0.1
    stakingRate = leverageFactor * gifStaking.getDipToTokenParityLevel() # 1 dip unlocks 10 cents (usd2)

    gifStaking.setDipContract(dip.address, {'from': instanceOperator})
    gifStaking.setStakingRate(
        usd2.address, 
        chainId, 
        stakingRate,
        {'from': instanceOperator})

    print('--- add bundle stakes ---')
    amountInUnits = 10**5
    stakingAmount = amountInUnits * 10**dip.decimals()
    gifStaking.stake(instanceId, bundleId, stakingAmount, {'from': stakerWithDips})
    gifStaking.stake(instanceId, bundleId, stakingAmount, {'from': staker2WithDips})

    print('--- check result via IStakingDataProvider api ---')
    expectedSupportedCapitalAmount = 2 * amountInUnits * 10**usd2.decimals() * leverageFactor

    assert gifStaking.getBundleStakes(instanceId, bundleId) == 2 * stakingAmount
    assert gifStaking.getBundleCapitalSupport(instanceId, bundleId) == expectedSupportedCapitalAmount
    assert gifStaking.getBundleToken(instanceId, bundleId) == usd2
