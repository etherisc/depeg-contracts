import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    GifStaking,
    DIP,
)

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


def test_staking_fixture(
    instance,
    instanceService,
    gifStaking: GifStaking,
    dip: DIP,
):
    assert gifStaking.getDip() == dip
    assert gifStaking.instances() == 1

    instanceId = gifStaking.getInstanceId(0)
    assert instanceId == instanceService.getInstanceId()

    info = gifStaking.getInstanceInfo(instanceId)
    assert info[0] == instanceId
    assert info[1] == instanceService.getChainId()
    assert info[2] == instance.getRegistry()
    assert info[3] > 0


def test_re_register_instance(
    instance,
    instanceService,
    gifStaking: GifStaking
):
    with brownie.reverts("ERROR:STK-020:INSTANCE_ALREADY_REGISTERED"):
        gifStaking.registerGifInstance(
            instanceService.getInstanceId(),
            instanceService.getChainId(),
            instance.getRegistry()
        )


def test_register_instance_bad_instance_id(
    instance,
    instanceService,
    gifStakingEmpty: GifStaking
):
    with brownie.reverts("ERROR:STK-023:INSTANCE_INVALID"):
        gifStakingEmpty.registerGifInstance(
            instanceService.getInstanceId()[:-1],
            instanceService.getChainId(),
            instance.getRegistry()
        )


def test_register_instance_bad_chain_id(
    instance,
    instanceService,
    gifStakingEmpty: GifStaking
):
    with brownie.reverts("ERROR:STK-023:INSTANCE_INVALID"):
        gifStakingEmpty.registerGifInstance(
            instanceService.getInstanceId(),
            instanceService.getChainId() + 1,
            instance.getRegistry()
        )


def test_register_instance_bad_registry(
    instance,
    instanceService,
    gifStakingEmpty: GifStaking
):
    with brownie.reverts("ERROR:STK-023:INSTANCE_INVALID"):
        gifStakingEmpty.registerGifInstance(
            instanceService.getInstanceId(),
            instanceService.getChainId() + 1,
            instanceService.address
        )