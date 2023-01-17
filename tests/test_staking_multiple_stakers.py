import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    chain,
    BundleRegistry,
    Staking,
    DIP,
    USD2
)

from scripts.setup import new_bundle

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


def test_staking_happy_path(
    instance,
    instanceOperator: Account,
    investor: Account,
    riskpool,
    riskpoolKeeper: Account,
    instanceService,
    bundleRegistry: BundleRegistry,
    staking: Staking,
    registryOwner: Account,
    stakerWithDips: Account,
    staker2WithDips: Account,
    dip: DIP,
    usd2: USD2,
):
    print('--- test setup before any staking ---')
    instance_id = instanceService.getInstanceId()
    chain_id = instanceService.getChainId()
    riskpool_id = riskpool.getId()
    bundle_name = 'bundle-1'
    bundle_id = new_bundle(
        instance,
        instanceOperator,
        investor,
        riskpool,
        bundle_name)

    from_owner = {'from': registryOwner}

    staking.setDipContract(dip, from_owner)
    bundleRegistry.registerToken(riskpool.getErc20Token(), from_owner)

    exp = 1
    staking_rate_f = 0.1
    staking_rate_i = staking_rate_f * 10 ** exp
    staking_rate = staking.toRate(staking_rate_i, -exp)

    staking.setStakingRate(
        usd2.address,
        chain_id,
        staking_rate,
        from_owner)

    riskpool.setStakingAddress(staking, {'from': riskpoolKeeper})

    bundle = riskpool.getBundleInfo(bundle_id).dict()
    bundle_expiry_at = bundle['createdAt'] + bundle['lifetime']
    bundleRegistry.registerInstance(instance.getRegistry(), from_owner)
    bundleRegistry.registerComponent(instance_id, riskpool_id, from_owner)
    bundleRegistry.registerBundle(instance_id, riskpool_id, bundle_id, bundle_name, bundle_expiry_at, from_owner)

    print('--- everything ready before any staking is done ---')
    initial_dip_balance = 10**6 * 10**dip.decimals()
    dip.approve(staking.getStakingWallet(), initial_dip_balance, {'from':instanceOperator})
    tx = staking.increaseRewardReserves(initial_dip_balance, {'from':instanceOperator})

    type_bundle = 4
    (bundle_target_id, bt) = staking.toTarget(type_bundle, instance_id, riskpool_id, bundle_id, '')
    staking.register(bundle_target_id, bt)

    assert staking.stakes(bundle_target_id, stakerWithDips) == 0
    assert staking.stakes(bundle_target_id, staker2WithDips) == 0

    assert staking.stakes(bundle_target_id) == 0
    assert staking.getStakeBalance() == 0
    assert staking.getRewardBalance() == 0

    assert dip.balanceOf(staking.getStakingWallet()) == initial_dip_balance

    print('--- test setup after first staking ---')
    staking_amount = 10**5 * 10**dip.decimals()
    dip.approve(staking.getStakingWallet(), staking_amount, {'from': stakerWithDips})
    dip.approve(staking.getStakingWallet(), staking_amount, {'from': staker2WithDips})

    staking.stake(bundle_target_id, staking_amount, {'from': stakerWithDips})
    staking.stake(bundle_target_id, staking_amount, {'from': staker2WithDips})

    assert staking.stakes(bundle_target_id, stakerWithDips) == staking_amount
    assert staking.stakes(bundle_target_id, staker2WithDips) == staking_amount

    assert staking.stakes(bundle_target_id) == 2 * staking_amount
    assert staking.getStakeBalance() == 2 * staking_amount
    assert staking.getRewardBalance() == 0

    assert dip.balanceOf(staking.getStakingWallet()) == 2 * staking_amount + initial_dip_balance

    print('--- wait until mid staking period ---')
    time_until_expiry = bundle_expiry_at - chain.time()
    chain.sleep(int(time_until_expiry/2))
    chain.mine(1)

    print('--- test setup after increased staking ---')
    stake_info = staking.getInfo(bundle_target_id, stakerWithDips)
    reward_amount = staking.calculateRewardsIncrement(stake_info)
    increase_amount = 5 * 10**4 * 10**dip.decimals()
    dip.approve(staking.getStakingWallet(), increase_amount, {'from': stakerWithDips})

    staking.stake(bundle_target_id, increase_amount, {'from': stakerWithDips})

    assert staking.stakes(bundle_target_id, stakerWithDips) == staking_amount + increase_amount
    assert staking.stakes(bundle_target_id, staker2WithDips) == staking_amount

    total_stakes = 2 * staking_amount + increase_amount
    assert staking.stakes(bundle_target_id) == total_stakes

    assert staking.getStakeBalance() == total_stakes
    assert staking.getRewardBalance() == reward_amount

    assert dip.balanceOf(staking.getStakingWallet()) == 2 * staking_amount + increase_amount + initial_dip_balance

    print('--- test setup after withdrawal of some staking ---')
    chain.sleep(int(time_until_expiry/2) + 1) # wait until expiry
    chain.mine(1)

    withdrawal_amount = 7 * 10**4 * 10**dip.decimals()
    staking.unstake(bundle_target_id, withdrawal_amount, {'from': stakerWithDips})

    assert staking.stakes(bundle_target_id, stakerWithDips) == staking_amount + reward_amount + increase_amount - withdrawal_amount
    assert staking.stakes(bundle_target_id, staker2WithDips) == staking_amount

    total_stakes = 2 * staking_amount + increase_amount - withdrawal_amount
    assert staking.stakes(bundle_target_id) == total_stakes

    assert staking.getStakeBalance() == total_stakes
    assert staking.getRewardBalance() == reward_amount

    assert dip.balanceOf(staking.getStakingWallet()) == 2 * staking_amount + increase_amount - withdrawal_amount + initial_dip_balance

    print('--- test setup after withdrawal of remaining staking ---')
    chain.sleep(20)
    chain.mine(1)

    staking.unstakeAndClaimRewards(bundle_target_id, {'from': stakerWithDips})

    assert staking.stakes(bundle_target_id, stakerWithDips) == 0
    assert staking.stakes(bundle_target_id, staker2WithDips) == staking_amount

    assert staking.stakes(bundle_target_id) == staking_amount

    assert staking.getStakeBalance() == staking_amount
    assert staking.getRewardBalance() == 0

    assert dip.balanceOf(staking.getStakingWallet()) == initial_dip_balance + staking_amount - reward_amount
