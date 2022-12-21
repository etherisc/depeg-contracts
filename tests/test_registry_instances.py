import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    chain,
    web3,
    InstanceRegistry,
)

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

# TODO test for registering failure modes

# TODO test for update function

# TODO test for update failure modes

# def test_register_instance_bad_instance_id(
#     instance,
#     instanceService,
#     gifStakingEmpty: GifStaking
# ):
#     with brownie.reverts("ERROR:STK-023:INSTANCE_INVALID"):
#         gifStakingEmpty.registerGifInstance(
#             instanceService.getInstanceId()[:-1],
#             instanceService.getChainId(),
#             instance.getRegistry()
#         )


# def test_register_instance_bad_chain_id(
#     instance,
#     instanceService,
#     gifStakingEmpty: GifStaking
# ):
#     with brownie.reverts("ERROR:STK-023:INSTANCE_INVALID"):
#         gifStakingEmpty.registerGifInstance(
#             instanceService.getInstanceId(),
#             instanceService.getChainId() + 1,
#             instance.getRegistry()
#         )


# def test_register_instance_bad_registry(
#     instance,
#     instanceService,
#     gifStakingEmpty: GifStaking
# ):
#     with brownie.reverts("ERROR:STK-023:INSTANCE_INVALID"):
#         gifStakingEmpty.registerGifInstance(
#             instanceService.getInstanceId(),
#             instanceService.getChainId() + 1,
#             instanceService.address
#         )