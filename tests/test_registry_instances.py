import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    chain,
    web3,
    InstanceRegistry,
)

from scripts.const import ZERO_ADDRESS

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass

DUMMY_INSTANCE_ID = '0x1cd783510e740524e4a1e0070b8c8cd37220ceaf1166960dd1fc0b7858c1de64'
DUMMY_REGISTRY = '0x55F8a0123Fe17710FB0c3393eB916fb8176d87b9'
DUMMY_CHAIN_ID = 1

def test_register_instance_happy_path(
    instance,
    instanceService,
    instanceRegistry: InstanceRegistry,
):
    instance_id = instanceService.getInstanceId()
    chain_id = web3.chain_id
    registry = instance.getRegistry()

    assert instanceRegistry.instances() == 0
    assert instanceRegistry.isRegisteredInstance(instance_id) == False

    tx = instanceRegistry.registerInstance(registry)

    assert 'LogInstanceRegistryInstanceRegistered' in tx.events
    assert tx.events['LogInstanceRegistryInstanceRegistered']['instanceId'] == instance_id
    assert tx.events['LogInstanceRegistryInstanceRegistered']['state'] == 1 # Approved
    assert tx.events['LogInstanceRegistryInstanceRegistered']['isNewInstance'] == True

    assert instanceRegistry.instances() == 1
    assert instanceRegistry.isRegisteredInstance(instance_id) == True
    assert instanceRegistry.getInstanceId(0) == instance_id

    info = instanceRegistry.getInstanceInfo(instance_id)
    assert info['id'] == instance_id
    assert info['state'] == 1 # Approved
    assert info['chainId'] == chain_id
    assert info['registry'] == registry
    assert info['displayName'] == ''
    assert info['createdAt'] > 0 
    assert info['updatedAt'] == info['createdAt']

    chain.sleep(1)
    chain.mine(1)

    # re-register instance on same chain
    tx = instanceRegistry.registerInstance(registry)
    assert 'LogInstanceRegistryInstanceRegistered' in tx.events
    assert tx.events['LogInstanceRegistryInstanceRegistered']['isNewInstance'] == False

    info = instanceRegistry.getInstanceInfo(instance_id)
    assert info['updatedAt'] > info['createdAt']

    assert instanceRegistry.instances() == 1
    assert instanceRegistry.isRegisteredInstance(instance_id) == True

    # register dummy instance on mainnet
    assert instanceRegistry.instances() == 1
    assert instanceRegistry.isRegisteredInstance(instance_id) == True
    assert instanceRegistry.isRegisteredInstance(DUMMY_INSTANCE_ID) == False

    tx = instanceRegistry.registerInstance(
        DUMMY_INSTANCE_ID,
        DUMMY_CHAIN_ID,
        DUMMY_REGISTRY)

    assert 'LogInstanceRegistryInstanceRegistered' in tx.events
    assert tx.events['LogInstanceRegistryInstanceRegistered']['instanceId'] == DUMMY_INSTANCE_ID
    assert tx.events['LogInstanceRegistryInstanceRegistered']['state'] == 1 # Approved
    assert tx.events['LogInstanceRegistryInstanceRegistered']['isNewInstance'] == True

    assert instanceRegistry.instances() == 2
    assert instanceRegistry.isRegisteredInstance(DUMMY_INSTANCE_ID) == True
    assert instanceRegistry.getInstanceId(1) == DUMMY_INSTANCE_ID

    info = instanceRegistry.getInstanceInfo(DUMMY_INSTANCE_ID)
    assert info['id'] == DUMMY_INSTANCE_ID
    assert info['state'] == 1 # Approved
    assert info['chainId'] == DUMMY_CHAIN_ID
    assert info['registry'] == DUMMY_REGISTRY
    assert info['displayName'] == ''
    assert info['createdAt'] > 0 
    assert info['updatedAt'] == info['createdAt']


def test_register_instance_failure_modes(
    instance,
    instanceService,
    instanceRegistry: InstanceRegistry,
    productOwner,
    usd1
):
    instance_id = instanceService.getInstanceId()
    chain_id = web3.chain_id
    registry = instance.getRegistry()

    # attempt to register as non-owner
    with brownie.reverts("Ownable: caller is not the owner"):
        instanceRegistry.registerInstance(
            registry, 
            {'from':productOwner})

    with brownie.reverts("Ownable: caller is not the owner"):
        instanceRegistry.registerInstance(
            DUMMY_INSTANCE_ID,
            DUMMY_CHAIN_ID,
            DUMMY_REGISTRY,
            {'from':productOwner})

    # attempt to register non existing instance on same chain
    with brownie.reverts("ERROR:IRG-120:REGISTRY_NOT_CONTRACT"):
        instanceRegistry.registerInstance(DUMMY_REGISTRY)

    # attempt to register via some arbitrary contract
    with brownie.reverts("ERROR:IRG-121:NOT_REGISTRY_CONTRACT"):
        instanceRegistry.registerInstance(usd1)

    # chain id zero
    with brownie.reverts("ERROR:IRG-030:CHAIN_ID_ZERO"):
        instanceRegistry.registerInstance(
            DUMMY_INSTANCE_ID,
            0,
            DUMMY_REGISTRY)

    # registry addresss zero
    with brownie.reverts("ERROR:IRG-031:REGISTRY_ADDRESS_ZERO"):
        instanceRegistry.registerInstance(
            DUMMY_INSTANCE_ID,
            DUMMY_CHAIN_ID,
            ZERO_ADDRESS)

    # invalid instance id        
    with brownie.reverts("ERROR:IRG-032:INSTANCE_ID_INVALID"):
        instanceRegistry.registerInstance(
            DUMMY_INSTANCE_ID,
            DUMMY_CHAIN_ID + 1,
            DUMMY_REGISTRY)


def test_update_instance_happy_path(
    instance,
    instanceService,
    instanceRegistry: InstanceRegistry,
):
    instance_id = instanceService.getInstanceId()
    chain_id = web3.chain_id
    registry = instance.getRegistry()

    instanceRegistry.registerInstance(registry)

    assert instanceRegistry.instances() == 1
    assert instanceRegistry.isRegisteredInstance(instance_id) == True

    chain.sleep(1)
    chain.mine(1)

    # update instance state to suspended
    state_approved = 1
    state_suspended = 2

    tx = instanceRegistry.updateInstance['bytes32,uint8'](instance_id, state_suspended)

    assert 'LogInstanceRegistryInstanceStateUpdated' in tx.events
    assert tx.events['LogInstanceRegistryInstanceStateUpdated']['instanceId'] == instance_id
    assert tx.events['LogInstanceRegistryInstanceStateUpdated']['oldState'] == state_approved
    assert tx.events['LogInstanceRegistryInstanceStateUpdated']['newState'] == state_suspended

    info = instanceRegistry.getInstanceInfo(instance_id)
    assert info['state'] == state_suspended
    assert info['updatedAt'] > info['createdAt']

    updated_state_at = info['updatedAt']
    
    assert instanceRegistry.instances() == 1
    assert instanceRegistry.isRegisteredInstance(instance_id) == True

    chain.sleep(1)
    chain.mine(1)

    # update instance display name to 'instance-42'
    display_name_old = info['displayName']
    display_name_new = 'instance-42'

    tx = instanceRegistry.updateInstance['bytes32,string'](instance_id, display_name_new)

    assert 'LogInstanceRegistryInstanceDisplayNameUpdated' in tx.events
    assert tx.events['LogInstanceRegistryInstanceDisplayNameUpdated']['instanceId'] == instance_id
    assert tx.events['LogInstanceRegistryInstanceDisplayNameUpdated']['oldDisplayName'] == display_name_old
    assert tx.events['LogInstanceRegistryInstanceDisplayNameUpdated']['newDisplayName'] == display_name_new

    info = instanceRegistry.getInstanceInfo(instance_id)
    assert info['displayName'] == display_name_new
    assert info['updatedAt'] > updated_state_at


def test_update_instance_failure_modes(
    instance,
    instanceService,
    instanceRegistry: InstanceRegistry,
):
    instance_id = instanceService.getInstanceId()
    chain_id = web3.chain_id
    registry = instance.getRegistry()

    state_undefined = 0
    state_suspended = 2
    display_name = 'instance-42'

    with brownie.reverts("ERROR:IRG-020:INSTANCE_NOT_REGISTERED"):
        instanceRegistry.updateInstance['bytes32,uint8'](instance_id, state_suspended)

    with brownie.reverts("ERROR:IRG-022:INSTANCE_NOT_REGISTERED"):
        instanceRegistry.updateInstance['bytes32,string'](instance_id, display_name)

    instanceRegistry.registerInstance(registry)

    with brownie.reverts("ERROR:IRG-021:INSTANCE_STATE_INVALID"):
        instanceRegistry.updateInstance['bytes32,uint8'](instance_id, state_undefined)
