import brownie
import pytest

from brownie.network.account import Account
from brownie import (
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
    gifStaking.updateBundleState(instanceId, bundleId)

    assert gifStaking.stakes(instanceId, bundleId, staker) == 0

    with brownie.reverts("ERROR:STK-060:ACCOUNT_WITHOUT_STAKING_RECORD"):
        gifStaking.getStakeInfo(instanceId, bundleId, staker)

    stakingAmount = 10**5 * 10**dip.decimals()
    gifStaking.stake(instanceId, bundleId, stakingAmount, {'from': staker})

    assert gifStaking.stakes(instanceId, bundleId, staker) == stakingAmount

    stakeInfo = gifStaking.getStakeInfo(instanceId, bundleId, staker)
    print('stakeInfo {}'.format(stakeInfo))

    assert stakeInfo[0] == staker
    assert stakeInfo[1] == instanceId
    assert stakeInfo[2] == bundleId
    assert stakeInfo[3] == stakingAmount
    assert stakeInfo[4] > 0
    assert stakeInfo[5] == stakeInfo[4]
