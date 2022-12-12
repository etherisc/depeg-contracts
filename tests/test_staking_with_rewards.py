import brownie
import pytest
import time

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


def test_staking_with_rewards(
    instance,
    instanceOperator,
    investor,
    riskpool,
    instanceService,
    gifStaking: GifStaking,
    staker,
    dip: DIP,
):
    instanceId = instanceService.getInstanceId()
    bundleId = create_bundle(instance, instanceOperator, investor, riskpool)
    gifStaking.updateBundleState(instanceId, bundleId)

    reward100Percent = gifStaking.getReward100PercentLevel()
    reward20Percent = reward100Percent / 5
    gifStaking.setRewardPercentage(reward20Percent)

    initialDipBalance = 10**6 * 10**dip.decimals()
    dip.transfer(gifStaking, initialDipBalance, {'from':instanceOperator})

    print('--- setup with initial staking ---')
    stakingAmount = 10**5 * 10**dip.decimals()
    gifStaking.stake(instanceId, bundleId, stakingAmount, {'from': staker})

    assert dip.balanceOf(gifStaking) == initialDipBalance + stakingAmount

    stakeInfo = gifStaking.getStakeInfo(instanceId, bundleId, staker)
    print('stakeInfo {}'.format(stakeInfo))

    assert stakeInfo[2] == stakingAmount
    assert gifStaking.calculateRewardsIncrement(stakeInfo) == 0 

    print('--- wait one year ---')
    chain.sleep(gifStaking.getOneYearDuration())
    chain.mine(1)

    rewardsIncrement = gifStaking.calculateRewardsIncrement(stakeInfo)
    print('amount {} rewardsIncrement {} percentage {}'.format(
        stakingAmount, rewardsIncrement, rewardsIncrement/stakingAmount
    ))

    assert rewardsIncrement == stakingAmount / 5

    print('--- increase stake by 1 ---')
    stakingIncrement = 1
    gifStaking.stake(instanceId, bundleId, stakingIncrement, {'from': staker})

    assert dip.balanceOf(gifStaking) == initialDipBalance + stakingAmount + stakingIncrement

    stakeInfo2 = gifStaking.getStakeInfo(instanceId, bundleId, staker).dict()
    print('stakeInfo2 {}'.format(stakeInfo2))

    assert stakeInfo2['balance'] == stakingAmount + rewardsIncrement + stakingIncrement
    assert stakeInfo2['updatedAt'] >= stakeInfo[4] + gifStaking.getOneYearDuration()

    print('--- partial stake withdrawal ---')
    withdrawalAmount = 70000000000000000000001
    gifStaking.withdraw(instanceId, bundleId, withdrawalAmount, {'from': staker})

    assert dip.balanceOf(gifStaking) == initialDipBalance + stakingAmount + stakingIncrement - withdrawalAmount

    stakeInfo3 = gifStaking.getStakeInfo(instanceId, bundleId, staker).dict()
    print('stakeInfo3 {}'.format(stakeInfo3))

    expectedBalance = 50000000000000000000000
    assert stakeInfo3['balance'] == expectedBalance

    print('--- remaining stake withdrawal ---')
    gifStaking.withdraw(instanceId, bundleId, {'from': staker})

    assert dip.balanceOf(gifStaking) == initialDipBalance + stakingAmount + stakingIncrement - withdrawalAmount - expectedBalance

    stakeInfo4 = gifStaking.getStakeInfo(instanceId, bundleId, staker).dict()
    print('stakeInfo4 {}'.format(stakeInfo4))

    expectedBalance = 0
    assert stakeInfo4['balance'] == expectedBalance
