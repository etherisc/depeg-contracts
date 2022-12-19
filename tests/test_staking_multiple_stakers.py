import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    chain,
    GifStaking,
    DIP,
)

from scripts.setup import create_bundle

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


def test_staking_happy_path(
    instance,
    instanceOperator,
    investor,
    riskpool,
    instanceService,
    gifStaking: GifStaking,
    staker,
    staker2,
    dip: DIP,
):
    print('--- test setup before any staking ---')
    instanceId = instanceService.getInstanceId()
    bundleId = create_bundle(instance, instanceOperator, investor, riskpool)
    gifStaking.registerToken(riskpool.getErc20Token())
    gifStaking.updateBundleState(instanceId, bundleId)

    reward100Percent = gifStaking.getReward100PercentLevel()
    reward20Percent = reward100Percent / 5
    gifStaking.setRewardPercentage(reward20Percent)

    initialDipBalance = 10**6 * 10**dip.decimals()
    dip.transfer(gifStaking, initialDipBalance, {'from':instanceOperator})

    assert gifStaking.stakes(instanceId, bundleId, staker) == 0
    assert gifStaking.stakes(instanceId, bundleId, staker2) == 0

    assert gifStaking.stakes(instanceId, bundleId) == 0
    assert gifStaking.stakes(instanceId) == 0
    assert gifStaking.stakes() == 0
    
    assert dip.balanceOf(gifStaking) == initialDipBalance

    print('--- test setup after first staking ---')
    stakingAmount = 10**5 * 10**dip.decimals()
    gifStaking.stake(instanceId, bundleId, stakingAmount, {'from': staker})
    gifStaking.stake(instanceId, bundleId, stakingAmount, {'from': staker2})

    assert gifStaking.stakes(instanceId, bundleId, staker) == stakingAmount
    assert gifStaking.stakes(instanceId, bundleId, staker2) == stakingAmount

    assert gifStaking.stakes(instanceId, bundleId) == 2 * stakingAmount
    assert gifStaking.stakes(instanceId) == 2 * stakingAmount
    assert gifStaking.stakes() == 2 * stakingAmount
    
    assert dip.balanceOf(gifStaking) == 2 * stakingAmount + initialDipBalance

    print('--- wait one year ---')
    chain.sleep(gifStaking.getOneYearDuration())
    chain.mine(1)

    print('--- test setup after increased staking ---')
    stakeInfo = gifStaking.getStakeInfo(instanceId, bundleId, staker)
    rewardAmount = gifStaking.calculateRewardsIncrement(stakeInfo)
    increaseAmount = 5 * 10**4 * 10**dip.decimals()
    gifStaking.stake(instanceId, bundleId, increaseAmount, {'from': staker})

    assert gifStaking.stakes(instanceId, bundleId, staker) == stakingAmount + rewardAmount + increaseAmount
    assert gifStaking.stakes(instanceId, bundleId, staker2) == stakingAmount

    totalStakes = 2 * stakingAmount + rewardAmount + increaseAmount
    assert gifStaking.stakes(instanceId, bundleId) == totalStakes
    assert gifStaking.stakes(instanceId) == totalStakes
    assert gifStaking.stakes() == totalStakes
    
    assert dip.balanceOf(gifStaking) == 2 * stakingAmount + increaseAmount + initialDipBalance

    print('--- test setup after withdrawal of some staking ---')
    chain.sleep(1) # force updatedAt > createdAt
    withdrawalAmount = 7 * 10**4 * 10**dip.decimals()
    gifStaking.withdraw(instanceId, bundleId, withdrawalAmount, {'from': staker})

    assert gifStaking.stakes(instanceId, bundleId, staker) == stakingAmount + rewardAmount + increaseAmount - withdrawalAmount
    assert gifStaking.stakes(instanceId, bundleId, staker2) == stakingAmount

    totalStakes = 2 * stakingAmount + rewardAmount + increaseAmount - withdrawalAmount
    assert gifStaking.stakes(instanceId, bundleId) == totalStakes
    assert gifStaking.stakes(instanceId) == totalStakes
    assert gifStaking.stakes() == totalStakes
    
    assert dip.balanceOf(gifStaking) == 2 * stakingAmount + increaseAmount - withdrawalAmount + initialDipBalance

    print('--- test setup after withdrawal of remaining staking ---')
    chain.sleep(1) # force updatedAt > createdAt
    gifStaking.withdraw(instanceId, bundleId, {'from': staker})

    assert gifStaking.stakes(instanceId, bundleId, staker) == 0
    assert gifStaking.stakes(instanceId, bundleId, staker2) == stakingAmount

    assert gifStaking.stakes(instanceId, bundleId) == stakingAmount
    assert gifStaking.stakes(instanceId) == stakingAmount
    assert gifStaking.stakes() == stakingAmount

    assert dip.balanceOf(gifStaking) == initialDipBalance + stakingAmount - rewardAmount
