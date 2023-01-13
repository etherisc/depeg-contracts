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
    dip.transfer(staker, initial_dip_balance, {'from':instanceOperator})

    dip.approve(staking.getStakingWallet(), initial_dip_balance, {'from':instanceOperator})
    tx = staking.increaseRewardReserves(initial_dip_balance, {'from':instanceOperator})

    assert 'LogStakingRewardReservesIncreased' in tx.events
    assert tx.events['LogStakingRewardReservesIncreased']['user'] == instanceOperator
    assert tx.events['LogStakingRewardReservesIncreased']['amount'] == initial_dip_balance
    assert tx.events['LogStakingRewardReservesIncreased']['newBalance'] == initial_dip_balance

    assert 'LogStakingDipBalanceChanged' in tx.events
    assert tx.events['LogStakingDipBalanceChanged']['stakeBalance'] == 0 
    assert tx.events['LogStakingDipBalanceChanged']['rewardBalance'] == 0 
    assert tx.events['LogStakingDipBalanceChanged']['actualBalance'] == initial_dip_balance
    assert tx.events['LogStakingDipBalanceChanged']['reserves'] == initial_dip_balance

    assert dip.balanceOf(staking.getStakingWallet()) == initial_dip_balance
    assert dip.balanceOf(staker) == initial_dip_balance

    print('--- setup with initial staking ---')
    type_bundle = 4
    (bundle_target_id, bt) = staking.toTarget(type_bundle, instance_id, riskpool_id, bundle_id, '')
    staking.register(bundle_target_id, bt)

    staking_amount = 50000 * 10**dip.decimals()
    dip.approve(staking.getStakingWallet(), staking_amount, {'from':staker})

    chain_time_before = chain.time()
    tx = staking.stake(bundle_target_id, staking_amount, {'from': staker})

    assert 'LogStakingStaked' in tx.events
    assert tx.events['LogStakingStaked']['user'] == staker
    assert tx.events['LogStakingStaked']['targetId'] == bundle_target_id
    assert tx.events['LogStakingStaked']['instanceId'] == instance_id
    assert tx.events['LogStakingStaked']['bundleId'] == bundle_id
    assert tx.events['LogStakingStaked']['amount'] == staking_amount
    assert tx.events['LogStakingStaked']['newBalance'] == staking_amount

    assert 'LogStakingDipBalanceChanged' in tx.events
    assert tx.events['LogStakingDipBalanceChanged']['stakeBalance'] == staking_amount
    assert tx.events['LogStakingDipBalanceChanged']['rewardBalance'] == 0
    assert tx.events['LogStakingDipBalanceChanged']['actualBalance'] == initial_dip_balance + staking_amount
    assert tx.events['LogStakingDipBalanceChanged']['reserves'] == initial_dip_balance

    assert dip.balanceOf(staking) == initial_dip_balance + staking_amount
    assert dip.balanceOf(staker) == initial_dip_balance - staking_amount

    bundle_stake_info = staking.getInfo(bundle_target_id, staker)
    info = bundle_stake_info.dict()
    print('info {}'.format(info))

    assert info['user'] == staker
    assert info['targetId'] == bundle_target_id
    assert info['stakeBalance'] == staking_amount
    assert info['rewardBalance'] == 0
    assert info['createdAt'] > 0
    assert info['updatedAt'] == info['createdAt']

    assert staking.calculateRewardsIncrement(bundle_stake_info) == 0

    print('--- wait for half of bundle lifetime  ---')
    time_until_bundle_expiry = bundle_expiry_at - chain.time()
    sleep_duration = int(time_until_bundle_expiry/2)
    chain.sleep(sleep_duration)
    chain.mine(1)

    print('--- increase stake by 1 ---')
    staking_increment = 1
    dip.approve(staking.getStakingWallet(), staking_increment, {'from':staker})

    chain_time_after = chain.time()
    rr = staking.fromRate(reward_rate).dict()
    tx2 = staking.stake(bundle_target_id, staking_increment, {'from': staker})

    rewards_increment = staking.calculateRewardsIncrement(bundle_stake_info)
    duration_factor = (chain_time_after - chain_time_before) / staking.oneYear()
    rewards_increment_expected = staking_amount * duration_factor * rr['value']/rr['divisor']

    assert 'LogStakingDipBalanceChanged' in tx.events
    assert tx.events['LogStakingDipBalanceChanged']['stakeBalance'] == staking_amount
    assert tx.events['LogStakingDipBalanceChanged']['rewardBalance'] == 0
    assert tx.events['LogStakingDipBalanceChanged']['actualBalance'] == initial_dip_balance + staking_amount
    assert tx.events['LogStakingDipBalanceChanged']['reserves'] == initial_dip_balance

    # sensitivity: < 1 / 1'000'000
    assert (rewards_increment - rewards_increment_expected)/rewards_increment_expected <= 10**-6
    assert dip.balanceOf(staking) == initial_dip_balance + staking_amount + staking_increment
    assert dip.balanceOf(staker) == initial_dip_balance - staking_amount - staking_increment

    assert 'LogStakingStaked' in tx2.events
    assert tx2.events['LogStakingStaked']['amount'] == staking_increment
    assert tx2.events['LogStakingStaked']['newBalance'] == staking_amount + staking_increment

    bundle_stake_info2 = staking.getInfo(bundle_target_id, staker).dict()
    print('bundle_stake_info2 {}'.format(bundle_stake_info2))

    assert bundle_stake_info2['stakeBalance'] == staking_amount + staking_increment
    assert bundle_stake_info2['rewardBalance'] == rewards_increment
    assert bundle_stake_info2['updatedAt'] >= bundle_stake_info.dict()['updatedAt'] + sleep_duration

    print('--- wait until expiry time is over ---')
    chain.sleep(sleep_duration + 1)
    chain.mine(1)

    withdrawal_amount = 10000 * 10**dip.decimals() + rewards_increment + 1
    bsi = staking.getInfo(bundle_target_id, staker)
    tx3 = staking.unstake(bundle_target_id, withdrawal_amount, {'from': staker})
    ri_unstake = staking.calculateRewardsIncrement(bsi)

    assert 'LogStakingUnstaked' in tx3.events
    assert tx3.events['LogStakingUnstaked']['user'] == staker
    assert tx3.events['LogStakingUnstaked']['targetId'] == bundle_target_id
    assert tx3.events['LogStakingUnstaked']['instanceId'] == instance_id
    assert tx3.events['LogStakingUnstaked']['componentId'] == riskpool_id
    assert tx3.events['LogStakingUnstaked']['bundleId'] == bundle_id
    assert tx3.events['LogStakingUnstaked']['amount'] == withdrawal_amount
    assert tx3.events['LogStakingUnstaked']['newBalance'] == staking_amount + staking_increment - withdrawal_amount

    assert 'LogStakingRewardsUpdated' in tx3.events
    assert tx3.events['LogStakingRewardsUpdated']['user'] == staker
    assert tx3.events['LogStakingRewardsUpdated']['targetId'] == bundle_target_id
    assert tx3.events['LogStakingRewardsUpdated']['instanceId'] == instance_id
    assert tx3.events['LogStakingRewardsUpdated']['componentId'] == riskpool_id
    assert tx3.events['LogStakingRewardsUpdated']['bundleId'] == bundle_id
    assert tx3.events['LogStakingRewardsUpdated']['amount'] == ri_unstake

    expected_reward_balance = rewards_increment_expected + ri_unstake
    actual_reward_balance = tx3.events['LogStakingRewardsUpdated']['newBalance']
    assert abs(expected_reward_balance - actual_reward_balance)/expected_reward_balance < 10**-6

    assert dip.balanceOf(staking) == initial_dip_balance + staking_amount + staking_increment - withdrawal_amount
    assert dip.balanceOf(staker) == initial_dip_balance - staking_amount - staking_increment + withdrawal_amount

    bundle_stake_info3 = staking.getInfo(bundle_target_id, staker)
    print('bundle_stake_info3 {}'.format(bundle_stake_info3.dict()))

    expected_balance = 40000 * 10**dip.decimals() + ri_unstake
    bsi3 = bundle_stake_info3.dict()
    assert bsi3['stakeBalance'] + bsi3['rewardBalance'] == expected_balance

    print('--- remaining stake withdrawal ---')
    tx4 = staking.unstakeAndClaimRewards(bundle_target_id, {'from': staker})
    ri_final = staking.calculateRewardsIncrement(bundle_stake_info3)

    assert 'LogStakingUnstaked' in tx4.events
    assert tx4.events['LogStakingUnstaked']['user'] == staker
    assert tx4.events['LogStakingUnstaked']['targetId'] == bundle_target_id
    assert tx4.events['LogStakingUnstaked']['instanceId'] == instance_id
    assert tx4.events['LogStakingUnstaked']['componentId'] == riskpool_id
    assert tx4.events['LogStakingUnstaked']['bundleId'] == bundle_id
    assert tx4.events['LogStakingUnstaked']['amount'] == bsi3['stakeBalance']
    assert tx4.events['LogStakingUnstaked']['newBalance'] == 0

    assert 'LogStakingRewardsClaimed' in tx4.events
    assert tx4.events['LogStakingRewardsClaimed']['user'] == staker
    assert tx4.events['LogStakingRewardsClaimed']['targetId'] == bundle_target_id
    assert tx4.events['LogStakingRewardsClaimed']['instanceId'] == instance_id
    assert tx4.events['LogStakingRewardsClaimed']['componentId'] == riskpool_id
    assert tx4.events['LogStakingRewardsClaimed']['bundleId'] == bundle_id
    assert tx4.events['LogStakingRewardsClaimed']['amount'] == bsi3['rewardBalance'] + ri_final
    assert tx4.events['LogStakingRewardsClaimed']['newBalance'] == 0

    assert dip.balanceOf(staker) == initial_dip_balance + rewards_increment + ri_unstake + ri_final

    bundle_stake_info4 = staking.getInfo(bundle_target_id, staker).dict()
    print('bundle_stake_info4 {}'.format(bundle_stake_info4))

    expected_balance = 0
    assert bundle_stake_info4['stakeBalance'] == expected_balance
    assert bundle_stake_info4['rewardBalance'] == expected_balance



def test_staking_rewards_corner_case(
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

    staking.setDipContract(dip)

    print('--- start with reward rate 0 ---')
    reward_rate_zero = staking.toRate(0, 0) # 20% apr for staking
    staking.setRewardRate(reward_rate_zero)

    print('--- setup with initial staking ---')
    type_bundle = 4
    (bundle_target_id, bt) = staking.toTarget(type_bundle, instance_id, riskpool_id, bundle_id, '')
    staking.register(bundle_target_id, bt)

    initial_dip_balance = 10**6 * 10**dip.decimals()
    dip.transfer(staker, initial_dip_balance, {'from':instanceOperator})

    staking_amount = 10**4 * 10**dip.decimals()
    dip.approve(staking.getStakingWallet(), 4 * staking_amount, {'from':staker})

    print('--- stake 1st time (rate == 0) ---')
    tx0 = staking.stake(bundle_target_id, staking_amount, {'from': staker})

    # wait some days
    chain.sleep(14 * 24 * 3600)
    chain.mine(1)

    print('--- update reward rate to non-zero ---')
    reward_rate_4_2 = staking.toRate(42, -3) # 20% apr for staking
    staking.setRewardRate(reward_rate_4_2)

    print('--- stake 2nd time (rate > 0) ---')
    tx1 = staking.stake(bundle_target_id, staking_amount, {'from': staker})

    # wait some more days
    chain.sleep(14 * 24 * 3600)
    chain.mine(1)

    print('--- stake 3rd time (rate > 0) ---')
    tx2 = staking.stake(bundle_target_id, staking_amount, {'from': staker})

    assert 'LogStakingDipBalanceChanged' in tx1.events
    assert tx2.events['LogStakingDipBalanceChanged']['reserves'] < 0
    assert tx2.events['LogStakingDipBalanceChanged']['reserves'] == staking.getReserveBalance()
