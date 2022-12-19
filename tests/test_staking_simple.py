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
    dip: DIP,
):
    instanceId = instanceService.getInstanceId()
    bundleId = create_bundle(instance, instanceOperator, investor, riskpool)
    token = instanceService.getComponentToken(riskpool.getId())
    gifStaking.registerToken(token)

    assert gifStaking.bundles() == 0

    gifStaking.updateBundleState(instanceId, bundleId)

    assert gifStaking.bundles() == 1

    bundleKey = gifStaking.getBundleKey(0).dict()
    assert bundleKey['instanceId'] == instanceId
    assert bundleKey['bundleId'] == bundleId

    with brownie.reverts('ERROR:STK-063:BUNDLE_INDEX_TOO_LARGE'):
        gifStaking.getBundleKey(1)

    print('--- test setup before any staking ---')
    assert gifStaking.stakes(instanceId, bundleId, staker) == 0
    assert dip.balanceOf(gifStaking) == 0

    with brownie.reverts("ERROR:STK-080:ACCOUNT_WITHOUT_STAKING_RECORD"):
        gifStaking.getStakeInfo(instanceId, bundleId, staker)

    print('--- test setup after first staking ---')
    stakingAmount = 10**5 * 10**dip.decimals()
    gifStaking.stake(instanceId, bundleId, stakingAmount, {'from': staker})

    assert gifStaking.stakes(instanceId, bundleId, staker) == stakingAmount
    assert dip.balanceOf(gifStaking) == stakingAmount

    stakeInfo = gifStaking.getStakeInfo(instanceId, bundleId, staker).dict()
    print('stakeInfo {}'.format(stakeInfo))

    assert stakeInfo['staker'] == staker
    assert stakeInfo['key'][0] == instanceId
    assert stakeInfo['key'][1] == bundleId
    assert stakeInfo['balance'] == stakingAmount
    assert stakeInfo['createdAt'] > 0
    assert stakeInfo['updatedAt'] == stakeInfo['createdAt']

    print('--- test setup after second increased staking ---')
    chain.sleep(1) # force updatedAt > createdAt
    increaseAmount = 5 * 10**4 * 10**dip.decimals()
    gifStaking.stake(instanceId, bundleId, increaseAmount, {'from': staker})

    assert gifStaking.stakes(instanceId, bundleId, staker) == stakingAmount + increaseAmount
    assert dip.balanceOf(gifStaking) == stakingAmount + increaseAmount

    stakeInfo2 = gifStaking.getStakeInfo(instanceId, bundleId, staker).dict()
    print('stakeInfo2 {}'.format(stakeInfo2))

    assert stakeInfo2['balance'] == stakingAmount + increaseAmount
    assert stakeInfo2['createdAt'] == stakeInfo['createdAt']
    assert stakeInfo2['updatedAt'] > stakeInfo['createdAt']

    print('--- test setup after withdrawal of some staking ---')
    chain.sleep(1)

    withdrawalAmount = 7 * 10**4 * 10**dip.decimals()
    gifStaking.withdraw(instanceId, bundleId, withdrawalAmount, {'from': staker})

    assert gifStaking.stakes(instanceId, bundleId, staker) == stakingAmount + increaseAmount - withdrawalAmount
    assert dip.balanceOf(gifStaking) == stakingAmount + increaseAmount - withdrawalAmount

    stakeInfo3 = gifStaking.getStakeInfo(instanceId, bundleId, staker).dict()
    print('stakeInfo3 {}'.format(stakeInfo3))

    assert stakeInfo3['balance'] == stakingAmount + increaseAmount - withdrawalAmount
    assert stakeInfo3['createdAt'] == stakeInfo['createdAt']
    assert stakeInfo3['updatedAt'] > stakeInfo2['createdAt']

    print('--- test setup after withdrawal of remaining staking ---')
    chain.sleep(1)
    gifStaking.withdraw(instanceId, bundleId, {'from': staker})

    assert gifStaking.stakes(instanceId, bundleId, staker) == 0
    assert dip.balanceOf(gifStaking) == 0

    stakeInfo4 = gifStaking.getStakeInfo(instanceId, bundleId, staker).dict()
    print('stakeInfo4 {}'.format(stakeInfo4))

    assert stakeInfo4['balance'] == 0
    assert stakeInfo4['createdAt'] == stakeInfo['createdAt']
    assert stakeInfo4['updatedAt'] > stakeInfo3['createdAt']
