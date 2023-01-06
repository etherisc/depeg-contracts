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


def test_targets_happy_path(
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

    # register instance target
    staking.register(iid, instance_target)

    # TODO check log entry (LogStakingTargetRegistered)

    assert staking.isTarget(instance_target_id) is True
    assert staking.isTarget(component_target_id) is False
    assert staking.isTarget(bundle_target_id) is False
    assert staking.targets() == 1

    # register component target
    staking.register(cid, component_target)

    # TODO check log entry

    assert staking.isTarget(instance_target_id) is True
    assert staking.isTarget(component_target_id) is True
    assert staking.isTarget(bundle_target_id) is False
    assert staking.targets() == 2

    # register bundle target
    staking.register(bid, bundle_target)

    # TODO check log entry

    assert staking.isTarget(instance_target_id) is True
    assert staking.isTarget(component_target_id) is True
    assert staking.isTarget(bundle_target_id) is True
    assert staking.targets() == 3

    # TODO check log entry

    # TODO check getTargeteId for instance, riskpool and bundle targets

    # TODO check getTarget for instance, riskpool and bundle targets


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
