import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    GifStaking,
    DIP,
)

from scripts.setup import create_bundle

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

    info = gifStaking.getInstanceInfo(instanceId).dict()
    assert info['id'] == instanceId
    assert info['chainId'] == instanceService.getChainId()
    assert info['registry'] == instance.getRegistry()
    assert info['createdAt'] > 0


def test_update_bundle(
    instance,
    instanceOperator,
    investor,
    riskpool,
    instanceService,
    gifStaking: GifStaking,
    dip: DIP,
):
    bundleId = create_bundle(instance, instanceOperator, investor, riskpool)
    assert instanceService.bundles() == 1

    bundle = instanceService.getBundle(bundleId).dict()
    token = instanceService.getComponentToken(bundle['riskpoolId'])
    print('bundle {} token {}'.format(bundle, token))

    instanceId = instanceService.getInstanceId()
    gifStaking.updateBundleState(instanceId, bundleId)
    bundleInfo = gifStaking.getBundleInfo(instanceId, bundleId).dict()
    print('bundleInfo {}'.format(bundleInfo))

    assert bundleInfo['key'][0] == instanceService.getInstanceId()
    assert bundleInfo['key'][1] == bundleId 
    assert bundleInfo['chainId'] == instanceService.getChainId()
    assert bundleInfo['token'] == token # riskpool token for riskpool associated with bundle
    assert bundleInfo['state'] == bundle['state'] # enum BundleState { Active, Locked, Closed, Burned }
    assert bundleInfo['closedSince'] == 0
    assert bundleInfo['createdAt'] >= bundle['createdAt']
    assert bundleInfo['updatedAt'] == bundleInfo['createdAt']


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