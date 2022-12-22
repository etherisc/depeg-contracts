import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    chain,
    web3,
    interface,
    ComponentRegistry,
    DepegRiskpool
)

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass

DUMMY_INSTANCE_ID = '0x1cd783510e740524e4a1e0070b8c8cd37220ceaf1166960dd1fc0b7858c1de64'
DUMMY_REGISTRY = '0x55F8a0123Fe17710FB0c3393eB916fb8176d87b9'
DUMMY_CHAIN_ID = 1

def test_register_happy_path(
    instance,
    instanceService: interface.IInstanceService,
    instanceOperator: Account,
    riskpool: DepegRiskpool,
    componentRegistry: ComponentRegistry,
    registryOwner: Account,
):
    instance_id = instanceService.getInstanceId()
    component_id = riskpool.getId()
    chain_id = web3.chain_id
    registry = instance.getRegistry()
    from_owner = {'from':registryOwner}

    # start with registered instance and no components
    componentRegistry.registerInstance(registry, from_owner)

    assert componentRegistry.instances() == 1
    assert componentRegistry.components(instance_id) == 0

    # register riskpool
    tx = componentRegistry.registerComponent(instance_id, component_id, from_owner)

    assert 'LogInstanceRegistryComponentRegistered' in tx.events
    assert tx.events['LogInstanceRegistryComponentRegistered']['instanceId'] == instance_id
    assert tx.events['LogInstanceRegistryComponentRegistered']['componentId'] == component_id
    assert tx.events['LogInstanceRegistryComponentRegistered']['componentType'] == instanceService.getComponentType(component_id)
    assert tx.events['LogInstanceRegistryComponentRegistered']['state'] == instanceService.getComponentState(component_id)
    assert tx.events['LogInstanceRegistryComponentRegistered']['isNewComponent'] == True

    assert componentRegistry.instances() == 1
    assert componentRegistry.components(instance_id) == 1
    assert componentRegistry.getComponentId(instance_id, 0) == component_id
    assert componentRegistry.isRegisteredComponent(instance_id, component_id) == True

    info = componentRegistry.getComponentInfo(instance_id, component_id).dict()
    assert info['key'][0] == instance_id
    assert info['key'][1] == component_id
    assert info['componentType'] == instanceService.getComponentType(component_id)
    assert info['state'] == instanceService.getComponentState(component_id)
    assert info['createdAt'] > 0
    assert info['updatedAt'] == info['createdAt']

    chain.sleep(1)
    chain.mine(1)

    # re-register riskpool on same chain
    tx = componentRegistry.registerComponent(instance_id, component_id, from_owner)

    assert 'LogInstanceRegistryComponentRegistered' in tx.events
    assert tx.events['LogInstanceRegistryComponentRegistered']['isNewComponent'] == False

    info = componentRegistry.getComponentInfo(instance_id, component_id)
    assert info['updatedAt'] > info['createdAt']

    assert componentRegistry.components(instance_id) == 1
    assert componentRegistry.isRegisteredComponent(instance_id, component_id) == True


def test_register_failure_modes(
    instance,
    instanceService: interface.IInstanceService,
    instanceOperator: Account,
    riskpool: DepegRiskpool,
    componentRegistry: ComponentRegistry,
    registryOwner: Account,
    theOutsider: Account,
):
    instance_id = instanceService.getInstanceId()
    component_id = riskpool.getId()
    state_active = 3
    state_suspended = 5

    chain_id = web3.chain_id
    registry = instance.getRegistry()
    from_owner = {'from':registryOwner}

    # start with registered instance and riskpool
    componentRegistry.registerInstance(registry, from_owner)

    assert componentRegistry.instances() == 1
    assert componentRegistry.components(instance_id) == 0

    # try to register component for non registered instance
    with brownie.reverts("ERROR:CRG-001:INSTANCE_NOT_REGISTERED"):
        componentRegistry.registerComponent(DUMMY_INSTANCE_ID, component_id, from_owner)

    assert componentRegistry.instances() == 1
    assert componentRegistry.components(instance_id) == 0

    # try to register non existent component for registered instance
    fake_component_id = 13
    with brownie.reverts("ERROR:CCR-008:INVALID_COMPONENT_ID"):
        componentRegistry.registerComponent(instance_id, fake_component_id, from_owner)

    assert componentRegistry.instances() == 1
    assert componentRegistry.components(instance_id) == 0

    # try to register existent component for registered instance from non-owner account
    with brownie.reverts("Ownable: caller is not the owner"):
        componentRegistry.registerComponent(instance_id, component_id, {'from': instanceOperator})

    assert componentRegistry.instances() == 1
    assert componentRegistry.components(instance_id) == 0

    # register instance on different chain
    componentRegistry.registerInstance(
        DUMMY_INSTANCE_ID,
        DUMMY_CHAIN_ID,
        DUMMY_REGISTRY
    )

    assert componentRegistry.instances() == 2
    assert componentRegistry.components(DUMMY_INSTANCE_ID) == 0

    # try to register component on different chain
    with brownie.reverts("ERROR:CRG-003:DIFFERENT_CHAIN_NOT_SUPPORTET"):
        componentRegistry.registerComponent(DUMMY_INSTANCE_ID, component_id, from_owner)

    assert componentRegistry.instances() == 2
    assert componentRegistry.components(DUMMY_INSTANCE_ID) == 0


def test_update_happy_path(
    instance,
    instanceService: interface.IInstanceService,
    instanceOperator: Account,
    riskpool: DepegRiskpool,
    componentRegistry: ComponentRegistry,
    registryOwner: Account,
    theOutsider: Account,
):
    instance_id = instanceService.getInstanceId()
    component_id = riskpool.getId()
    state_active = 3
    state_suspended = 5

    chain_id = web3.chain_id
    registry = instance.getRegistry()
    from_owner = {'from':registryOwner}

    # start with registered instance and riskpool
    componentRegistry.registerInstance(registry, from_owner)
    componentRegistry.registerComponent(instance_id, component_id, from_owner)

    assert instanceService.getComponentState(component_id) == state_active
    assert componentRegistry.instances() == 1
    assert componentRegistry.components(instance_id) == 1
    assert componentRegistry.isRegisteredComponent(instance_id, component_id) == True

    chain.sleep(1)
    chain.mine(1)

    # suspend riskpool
    instanceOperatorService = instance.getInstanceOperatorService()
    instanceOperatorService.suspend(component_id, {'from': instanceOperator})

    assert instanceService.getComponentState(component_id) == state_suspended

    tx = componentRegistry.updateComponent(instance_id, component_id, {'from': theOutsider})

    assert 'LogInstanceRegistryComponentUpdated' in tx.events
    assert tx.events['LogInstanceRegistryComponentUpdated']['instanceId'] == instance_id
    assert tx.events['LogInstanceRegistryComponentUpdated']['componentId'] == component_id
    assert tx.events['LogInstanceRegistryComponentUpdated']['oldState'] == state_active
    assert tx.events['LogInstanceRegistryComponentUpdated']['newState'] == state_suspended

    info = componentRegistry.getComponentInfo(instance_id, component_id).dict()
    assert info['key'][0] == instance_id
    assert info['key'][1] == component_id
    assert info['componentType'] == instanceService.getComponentType(component_id)
    assert info['state'] == state_suspended
    assert info['createdAt'] > 0
    assert info['updatedAt'] > info['createdAt']


def test_update_failure_modes(
    instance,
    instanceService: interface.IInstanceService,
    instanceOperator: Account,
    riskpool: DepegRiskpool,
    componentRegistry: ComponentRegistry,
    registryOwner: Account,
    theOutsider: Account,
):
    instance_id = instanceService.getInstanceId()
    component_id = riskpool.getId()
    state_active = 3
    state_suspended = 5

    chain_id = web3.chain_id
    registry = instance.getRegistry()
    from_owner = {'from':registryOwner}

    # try to update component on non-registered instance
    with brownie.reverts("ERROR:IRG-041:INSTANCE_NOT_REGISTERED"):
        componentRegistry.updateComponent(instance_id, component_id, from_owner)

    assert componentRegistry.instances() == 0
    assert componentRegistry.components(instance_id) == 0
    assert componentRegistry.isRegisteredComponent(instance_id, component_id) == False

    # register instance and try again
    componentRegistry.registerInstance(registry, from_owner)

    # try to update non-registered component
    with brownie.reverts("ERROR:CRG-002:COMPONENT_NOT_REGISTERED"):
        componentRegistry.updateComponent(instance_id, component_id, from_owner)

    assert componentRegistry.instances() == 1
    assert componentRegistry.components(instance_id) == 0
    assert componentRegistry.isRegisteredComponent(instance_id, component_id) == False

    # register instance on different chain
    componentRegistry.registerInstance(
        DUMMY_INSTANCE_ID,
        DUMMY_CHAIN_ID,
        DUMMY_REGISTRY
    )

    # try to update compnent on instance on different chain
    with brownie.reverts("ERROR:CRG-003:DIFFERENT_CHAIN_NOT_SUPPORTET"):
        componentRegistry.updateComponent(DUMMY_INSTANCE_ID, component_id, from_owner)

    assert componentRegistry.instances() == 2
    assert componentRegistry.components(DUMMY_INSTANCE_ID) == 0
    assert componentRegistry.isRegisteredComponent(DUMMY_INSTANCE_ID, component_id) == False
