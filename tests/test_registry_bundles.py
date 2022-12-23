import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    chain,
    web3,
    interface,
    BundleRegistry,
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
    riskpool: DepegRiskpool,
    bundleRegistry: BundleRegistry,
    registryOwner: Account,
    theOutsider: Account,
):
    instance_id = instanceService.getInstanceId()
    riskpool_id = riskpool.getId()
    chain_id = web3.chain_id
    registry = instance.getRegistry()
    from_owner = {'from':registryOwner}

    # start with registered instance and riskpool
    bundleRegistry.registerInstance(registry, from_owner)
    bundleRegistry.registerComponent(instance_id, riskpool_id, from_owner)

    assert bundleRegistry.instances() == 1
    assert bundleRegistry.components(instance_id) == 1
    assert bundleRegistry.bundles(instance_id, riskpool_id) == 0

    # register bundle


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
    riskpool: DepegRiskpool,
    bundleRegistry: BundleRegistry,
    registryOwner: Account,
    theOutsider: Account,
):
    instance_id = instanceService.getInstanceId()
    riskpool_id = riskpool.getId()
    chain_id = web3.chain_id
    registry = instance.getRegistry()
    from_owner = {'from':registryOwner}

    # start with registered instance and riskpool
    bundleRegistry.registerInstance(registry, from_owner)
    bundleRegistry.registerComponent(instance_id, riskpool_id, from_owner)

    chain.sleep(1)
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
