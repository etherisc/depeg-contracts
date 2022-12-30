import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    chain,
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
    staking.registerToken(riskpool.getErc20Token(), from_owner)

    exp = 1
    staking_rate_f = 0.1
    staking_rate_i = staking_rate_f * 10 ** exp
    staking_rate = staking.toRate(staking_rate_i, -exp)

    staking.setStakingRate(
        usd2.address,
        chain_id,
        staking_rate,
        from_owner)

    riskpool.setStakingDataProvider(staking, {'from': riskpoolKeeper})

    bundle = riskpool.getBundleInfo(bundle_id).dict()
    bundle_expiry_at = bundle['createdAt'] + bundle['lifetime']
    staking.registerInstance(instance.getRegistry(), from_owner)
    staking.registerComponent(instance_id, riskpool_id, from_owner)
    staking.registerBundle(instance_id, riskpool_id, bundle_id, bundle_name, bundle_expiry_at, from_owner)

    print('--- everything ready before any staking is done ---')
    initial_dip_balance = 10**6 * 10**dip.decimals()
    dip.transfer(staking.getStakingWallet(), initial_dip_balance, {'from':instanceOperator})

    assert staking.getBundleStakes(instance_id, bundle_id, stakerWithDips) == 0
    assert staking.getBundleStakes(instance_id, bundle_id, staker2WithDips) == 0

    assert staking.getBundleStakes(instance_id, bundle_id) == 0
    assert staking.getTotalStakes(instance_id) == 0
    assert staking.getTotalStakes() == 0

    assert dip.balanceOf(staking.getStakingWallet()) == initial_dip_balance

    print('--- test setup after first staking ---')
    staking_amount = 10**5 * 10**dip.decimals()
    dip.approve(staking.getStakingWallet(), staking_amount, {'from': stakerWithDips})
    dip.approve(staking.getStakingWallet(), staking_amount, {'from': staker2WithDips})

    staking.stakeForBundle(instance_id, bundle_id, staking_amount, {'from': stakerWithDips})
    staking.stakeForBundle(instance_id, bundle_id, staking_amount, {'from': staker2WithDips})

    assert staking.getBundleStakes(instance_id, bundle_id, stakerWithDips) == staking_amount
    assert staking.getBundleStakes(instance_id, bundle_id, staker2WithDips) == staking_amount

    assert staking.getBundleStakes(instance_id, bundle_id) == 2 * staking_amount
    assert staking.getTotalStakes(instance_id) == 2 * staking_amount
    assert staking.getTotalStakes() == 2 * staking_amount

    assert dip.balanceOf(staking.getStakingWallet()) == 2 * staking_amount + initial_dip_balance

    print('--- wait one year ---')
    chain.sleep(staking.oneYear())
    chain.mine(1)

    print('--- test setup after increased staking ---')
    stake_info = staking.getBundleStakeInfo(instance_id, bundle_id, stakerWithDips)
    reward_amount = staking.calculateRewardsIncrement(stake_info)
    increase_amount = 5 * 10**4 * 10**dip.decimals()
    dip.approve(staking.getStakingWallet(), increase_amount, {'from': stakerWithDips})

    staking.stakeForBundle(instance_id, bundle_id, increase_amount, {'from': stakerWithDips})

    assert staking.getBundleStakes(instance_id, bundle_id, stakerWithDips) == staking_amount + reward_amount + increase_amount
    assert staking.getBundleStakes(instance_id, bundle_id, staker2WithDips) == staking_amount

    total_stakes = 2 * staking_amount + reward_amount + increase_amount
    assert staking.getBundleStakes(instance_id, bundle_id) == total_stakes
    assert staking.getTotalStakes(instance_id) == total_stakes
    assert staking.getTotalStakes() == total_stakes

    assert dip.balanceOf(staking.getStakingWallet()) == 2 * staking_amount + increase_amount + initial_dip_balance

    print('--- test setup after withdrawal of some staking ---')
    chain.sleep(1) # force updatedAt > createdAt
    withdrawal_amount = 7 * 10**4 * 10**dip.decimals()
    staking.unstakeFromBundle(instance_id, bundle_id, withdrawal_amount, {'from': stakerWithDips})

    assert staking.getBundleStakes(instance_id, bundle_id, stakerWithDips) == staking_amount + reward_amount + increase_amount - withdrawal_amount
    assert staking.getBundleStakes(instance_id, bundle_id, staker2WithDips) == staking_amount

    total_stakes = 2 * staking_amount + reward_amount + increase_amount - withdrawal_amount
    assert staking.getBundleStakes(instance_id, bundle_id) == total_stakes
    assert staking.getTotalStakes(instance_id) == total_stakes
    assert staking.getTotalStakes() == total_stakes

    assert dip.balanceOf(staking.getStakingWallet()) == 2 * staking_amount + increase_amount - withdrawal_amount + initial_dip_balance

    print('--- test setup after withdrawal of remaining staking ---')
    chain.sleep(1) # force updatedAt > createdAt
    staking.unstakeFromBundle(instance_id, bundle_id, {'from': stakerWithDips})

    assert staking.getBundleStakes(instance_id, bundle_id, stakerWithDips) == 0
    assert staking.getBundleStakes(instance_id, bundle_id, staker2WithDips) == staking_amount

    assert staking.getBundleStakes(instance_id, bundle_id) == staking_amount
    assert staking.getTotalStakes(instance_id) == staking_amount
    assert staking.getTotalStakes() == staking_amount

    assert dip.balanceOf(staking.getStakingWallet()) == initial_dip_balance + staking_amount - reward_amount
