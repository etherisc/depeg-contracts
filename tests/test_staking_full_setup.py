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

from scripts.setup import (
    FUNDING,
    new_bundle,
    apply_for_policy
)

from scripts.deploy_depeg import best_premium


# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


def test_staking_full_setup(
    instance,
    instanceOperator: Account,
    product,
    customer: Account,
    investor: Account,
    riskpool,
    riskpoolKeeper: Account,
    instanceService,
    bundleRegistry: BundleRegistry,
    staking: Staking,
    registryOwner: Account,
    stakerWithDips: Account,
    usd2: USD2,
    dip: DIP,
):
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

    bundleRegistry.registerToken(riskpool.getErc20Token(), from_owner)
    staking.setDipContract(dip, from_owner)

    print('--- setup staking rate ---')
    exp = 1
    staking_rate_f = 0.1
    staking_rate_i = staking_rate_f * 10 ** exp
    staking_rate = staking.toRate(staking_rate_i, -exp)
    
    staking.setStakingRate(
        usd2.address,
        chain_id,
        staking_rate,
        from_owner)

    print('--- link staking to gif instance/riskpool/bundle ---')
    bundle = riskpool.getBundleInfo(bundle_id).dict()
    bundle_expiry_at = bundle['createdAt'] + bundle['lifetime']
    bundleRegistry.registerInstance(instance.getRegistry(), from_owner)
    bundleRegistry.registerComponent(instance_id, riskpool_id, from_owner)
    bundleRegistry.registerBundle(instance_id, riskpool_id, bundle_id, bundle_name, bundle_expiry_at, from_owner)

    assert bundle['bundleId'] == bundle_id
    assert bundle['capitalSupportedByStaking'] == riskpool.getBundleCapitalCap()
    assert bundle['capital'] > 0.9 * FUNDING
    assert bundle['lockedCapital'] == 0

    print('--- link riskpool to staking contract ---')
    riskpool.setStakingDataProvider(staking, {'from': riskpoolKeeper})

    print('--- attempt to buy a policy with insufficient staking ---')
    bundle = riskpool.getBundleInfo(bundle_id).dict()
    print('bundle {}'.format(bundle))

    assert bundle['bundleId'] == bundle_id
    assert bundle['capitalSupportedByStaking'] == 0
    assert bundle['capital'] > 0.9 * FUNDING
    assert bundle['lockedCapital'] == 0

    assert staking.getBundleStakes(instance_id, bundle_id) == 0
    assert staking.getBundleCapitalSupport(instance_id, bundle_id) == 0

    # case: insufficient staking
    # attempt to buy a policy where the sum insured cannot be covered by riskpool
    sum_insured = 4000 * 10**usd2.decimals()
    duration_days = 60
    premium_info = best_premium(instanceService, riskpool, product, sum_insured, duration_days)
    print('premium_info {}'.format(premium_info))

    # ensure there is a bundle that matches with the application
    assert premium_info['comment'] == 'recommended bundle'

    # check that capital support is 0 (as nothing has yet been staked to the bundle)
    assert staking.getBundleCapitalSupport(instance_id, bundle_id) == 0
    assert sum_insured > staking.getBundleCapitalSupport(instance_id, bundle_id)

    process_id1 = apply_for_policy(
        instance,
        instanceOperator,
        product,
        customer,
        sum_insured,
        duration_days,
        premium_info['premium'])

    metadata = instanceService.getMetadata(process_id1)
    application = instanceService.getApplication(process_id1)

    policy = instanceService.getPolicy(process_id1).dict()

    print('process_id1 {}'.format(process_id1))
    print('metadata {}'.format(metadata))
    print('application {}'.format(application))
    print('policy {}'.format(policy))

    print('--- add bundle stakes and retry to buy a policy---')
    target_usd2_support = 3 * sum_insured
    required_staking_amount = staking.calculateRequiredStaking(usd2, chain_id, target_usd2_support)
    staking_amount = 100000 * 10**dip.decimals()
    dip.approve(staking.getStakingWallet(), required_staking_amount, {'from': stakerWithDips})
    staking.stakeForBundle(instance_id, bundle_id, required_staking_amount, {'from': stakerWithDips})

    # check conditions to allow for underwriting
    assert staking.getBundleStakes(instance_id, bundle_id) == required_staking_amount
    assert staking.getBundleCapitalSupport(instance_id, bundle_id) == target_usd2_support
    assert sum_insured <= bundle['capital'] - bundle['lockedCapital']

    process_id2 = apply_for_policy(
        instance,
        instanceOperator,
        product,
        customer,
        sum_insured,
        duration_days,
        premium_info['premium'])

    metadata = instanceService.getMetadata(process_id2)
    application = instanceService.getApplication(process_id2)
    policy = instanceService.getPolicy(process_id2)

    print('process_id2 {}'.format(process_id2))
    print('metadata2 {}'.format(metadata))
    print('application2 {}'.format(application))
    print('policy2 {}'.format(policy))

    # check updated bundleInfo
    bundle2 = riskpool.getBundleInfo(bundle_id)
    print('bundle2 {}'.format(bundle2))

    assert bundle2['bundleId'] == bundle_id
    assert bundle2['capitalSupportedByStaking'] == staking.getBundleCapitalSupport(instance_id, bundle_id)
    assert bundle2['capital'] == bundle['capital']
    assert bundle2['lockedCapital'] == 2 * sum_insured
