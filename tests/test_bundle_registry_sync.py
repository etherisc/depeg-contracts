import brownie
import pytest

from brownie import MockRegistryStaking

from scripts.setup import create_bundle


# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


def test_close_and_burn_bundle_sync_registry_expiry(
    instance,
    instanceService,
    instanceOperator,
    investor,
    riskpool,
    riskpoolKeeper,
    riskpoolWallet,
    dip,
    usd2,
    registryOwner,
):
    mock = MockRegistryStaking.deploy(dip, usd2, {'from': registryOwner})
    mock.mockRegisterRiskpool(instanceService.getInstanceId(), riskpool.getId(), {'from': registryOwner})
    riskpool.setStakingAddress(mock, {'from': riskpoolKeeper})

    bundle_id = create_bundle(
        instance,
        instanceOperator,
        investor,
        riskpool,
        funding=100000,
        bundleName='registry-sync-bundle',
        bundleLifetimeDays=90,
        minProtectedBalance=2000,
        maxProtectedBalance=10000,
        minDurationDays=14,
        maxDurationDays=60,
        aprPercentage=5.0,
    )

    bundle_nft = mock.getBundleNftId(instanceService.getInstanceId(), bundle_id)
    registry_data_before = mock.decodeBundleData(bundle_nft).dict()
    bundle_before = instanceService.getBundle(bundle_id).dict()

    assert registry_data_before['expiryAt'] == bundle_before['createdAt'] + 90 * 24 * 3600

    brownie.chain.sleep(123)
    brownie.chain.mine(1)
    close_ts = brownie.chain.time()

    tx_close = riskpool.closeBundle(bundle_id, {'from': investor})
    assert 'LogRiskpoolBundleClosed' in tx_close.events
    assert 'LogMockBundleExpirySet' in tx_close.events

    registry_data_closed = mock.decodeBundleData(bundle_nft).dict()
    assert registry_data_closed['expiryAt'] == close_ts

    token = brownie.interface.IERC20Metadata(instanceService.getComponentToken(riskpool.getId()))
    token.approve(instanceService.getTreasuryAddress(), 0, {'from': riskpoolWallet})
    token.approve(instanceService.getTreasuryAddress(), 10**30, {'from': riskpoolWallet})

    bundle_balance = instanceService.getBundle(bundle_id).dict()['balance']
    riskpool.defundBundle(bundle_id, bundle_balance, {'from': investor})

    brownie.chain.sleep(77)
    brownie.chain.mine(1)
    burn_ts = brownie.chain.time()

    tx_burn = riskpool.burnBundle(bundle_id, {'from': investor})
    assert 'LogRiskpoolBundleBurned' in tx_burn.events

    registry_data_burned = mock.decodeBundleData(bundle_nft).dict()
    assert registry_data_burned['expiryAt'] == close_ts
    assert registry_data_burned['expiryAt'] < burn_ts
