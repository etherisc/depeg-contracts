import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    chain,
    web3,
    BundleRegistry,
    Staking,
    USD2,
    DIP,
)

from scripts.setup import new_bundle

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


def test_targets_happy_path(
    instance,
    instanceOperator,
    investor: Account,
    riskpool,
    instanceService,
    bundleRegistry: BundleRegistry,
    staking: Staking,
    stakerWithDips: Account,
    usd2: USD2,
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

    bundle = riskpool.getBundleInfo(bundle_id).dict()
    print('bundle {}'.format(bundle))

    # get target ids for instance, component and bundle
    instance_target_id = staking.toInstanceTargetId(instance_id)
    component_target_id = staking.toComponentTargetId(instance_id, riskpool_id)
    bundle_target_id = staking.toBundleTargetId(instance_id, riskpool_id, bundle_id)

    # target types
    type_instance = 2
    type_component = 3
    type_bundle = 4

    # get targets
    (iid, instance_target) = staking.toTarget(
        type_instance, instance_id, 0, 0, '')

    (cid, component_target) = staking.toTarget(
        type_component, instance_id, riskpool_id, 0, '')

    (bid, bundle_target) = staking.toTarget(
        type_bundle, instance_id, riskpool_id, bundle_id, '')

    assert iid == instance_target_id
    assert cid == component_target_id
    assert bid == bundle_target_id

    assert staking.isTargetRegistered(instance_target) is False
    assert staking.isTargetRegistered(component_target) is False
    assert staking.isTargetRegistered(bundle_target) is False

    assert staking.isTarget(instance_target_id) is False
    assert staking.isTarget(component_target_id) is False
    assert staking.isTarget(bundle_target_id) is False

    assert staking.targets() == 0

    # register instance
    bundle_expiry_at = bundle['createdAt'] + bundle['lifetime']
    bundleRegistry.registerInstance(instance.getRegistry())

    assert staking.isTargetRegistered(instance_target) is True
    assert staking.isTargetRegistered(component_target) is False
    assert staking.isTargetRegistered(bundle_target) is False

    assert staking.isTarget(instance_target_id) is False
    assert staking.isTarget(component_target_id) is False
    assert staking.isTarget(bundle_target_id) is False

    assert staking.targets() == 0

    # register component
    bundleRegistry.registerComponent(instance_id, riskpool_id)

    assert staking.isTargetRegistered(instance_target) is True
    assert staking.isTargetRegistered(component_target) is True
    assert staking.isTargetRegistered(bundle_target) is False

    assert staking.isTarget(instance_target_id) is False
    assert staking.isTarget(component_target_id) is False
    assert staking.isTarget(bundle_target_id) is False

    # register bundle
    bundleRegistry.registerBundle(instance_id, riskpool_id, bundle_id, bundle_name, bundle_expiry_at)

    assert staking.isTargetRegistered(instance_target) is True
    assert staking.isTargetRegistered(component_target) is True
    assert staking.isTargetRegistered(bundle_target) is True

    assert staking.isTarget(instance_target_id) is False
    assert staking.isTarget(component_target_id) is False
    assert staking.isTarget(bundle_target_id) is False

    assert staking.targets() == 0

    # repeat toTarget, difference to before: component and 
    # bundle are now registered in the registry, in this on-chain
    # scenario toTarget will also fill in token attributes
    (cid, component_target) = staking.toTarget(
        type_component, instance_id, riskpool_id, 0, '')

    (bid, bundle_target) = staking.toTarget(
        type_bundle, instance_id, riskpool_id, bundle_id, '')

    # register instance target
    tx = staking.register(iid, instance_target)

    assert 'LogStakingTargetRegistered' in tx.events
    assert tx.events['LogStakingTargetRegistered']['targetId'] == iid
    assert tx.events['LogStakingTargetRegistered']['targetType'] == type_instance
    assert tx.events['LogStakingTargetRegistered']['instanceId'] == instance_id
    assert tx.events['LogStakingTargetRegistered']['componentId'] == 0
    assert tx.events['LogStakingTargetRegistered']['bundleId'] == 0

    assert staking.isTarget(instance_target_id) is True
    assert staking.isTarget(component_target_id) is False
    assert staking.isTarget(bundle_target_id) is False
    assert staking.targets() == 1

    # register component target
    tx = staking.register(cid, component_target)

    assert 'LogStakingTargetRegistered' in tx.events
    assert tx.events['LogStakingTargetRegistered']['targetId'] == cid
    assert tx.events['LogStakingTargetRegistered']['targetType'] == type_component
    assert tx.events['LogStakingTargetRegistered']['instanceId'] == instance_id
    assert tx.events['LogStakingTargetRegistered']['componentId'] == riskpool_id
    assert tx.events['LogStakingTargetRegistered']['bundleId'] == 0

    assert staking.isTarget(instance_target_id) is True
    assert staking.isTarget(component_target_id) is True
    assert staking.isTarget(bundle_target_id) is False
    assert staking.targets() == 2

    # register bundle target
    tx = staking.register(bid, bundle_target)

    assert 'LogStakingTargetRegistered' in tx.events
    assert tx.events['LogStakingTargetRegistered']['targetId'] == bid
    assert tx.events['LogStakingTargetRegistered']['targetType'] == type_bundle
    assert tx.events['LogStakingTargetRegistered']['instanceId'] == instance_id
    assert tx.events['LogStakingTargetRegistered']['componentId'] == riskpool_id
    assert tx.events['LogStakingTargetRegistered']['bundleId'] == bundle_id

    assert staking.isTarget(instance_target_id) is True
    assert staking.isTarget(component_target_id) is True
    assert staking.isTarget(bundle_target_id) is True
    assert staking.targets() == 3

    # check getTargetId for instance, riskpool and bundle targets
    assert staking.getTargetId(0) == iid
    assert staking.getTargetId(1) == cid
    assert staking.getTargetId(2) == bid

    # check getTarget for instance, riskpool and bundle targets
    zero_address = '0x0000000000000000000000000000000000000000'
    zero_data = '0x'

    itarget = staking.getTarget(iid).dict()

    assert itarget['targetType'] == type_instance
    assert itarget['instanceId'] == instance_id
    assert itarget['componentId'] == 0
    assert itarget['bundleId'] == 0
    assert itarget['data'] == zero_data
    assert itarget['token'] == zero_address
    assert itarget['chainId'] == 0

    # check getTarget for riskpool
    ctarget = staking.getTarget(cid).dict()

    assert ctarget['targetType'] == type_component
    assert ctarget['instanceId'] == instance_id
    assert ctarget['componentId'] == riskpool_id
    assert ctarget['bundleId'] == 0
    assert ctarget['data'] == zero_data
    assert ctarget['token'] == usd2
    assert ctarget['chainId'] == web3.chain_id

    # check getTarget for bundle target
    btarget = staking.getTarget(bid).dict()

    assert btarget['targetType'] == type_bundle
    assert btarget['instanceId'] == instance_id
    assert btarget['componentId'] == riskpool_id
    assert btarget['bundleId'] == bundle_id
    assert btarget['data'] == zero_data
    assert btarget['token'] == usd2
    assert btarget['chainId'] == web3.chain_id


def test_targets_failure_modes(
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

    # register token, instance, component (not bundle, yet)
    token = instanceService.getComponentToken(riskpool_id)
    bundleRegistry.registerToken(token)
    staking.setDipContract(dip)

    type_protocol = 1
    type_instance = 2
    type_component = 3

    (iid, instance_target) = staking.toTarget(
        type_instance, instance_id, 0, 0, '')

    bundleRegistry.registerInstance(instance.getRegistry())
    
    # register instance target
    staking.register(iid, instance_target)

    with brownie.reverts('ERROR:STK-200:TARGET_INDEX_TOO_LARGE'):
        target = staking.getTargetId(1)

    (cid, component_target) = staking.toTarget(
        type_component, instance_id, riskpool_id, 0, '')

    # try to get target metadata for a non-registred target
    with brownie.reverts('ERROR:STK-003:TARGET_NOT_REGISTERED'):
        staking.getTarget(cid)

    # try to register protocol target (not (yet) supported)
    with brownie.reverts('ERROR:STK-220:TARGET_TYPE_UNSUPPORTED'):
        (pid, protocol_target) = staking.toTarget(
            type_protocol, 0, 0, 0, '')

    # try to re-register instance target
    with brownie.reverts('ERROR:STK-030:TARGET_ALREADY_REGISTERED'):
        staking.register(iid, instance_target)

    # try to register target with a non-matching id
    with brownie.reverts('ERROR:STK-031:TARGET_DATA_INCONSISTENT'):
        staking.register(cid, instance_target)

    # try to register component target (without having registered component first)
    with brownie.reverts('ERROR:STK-032:TARGET_NOT_IN_REGISTRY'):
        staking.register(cid, component_target)
