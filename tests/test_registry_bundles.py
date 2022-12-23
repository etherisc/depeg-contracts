import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    chain,
    web3,
    interface,
    BundleRegistry,
    DepegRiskpool,
    USD2
)

from scripts.setup import create_bundle
from scripts.util import contract_from_address

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass

DUMMY_INSTANCE_ID = '0x1cd783510e740524e4a1e0070b8c8cd37220ceaf1166960dd1fc0b7858c1de64'
DUMMY_REGISTRY = '0x55F8a0123Fe17710FB0c3393eB916fb8176d87b9'
DUMMY_CHAIN_ID = 1

USD2_DECIMALS = 6
FUNDING = 10000 * 10**USD2_DECIMALS
BUNDLE_LIFETIME_DAYS = 60
MAX_SUM_INSURED = FUNDING
MAX_DURATION_DAYS = BUNDLE_LIFETIME_DAYS
ARP_PERCENTAGE = 3.1415


def test_register_happy_path(
    instance,
    instanceOperator,
    instanceService: interface.IInstanceService,
    riskpool: DepegRiskpool,
    investor: Account,
    bundleRegistry: BundleRegistry,
    registryOwner: Account,
    theOutsider: Account,
    usd1,
    usd2: USD2,
    dip
):
    instance_id = instanceService.getInstanceId()
    riskpool_id = riskpool.getId()
    chain_id = web3.chain_id
    registry = instance.getRegistry()
    from_owner = {'from':registryOwner}
    from_outsider = {'from':theOutsider}

    # create bundle
    bundle_name = 'bundle-1'
    bundle_id = new_bundle(
        instance,
        instanceOperator,
        investor,
        riskpool,
        bundle_name)

    bundle = riskpool.getBundleInfo(bundle_id).dict()
    print('bundle {}'.format(bundle))

    # start with registered instance and riskpool
    bundleRegistry.registerInstance(registry, from_owner)
    bundleRegistry.registerComponent(instance_id, riskpool_id, from_owner)

    # register some tokens
    bundleRegistry.registerToken(usd1, from_owner)
    bundleRegistry.registerToken(usd2, from_owner)
    bundleRegistry.registerToken(dip, from_owner)

    assert bundleRegistry.instances() == 1
    assert bundleRegistry.components(instance_id) == 1
    assert bundleRegistry.bundles(instance_id, riskpool_id) == 0
    assert bundleRegistry.isRegisteredBundle(instance_id, bundle_id) == False

    # register bundle
    expiry_at = bundle['createdAt'] + bundle['lifetime']
    tx = bundleRegistry.registerBundle(
        instance_id, 
        riskpool_id, 
        bundle_id,
        bundle_name,
        expiry_at,
        from_outsider)

    assert 'LogInstanceRegistryBundleRegistered' in tx.events
    assert tx.events['LogInstanceRegistryBundleRegistered']['instanceId'] == instance_id
    assert tx.events['LogInstanceRegistryBundleRegistered']['riskpoolId'] == riskpool_id
    assert tx.events['LogInstanceRegistryBundleRegistered']['bundleId'] == bundle_id

    assert bundleRegistry.bundles(instance_id, riskpool_id) == 1
    assert bundleRegistry.getBundleId(instance_id, riskpool_id, 0) == bundle_id
    assert bundleRegistry.isRegisteredBundle(instance_id, bundle_id) == True
    assert bundleRegistry.isRegisteredBundle(instance_id, bundle_id + 1) == False

    token_info = bundleRegistry.getBundleTokenInfo(instance_id, bundle_id).dict()
    print('token_info {}'.format(token_info))

    assert token_info['key'][0] == usd2
    assert token_info['symbol'] == usd2.symbol()
    assert token_info['decimals'] == usd2.decimals()

    tokenAddress = bundleRegistry.getBundleToken(instance_id, bundle_id)
    token = contract_from_address(interface.IERC20Metadata, tokenAddress)
    print('token {}'.format(token))

    assert token.address == usd2.address
    assert token.name() == usd2.name()
    assert token.symbol() == usd2.symbol()
    assert token.decimals() == usd2.decimals()

    bundle_info = bundleRegistry.getBundleInfo(instance_id, bundle_id).dict()
    print('bundle_info {}'.format(bundle_info))

    active_state = 0
    assert bundle_info['key'][0] == instance_id
    assert bundle_info['key'][1] == bundle_id
    assert bundle_info['riskpoolId'] == riskpool_id
    assert bundle_info['token'] == usd2
    assert bundle_info['state'] == active_state
    assert bundle_info['name'] == bundle_name
    assert bundle_info['expiryAt'] == expiry_at
    assert bundle_info['closedAt'] == 0
    assert bundle_info['createdAt'] > 0
    assert bundle_info['updatedAt'] == bundle_info['createdAt']

    sleep_days(14)

    # create 2nd bundle
    bundle_name2 = 'bundle-2'
    bundle_id2 = new_bundle(
        instance,
        instanceOperator,
        investor,
        riskpool,
        bundle_name2)

    bundle2 = riskpool.getBundleInfo(bundle_id2).dict()

    # register 2nd bundle
    expiry_at2 = bundle2['createdAt'] + bundle2['lifetime']
    tx = bundleRegistry.registerBundle(
        instance_id, 
        riskpool_id, 
        bundle_id2,
        bundle_name2,
        expiry_at2,
        from_outsider)

    assert bundle_id2 == bundle_id + 1
    assert bundleRegistry.bundles(instance_id, riskpool_id) == 2

    assert bundleRegistry.getBundleId(instance_id, riskpool_id, 0) == bundle_id
    assert bundleRegistry.getBundleId(instance_id, riskpool_id, 1) == bundle_id2

    assert bundleRegistry.isRegisteredBundle(instance_id, bundle_id) == True
    assert bundleRegistry.isRegisteredBundle(instance_id, bundle_id + 1) == True

    assert bundleRegistry.getBundleToken(instance_id, bundle_id) == bundleRegistry.getBundleToken(instance_id, bundle_id2)

    bundle_info2 = bundleRegistry.getBundleInfo(instance_id, bundle_id2).dict()
    print('bundle_info2 {}'.format(bundle_info2))

    fourteen_days = 14 * 24 * 3600
    assert bundle_info2['key'][0] == instance_id
    assert bundle_info2['key'][1] == bundle_id2
    assert bundle_info2['riskpoolId'] == riskpool_id
    assert bundle_info2['token'] == usd2
    assert bundle_info2['state'] == active_state
    assert bundle_info2['name'] == bundle_name2
    assert bundle_info2['expiryAt'] == expiry_at2
    assert bundle_info2['closedAt'] == 0
    assert bundle_info2['createdAt'] >= bundle_info['createdAt'] + fourteen_days
    assert bundle_info2['updatedAt'] == bundle_info2['createdAt']


def test_register_failure_modes(
    instance,
    instanceService: interface.IInstanceService,
    riskpool: DepegRiskpool,
    bundleRegistry: BundleRegistry,
    registryOwner: Account,
    theOutsider: Account,
):
    instance_id = instanceService.getInstanceId()
    riskpool_id = riskpool.getId()
    state_active = 3
    state_suspended = 5

    chain_id = web3.chain_id
    registry = instance.getRegistry()
    from_owner = {'from':registryOwner}

    # start with registered instance
    bundleRegistry.registerInstance(registry, from_owner)

    # register riskpool
    bundleRegistry.registerComponent(instance_id, riskpool_id, from_owner)

    # register instance on different chain
    bundleRegistry.registerInstance(
        DUMMY_INSTANCE_ID,
        DUMMY_CHAIN_ID,
        DUMMY_REGISTRY
    )


def test_update_happy_path(
    instance,
    instanceService: interface.IInstanceService,
    instanceOperator: Account,
    riskpool: DepegRiskpool,
    investor: Account,
    bundleRegistry: BundleRegistry,
    registryOwner: Account,
    theOutsider: Account,
):
    instance_id = instanceService.getInstanceId()
    riskpool_id = riskpool.getId()
    chain_id = web3.chain_id
    registry = instance.getRegistry()
    from_owner = {'from':registryOwner}
    from_outsider = {'from':theOutsider}

    # create bundle
    bundle_name = 'bundle-1'
    bundle_id = new_bundle(
        instance,
        instanceOperator,
        investor,
        riskpool,
        bundle_name)

    bundle = riskpool.getBundleInfo(bundle_id).dict()
    print('bundle {}'.format(bundle))

    # register instance and riskpool
    bundleRegistry.registerInstance(registry, from_owner)
    bundleRegistry.registerComponent(instance_id, riskpool_id, from_owner)

    # register bundle
    expiry_at = bundle['createdAt'] + bundle['lifetime']
    bundleRegistry.registerBundle(
        instance_id, 
        riskpool_id, 
        bundle_id,
        bundle_name,
        expiry_at,
        from_outsider)

    sleep_days(14)

    state_active = 0
    state_locked = 1
    bundle = instanceService.getBundle(bundle_id).dict()
    assert bundle['state'] == state_active

    # lock bundle
    riskpool.lockBundle(bundle_id, {'from': investor})

    bundle = instanceService.getBundle(bundle_id).dict()
    assert bundle['state'] == state_locked

    # update bundle data
    tx = bundleRegistry.updateBundle(instance_id, bundle_id)

    assert 'LogInstanceRegistryBundleUpdated' in tx.events
    assert tx.events['LogInstanceRegistryBundleUpdated']['instanceId'] == instance_id
    assert tx.events['LogInstanceRegistryBundleUpdated']['bundleId'] == bundle_id
    assert tx.events['LogInstanceRegistryBundleUpdated']['oldState'] == state_active
    assert tx.events['LogInstanceRegistryBundleUpdated']['newState'] == state_locked

    assert bundleRegistry.bundles(instance_id, riskpool_id) == 1
    assert bundleRegistry.getBundleId(instance_id, riskpool_id, 0) == bundle_id
    assert bundleRegistry.isRegisteredBundle(instance_id, bundle_id) == True

    bundle_info = bundleRegistry.getBundleInfo(instance_id, bundle_id).dict()
    print('bundle_info {}'.format(bundle_info))

    active_state = 0
    assert bundle_info['key'][0] == instance_id
    assert bundle_info['key'][1] == bundle_id
    assert bundle_info['state'] == state_locked
    assert bundle_info['updatedAt'] > bundle_info['createdAt']


def sleep_days(days):
    chain.sleep(days * 24 * 3600)
    chain.mine(1)


def test_update_failure_modes(
    instance,
    instanceService: interface.IInstanceService,
    riskpool: DepegRiskpool,
    bundleRegistry: BundleRegistry,
    registryOwner: Account,
    theOutsider: Account,
):
    instance_id = instanceService.getInstanceId()
    riskpool_id = riskpool.getId()
    state_active = 3
    state_suspended = 5

    chain_id = web3.chain_id
    registry = instance.getRegistry()
    from_owner = {'from':registryOwner}

    # start with registered instance
    bundleRegistry.registerInstance(registry, from_owner)

    # register riskpool
    bundleRegistry.registerComponent(instance_id, riskpool_id, from_owner)

    # register instance on different chain
    bundleRegistry.registerInstance(
        DUMMY_INSTANCE_ID,
        DUMMY_CHAIN_ID,
        DUMMY_REGISTRY
    )


def new_bundle(
    instance,
    instanceOperator,
    investor,
    riskpool,
    bundleName
):
    return create_bundle(
        instance,
        instanceOperator,
        investor,
        riskpool,
        FUNDING,
        bundleName,
        BUNDLE_LIFETIME_DAYS,
        1,
        MAX_SUM_INSURED,
        1,
        MAX_DURATION_DAYS,
        ARP_PERCENTAGE)
