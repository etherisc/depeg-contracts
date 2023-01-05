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

def test_staking_with_rewards(
    instance,
    instanceOperator: Account,
    investor: Account,
    riskpool,
    instanceService,
    bundleRegistry: BundleRegistry,
    staking: Staking,
    staker: Account,
    dip: DIP,
    usd2: USD2
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

    bundle = riskpool.getBundleInfo(bundle_id).dict()
    print('bundle {}'.format(bundle))

    # register token, instance, component and bundle
    bundle_expiry_at = bundle['createdAt'] + bundle['lifetime']
    bundleRegistry.registerToken(riskpool.getErc20Token())
    bundleRegistry.registerInstance(instance.getRegistry())
    bundleRegistry.registerComponent(instance_id, riskpool_id)
    bundleRegistry.registerBundle(instance_id, riskpool_id, bundle_id, bundle_name, bundle_expiry_at)

    reward_rate = staking.toRate(2, -1) # 20% apr for staking
    staking.setRewardRate(reward_rate)
    staking.setDipContract(dip)

    assert dip.balanceOf(staking.getStakingWallet()) == 0
    assert dip.balanceOf(staker) == 0

    initial_dip_balance = 10**6 * 10**dip.decimals()
    dip.transfer(staking.getStakingWallet(), initial_dip_balance, {'from':instanceOperator})
    dip.transfer(staker, initial_dip_balance, {'from':instanceOperator})

    assert dip.balanceOf(staking.getStakingWallet()) == initial_dip_balance
    assert dip.balanceOf(staker) == initial_dip_balance

    print('--- setup with initial staking ---')
    staking_amount = 50000 * 10**dip.decimals()
    dip.approve(staking.getStakingWallet(), staking_amount, {'from':staker})

    chain_time_before = chain.time()
    tx = staking.stakeForBundle(instance_id, bundle_id, staking_amount, {'from': staker})

    assert 'LogStakingStakedForBundle' in tx.events
    assert tx.events['LogStakingStakedForBundle']['user'] == staker
    assert tx.events['LogStakingStakedForBundle']['instanceId'] == instance_id
    assert tx.events['LogStakingStakedForBundle']['bundleId'] == bundle_id
    assert tx.events['LogStakingStakedForBundle']['amount'] == staking_amount
    assert tx.events['LogStakingStakedForBundle']['rewards'] == 0

    assert dip.balanceOf(staking) == initial_dip_balance + staking_amount
    assert dip.balanceOf(staker) == initial_dip_balance - staking_amount

    bundle_stake_info = staking.getBundleStakeInfo(instance_id, bundle_id, staker)
    info = bundle_stake_info.dict()
    print('info {}'.format(info))

    assert info['user'] == staker
    assert info['key'][0] == instance_id
    assert info['key'][1] == bundle_id
    assert info['balance'] == staking_amount
    assert info['createdAt'] > 0
    assert info['updatedAt'] == info['createdAt']

    assert staking.calculateRewardsIncrement(bundle_stake_info) == 0

    print('--- wait approx 2 months ---')
    sleep_duration = 60 * 24 * 3600
    chain.sleep(sleep_duration)
    chain.mine(1)

    print('--- increase stake by 1 ---')
    staking_increment = 1
    dip.approve(staking.getStakingWallet(), staking_increment, {'from':staker})

    chain_time_after = chain.time()
    rr = staking.fromRate(reward_rate).dict()
    tx2 = staking.stakeForBundle(instance_id, bundle_id, staking_increment, {'from': staker})

    rewards_increment = staking.calculateRewardsIncrement(bundle_stake_info)
    duration_factor = (chain_time_after - chain_time_before) / staking.oneYear()
    rewards_increment_expected = staking_amount * duration_factor * rr['value']/rr['divisor']

    # sensitivity: < 1 / 1'000'000
    assert (rewards_increment - rewards_increment_expected)/rewards_increment_expected <= 10**-6
    assert dip.balanceOf(staking) == initial_dip_balance + staking_amount + staking_increment
    assert dip.balanceOf(staker) == initial_dip_balance - staking_amount - staking_increment

    assert 'LogStakingStakedForBundle' in tx2.events
    assert tx2.events['LogStakingStakedForBundle']['amount'] == staking_increment
    assert tx2.events['LogStakingStakedForBundle']['rewards'] == rewards_increment

    bundle_stake_info2 = staking.getBundleStakeInfo(instance_id, bundle_id, staker).dict()
    print('bundle_stake_info2 {}'.format(bundle_stake_info2))

    assert bundle_stake_info2['balance'] == staking_amount + rewards_increment + staking_increment
    assert bundle_stake_info2['updatedAt'] >= bundle_stake_info.dict()['updatedAt'] + sleep_duration

    print('--- partial stake withdrawal ---')
    sleep_a_little_more_duration = 7 * 24 * 3600
    chain.sleep(sleep_a_little_more_duration)
    chain.mine(1)

    chain_time_unstake1 = chain.time()
    chain_time_delta = chain_time_unstake1 - chain_time_after
    withdrawal_amount = 10000 * 10**dip.decimals() + rewards_increment + 1

    bsi = staking.getBundleStakeInfo(instance_id, bundle_id, staker)
    tx3 = staking.unstakeFromBundle(instance_id, bundle_id, withdrawal_amount, {'from': staker})
    ri_unstake = staking.calculateRewardsIncrement(bsi)

    assert 'LogStakingUnstakedFromBundle' in tx3.events
    assert tx3.events['LogStakingUnstakedFromBundle']['user'] == staker
    assert tx3.events['LogStakingUnstakedFromBundle']['instanceId'] == instance_id
    assert tx3.events['LogStakingUnstakedFromBundle']['bundleId'] == bundle_id
    assert tx3.events['LogStakingUnstakedFromBundle']['amount'] == withdrawal_amount
    assert tx3.events['LogStakingUnstakedFromBundle']['rewards'] == ri_unstake
    assert tx3.events['LogStakingUnstakedFromBundle']['all'] is False

    assert dip.balanceOf(staking) == initial_dip_balance + staking_amount + staking_increment - withdrawal_amount
    assert dip.balanceOf(staker) == initial_dip_balance - staking_amount - staking_increment + withdrawal_amount

    bundle_stake_info3 = staking.getBundleStakeInfo(instance_id, bundle_id, staker)
    print('bundle_stake_info3 {}'.format(bundle_stake_info3.dict()))

    expected_balance = 40000 * 10**dip.decimals() + ri_unstake
    assert bundle_stake_info3.dict()['balance'] == expected_balance

    print('--- remaining stake withdrawal ---')
    tx4 = staking.unstakeFromBundle(instance_id, bundle_id, {'from': staker})
    ri_final = staking.calculateRewardsIncrement(bundle_stake_info3)

    assert 'LogStakingUnstakedFromBundle' in tx4.events
    assert tx4.events['LogStakingUnstakedFromBundle']['user'] == staker
    assert tx4.events['LogStakingUnstakedFromBundle']['instanceId'] == instance_id
    assert tx4.events['LogStakingUnstakedFromBundle']['bundleId'] == bundle_id
    assert tx4.events['LogStakingUnstakedFromBundle']['amount'] == expected_balance + ri_final
    assert tx4.events['LogStakingUnstakedFromBundle']['rewards'] == ri_final
    assert tx4.events['LogStakingUnstakedFromBundle']['all'] is True

    assert dip.balanceOf(staker) == initial_dip_balance + rewards_increment + ri_unstake + ri_final

    bundle_stake_info4 = staking.getBundleStakeInfo(instance_id, bundle_id, staker).dict()
    print('bundle_stake_info4 {}'.format(bundle_stake_info4))

    expected_balance = 0
    assert bundle_stake_info4['balance'] == expected_balance
