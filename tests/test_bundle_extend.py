import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    chain,
    history,
    interface,
)

from scripts.util import b2s

from scripts.depeg_product import (
    GifDepegProduct,
    GifDepegRiskpool,
)

from scripts.setup import (
    create_bundle,
    apply_for_policy_with_bundle
)

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass

def test_extend_bundle(
    instance,
    instanceService,
    instanceOperator,
    investor,
    riskpool,
    product,
    customer,
    protectedWallet
):
    instanceWallet = instanceService.getInstanceWallet()
    riskpoolWallet = instanceService.getRiskpoolWallet(riskpool.getId())
    tokenAddress = instanceService.getComponentToken(riskpool.getId())
    token = interface.IERC20Metadata(tokenAddress)

    bundle_funding = 100000

    bundleName = 'test bundle'
    bundleLifetimeDays = 90
    minProtectedBalance =  2000
    maxProtectedBalance = 10000
    minDurationDays = 14
    maxDurationDays = 60
    aprPercentage = 5.0
    bundleId = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool, 
        bundle_funding, 
        bundleName,
        bundleLifetimeDays,
        minProtectedBalance, 
        maxProtectedBalance, 
        minDurationDays, 
        maxDurationDays, 
        aprPercentage)

    # check riskpool bundles
    assert riskpool.activeBundles() == 1
    assert riskpool.bundles() == 1
    assert riskpool.getBundleId(0) == bundleId

    print('bundle {} created'.format(bundleId))

    # check bundle statistics
    (
        id, 
        riskpoolId, 
        tokenId, 
        state, 
        bundleFilter, 
        capital, 
        lockedCapital, 
        balance, 
        createdAt, 
        updatedAt
    ) = instanceService.getBundle(bundleId)

    assert id == bundleId
    assert riskpoolId == riskpool.getId()
    assert state == 0 # enum BundleState { Active, Locked, Closed, Burned }
    assert createdAt > 0
    assert updatedAt == createdAt

    # check bundle filter data
    (
        filterBundleName,
        filterBundleLifetime,
        filterMinSumInsured,
        filterMaxSumInsured,
        filterMinDuration,
        filterMaxDuration,
        filterAnnualPercentageReturn
    ) = riskpool.decodeBundleParamsFromFilter(bundleFilter)

    assert filterBundleName == bundleName
    assert filterBundleLifetime == bundleLifetimeDays * 24 * 3600

    bundleInfo = riskpool.getBundleInfo(bundleId).dict()
    print('bundleInfo {}'.format(bundleInfo))

    assert bundleInfo['state'] == state
    assert bundleInfo['tokenId'] == tokenId
    assert bundleInfo['owner'] == investor

    assert bundleInfo['name'] == bundleName
    assert bundleInfo['lifetime'] == bundleLifetimeDays * 24 * 3600

    assert bundleInfo['minDuration'] == filterMinDuration
    assert bundleInfo['maxDuration'] == filterMaxDuration
    assert bundleInfo['annualPercentageReturn'] == filterAnnualPercentageReturn

    assert bundleInfo['createdAt'] == createdAt

    (
        ltState,
        ltCreatedAt,
        ltLifetime,
        ltExtendedLifetime,
        ltIsExpired
    ) = riskpool.getBundleLifetimeData(bundleId)

    assert ltState == state
    assert ltCreatedAt == createdAt
    assert ltLifetime == filterBundleLifetime
    assert ltExtendedLifetime == ltLifetime
    assert ltIsExpired is False

    # create 1st policy
    protectedBalance = 5000
    sumInsured = riskpool.calculateSumInsured(protectedBalance)
    durationDays = 60
    maxPremium = 750

    processId1 = apply_for_policy_with_bundle(
        instance,
        instanceOperator,
        product,
        customer,
        bundleId,
        protectedWallet,
        protectedBalance,
        durationDays,
        maxPremium)

    assert 'LogDepegPolicyCreated' in history[-1].events

    # attemt bad ways to extend the bundle lifetime
    extend_45_days = 45 * 24 * 3600
    extend_zero_days = 0

    # check only bundle owner
    with brownie.reverts("ERROR:RPL-002:NOT_BUNDLE_OWNER"):
        riskpool.extendBundleLifetime(bundleId, extend_45_days, {'from': instanceOperator})

    # check extension time
    with brownie.reverts("ERROR:DRP-030:LIFETIME_EXTENSION_INVALID"):
        riskpool.extendBundleLifetime(bundleId, extend_zero_days, {'from': investor})

    # check wrong state
    riskpool.lockBundle(bundleId, {'from': investor})
    with brownie.reverts("ERROR:DRP-031:BUNDLE_NOT_ACTIVE"):
        riskpool.extendBundleLifetime(bundleId, extend_45_days, {'from': investor})

    riskpool.unlockBundle(bundleId, {'from': investor})
    with brownie.reverts("ERROR:DRP-033:TOO_EARLY"):
        riskpool.extendBundleLifetime(bundleId, extend_45_days, {'from': investor})

    # set clock at time where bundle extension is supported
    sleep_time = bundleLifetimeDays * 24 * 3600 - (riskpool.EXTENSION_INTERVAL() - 10)
    chain.sleep(sleep_time)
    chain.mine(1)

    tx = riskpool.extendBundleLifetime(bundleId, extend_45_days, {'from': investor})

    (
        ltState2,
        ltCreatedAt2,
        ltLifetime2,
        ltExtendedLifetime2,
        ltIsExpired2
    ) = riskpool.getBundleLifetimeData(bundleId)

    assert ltState2 == ltState
    assert ltCreatedAt2 == ltCreatedAt
    assert ltLifetime2 == ltLifetime
    assert ltExtendedLifetime2 == ltLifetime2 + extend_45_days
    assert ltIsExpired2 == ltIsExpired

    # check log entry
    assert 'LogBundleExtended' in tx.events
    evt = tx.events['LogBundleExtended']
    assert evt['bundleId'] == bundleId
    assert evt['createdAt'] == ltCreatedAt2
    assert evt['lifetime'] == ltLifetime2
    assert evt['lifetimeExtended'] == ltExtendedLifetime2

    # set clock at time where original lifetime would lead to expired bundle
    chain.sleep(extend_45_days)
    chain.mine(1)

    (
        ltState3,
        ltCreatedAt3,
        ltLifetime3,
        ltExtendedLifetime3,
        ltIsExpired3
    ) = riskpool.getBundleLifetimeData(bundleId)

    assert chain.time() > ltCreatedAt3 + ltLifetime3
    assert chain.time() < ltCreatedAt3 + ltExtendedLifetime3
    assert ltIsExpired3 is False

    # check that a policy can be created
    processId2 = apply_for_policy_with_bundle(
        instance,
        instanceOperator,
        product,
        customer,
        bundleId,
        protectedWallet,
        protectedBalance,
        durationDays,
        maxPremium)

    assert 'LogDepegPolicyCreated' in history[-1].events

    # set clock after expiry
    sleep_time = ltCreatedAt3 + ltExtendedLifetime3 - chain.time() + 1
    chain.sleep(sleep_time)
    chain.mine(1)

    (
        ltState4,
        ltCreatedAt4,
        ltLifetime4,
        ltExtendedLifetime4,
        ltIsExpired4
    ) = riskpool.getBundleLifetimeData(bundleId)

    assert chain.time() > ltCreatedAt4 + ltLifetime4
    assert chain.time() > ltCreatedAt4 + ltExtendedLifetime4
    assert ltIsExpired4 is True

    # attempt to further extend lifetime
    with brownie.reverts("ERROR:DRP-032:BUNDLE_EXPIRED"):
        riskpool.extendBundleLifetime(bundleId, extend_45_days, {'from': investor})

    # attempt to create additional policy
    with brownie.reverts("ERROR:DP-016:UNDERWRITING_FAILED"):
        product.applyForPolicyWithBundle(
            protectedWallet,
            protectedBalance * 10**6,
            durationDays * 24 * 3600,
            bundleId,
            {'from': customer})

    assert 'LogDepegPolicyCreated' not in history[-1].events
