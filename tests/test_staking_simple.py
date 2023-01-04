import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    chain,
    BundleRegistry,
    Staking,
    DIP,
)

from scripts.setup import new_bundle

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


def test_staking_happy_path(
    instance,
    instanceOperator,
    investor: Account,
    riskpool,
    instanceService,
    bundleRegistry: BundleRegistry,
    staking: Staking,
    stakerWithDips: Account,
    dip: DIP,
):
    instance_id = instanceService.getInstanceId()
    riskpool_id = riskpool.getId()
    bundle_name = 'bundle-1'
    bundle_id = new_bundle(
        instance,
        instanceOperator,
        investor,
        riskpool,
        bundle_name)

    token = instanceService.getComponentToken(riskpool_id)
    bundleRegistry.registerToken(token)
    staking.setDipContract(dip)

    bundle = riskpool.getBundleInfo(bundle_id).dict()
    print('bundle {}'.format(bundle))

    # register token, instance, component and bundle
    bundle_expiry_at = bundle['createdAt'] + bundle['lifetime']
    bundleRegistry.registerInstance(instance.getRegistry())
    bundleRegistry.registerComponent(instance_id, riskpool_id)

    assert bundleRegistry.bundles(instance_id, riskpool_id) == 0

    bundleRegistry.registerBundle(instance_id, riskpool_id, bundle_id, bundle_name, bundle_expiry_at)
    assert bundleRegistry.bundles(instance_id, riskpool_id) == 1

    print('--- test setup before any staking ---')
    assert staking.hasBundleStakeInfo(instance_id, bundle_id, stakerWithDips) is False
    assert staking.getBundleStakes(instance_id, bundle_id, stakerWithDips) == 0
    assert dip.balanceOf(staking.getStakingWallet()) == 0

    print('--- test setup after first staking ---')
    staking_amount = 10**5 * 10**dip.decimals()
    dip.approve(staking.getStakingWallet(), staking_amount, {'from': stakerWithDips})

    staking.stakeForBundle(instance_id, bundle_id, staking_amount, {'from': stakerWithDips})

    assert staking.hasBundleStakeInfo(instance_id, bundle_id, stakerWithDips) is True
    assert staking.getBundleStakes(instance_id, bundle_id, stakerWithDips) == staking_amount
    assert dip.balanceOf(staking.getStakingWallet()) == staking_amount

    stake_info = staking.getBundleStakeInfo(instance_id, bundle_id, stakerWithDips).dict()
    print('stake_info {}'.format(stake_info))

    assert stake_info['user'] == stakerWithDips
    assert stake_info['key'][0] == instance_id
    assert stake_info['key'][1] == bundle_id
    assert stake_info['balance'] == staking_amount
    assert stake_info['createdAt'] > 0
    assert stake_info['updatedAt'] == stake_info['createdAt']

    print('--- test setup after second increased staking ---')
    chain.sleep(1) # force updatedAt > createdAt
    increase_amount = 5 * 10**4 * 10**dip.decimals()
    dip.approve(staking.getStakingWallet(), increase_amount, {'from': stakerWithDips})

    staking.stakeForBundle(instance_id, bundle_id, increase_amount, {'from': stakerWithDips})

    assert staking.getBundleStakes(instance_id, bundle_id, stakerWithDips) == staking_amount + increase_amount
    assert dip.balanceOf(staking.getStakingWallet()) == staking_amount + increase_amount

    stake_info2 = staking.getBundleStakeInfo(instance_id, bundle_id, stakerWithDips).dict()
    print('stake_info2 {}'.format(stake_info2))

    assert stake_info2['balance'] == staking_amount + increase_amount
    assert stake_info2['createdAt'] == stake_info['createdAt']
    assert stake_info2['updatedAt'] > stake_info['createdAt']

    print('--- test setup after withdrawal of some staking ---')
    chain.sleep(1)

    withdrawalAmount = 7 * 10**4 * 10**dip.decimals()
    staking.unstakeFromBundle(instance_id, bundle_id, withdrawalAmount, {'from': stakerWithDips})

    assert staking.getBundleStakes(instance_id, bundle_id, stakerWithDips) == staking_amount + increase_amount - withdrawalAmount
    assert dip.balanceOf(staking.getStakingWallet()) == staking_amount + increase_amount - withdrawalAmount

    stake_info3 = staking.getBundleStakeInfo(instance_id, bundle_id, stakerWithDips).dict()
    print('stake_info3 {}'.format(stake_info3))

    assert stake_info3['balance'] == staking_amount + increase_amount - withdrawalAmount
    assert stake_info3['createdAt'] == stake_info['createdAt']
    assert stake_info3['updatedAt'] > stake_info2['createdAt']

    print('--- test setup after withdrawal of remaining staking ---')
    chain.sleep(1)
    staking.unstakeFromBundle(instance_id, bundle_id, {'from': stakerWithDips})

    assert staking.getBundleStakes(instance_id, bundle_id, stakerWithDips) == 0
    assert dip.balanceOf(staking.getStakingWallet()) == 0

    stake_info4 = staking.getBundleStakeInfo(instance_id, bundle_id, stakerWithDips).dict()
    print('stake_info4 {}'.format(stake_info4))

    assert stake_info4['balance'] == 0
    assert stake_info4['createdAt'] == stake_info['createdAt']
    assert stake_info4['updatedAt'] > stake_info3['createdAt']


def test_staking_failure_modes(
    instance,
    instanceOperator,
    investor: Account,
    riskpool,
    instanceService,
    bundleRegistry: BundleRegistry,
    staking: Staking,
    stakerWithDips: Account,
    dip: DIP,
):
    instance_id = instanceService.getInstanceId()
    riskpool_id = riskpool.getId()
    bundle_name = 'bundle-1'
    bundle_id = new_bundle(
        instance,
        instanceOperator,
        investor,
        riskpool,
        bundle_name)

    # register token, instance, component (not bundle, yet)
    token = instanceService.getComponentToken(riskpool_id)
    bundleRegistry.registerToken(token)
    staking.setDipContract(dip)
    bundle = riskpool.getBundleInfo(bundle_id).dict()
    bundle_expiry_at = bundle['createdAt'] + bundle['lifetime']
    bundleRegistry.registerInstance(instance.getRegistry())
    bundleRegistry.registerComponent(instance_id, riskpool_id)

    # 1st attempt to get bundle stake info
    with brownie.reverts("ERROR:STK-002:USER_WITHOUT_BUNDLE_STAKE_INFO"):
        staking.getBundleStakeInfo(instance_id, bundle_id, stakerWithDips)

    # 1st attempt to stake to bundle
    staking_amount = 10**5 * 10**dip.decimals()
    with brownie.reverts("ERROR:STK-040:BUNDLE_NOT_REGISTERED"):
        staking.stakeForBundle(instance_id, bundle_id, staking_amount, {'from': stakerWithDips})

    # 1st attempt to unstake from bundle
    with brownie.reverts("ERROR:STK-002:USER_WITHOUT_BUNDLE_STAKE_INFO"):
        staking.unstakeFromBundle(instance_id, bundle_id, staking_amount, {'from': stakerWithDips})

    # now register bundle
    bundleRegistry.registerBundle(instance_id, riskpool_id, bundle_id, bundle_name, bundle_expiry_at)

    # 2nd attempt to get bundle stake info
    with brownie.reverts("ERROR:STK-002:USER_WITHOUT_BUNDLE_STAKE_INFO"):
        staking.getBundleStakeInfo(instance_id, bundle_id, stakerWithDips)

    # 2nd attempt to stake to bundle
    with brownie.reverts("ERC20: insufficient allowance"):
        staking.stakeForBundle(instance_id, bundle_id, staking_amount, {'from': stakerWithDips})

    # 3rd attempt to get bundle stake info
    with brownie.reverts("ERROR:STK-002:USER_WITHOUT_BUNDLE_STAKE_INFO"):
        staking.getBundleStakeInfo(instance_id, bundle_id, stakerWithDips)

    with brownie.reverts("ERROR:STK-041:STAKING_AMOUNT_ZERO"):
        staking.stakeForBundle(instance_id, bundle_id, 0, {'from': stakerWithDips})

    # create approval and try again
    dip.approve(staking.getStakingWallet(), staking_amount, {'from': stakerWithDips})
    staking.stakeForBundle(instance_id, bundle_id, staking_amount, {'from': stakerWithDips})

    # 2nd attempt to unstake from bundle
    with brownie.reverts("ERROR:STK-050:WITHDRAWAL_AMOUNT_ZERO"):
        staking.unstakeFromBundle(instance_id, bundle_id, 0, {'from': stakerWithDips})

    # 3rd attempt to unstake from bundle
    with brownie.reverts("ERROR:STK-120:WITHDRAWAL_AMOUNT_EXCEEDS_STAKING_BALANCE"):
        staking.unstakeFromBundle(instance_id, bundle_id, staking_amount + 1, {'from': stakerWithDips})
