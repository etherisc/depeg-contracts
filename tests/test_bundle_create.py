import brownie
from scripts.util import b2s

from scripts.depeg_product import (
    GifDepegProduct,
    GifDepegRiskpool,
)

def test_create_bundle_happy_case(
    instance,
    instanceService,
    instanceOperator,
    investor,
    riskpool,
):
    instanceWallet = instanceService.getInstanceWallet()
    riskpoolWallet = instanceService.getRiskpoolWallet(riskpool.getId())
    tokenAddress = instanceService.getComponentToken(riskpool.getId())
    token = interface.IERC20(tokenAddress)

    bundle_funding = 100000

    # check initialized riskpool
    assert instanceService.bundles() == 0
    assert token.balanceOf(instanceWallet) == 0
    assert token.balanceOf(riskpoolWallet) == 0
    assert token.balanceOf(investor) == 0
    assert token.balanceOf(instanceOperator) >= bundle_funding

    # check riskpool bundles
    assert riskpool.activeBundles() == 0
    assert riskpool.bundles() == 0

    bundleName = 'test bundle'
    bundleLifetimeDays = 90
    minProtectedBalance = 2000
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

    # check wallet balances against bundle investment
    fixedFee = 0
    fractionalFee = 0
    capital_fees = fractionalFee * bundle_funding + fixedFee
    net_capital = bundle_funding - capital_fees
    tf = 10**token.decimals()

    # check riskpool bundles
    assert riskpool.activeBundles() == 1
    assert riskpool.bundles() == 1
    assert riskpool.getBundleId(0) == bundleId

    with brownie.reverts('ERROR:RPL-007:BUNDLE_INDEX_TOO_LARGE'):
        riskpool.getBundleId(1) > 0

    assert instanceService.bundles() == 1
    assert token.balanceOf(riskpoolWallet) == net_capital * tf
    assert token.balanceOf(instanceWallet) == capital_fees * tf

    print('bundle {} created'.format(bundleId))

    # check riskpool statistics
    assert instanceService.getCapital(riskpool.getId()) == net_capital * tf
    assert instanceService.getCapacity(riskpool.getId()) == net_capital * tf
    assert instanceService.getBalance(riskpool.getId()) == net_capital * tf
    assert instanceService.getTotalValueLocked(riskpool.getId()) == 0

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
    assert capital == net_capital * tf
    assert lockedCapital == 0
    assert balance == net_capital * tf
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

    minSumInsured = riskpool.calculateSumInsured(minProtectedBalance)
    maxSumInsured = riskpool.calculateSumInsured(maxProtectedBalance)
    
    assert filterMinSumInsured == minSumInsured * tf
    assert filterMaxSumInsured == maxSumInsured * tf
    assert filterMinDuration == minDurationDays * 24 * 3600
    assert filterMaxDuration == maxDurationDays * 24 * 3600
    assert filterAnnualPercentageReturn == riskpool.getApr100PercentLevel() * aprPercentage / 100.0

    bundleInfo = riskpool.getBundleInfo(bundleId).dict()
    print('bundleInfo {}'.format(bundleInfo))

    assert bundleInfo['state'] == state
    assert bundleInfo['tokenId'] == tokenId
    assert bundleInfo['owner'] == investor

    assert bundleInfo['name'] == bundleName
    assert bundleInfo['lifetime'] == bundleLifetimeDays * 24 * 3600

    assert bundleInfo['minSumInsured'] == minSumInsured * tf
    assert bundleInfo['maxSumInsured'] == maxSumInsured * tf
    assert bundleInfo['minDuration'] == filterMinDuration
    assert bundleInfo['maxDuration'] == filterMaxDuration
    assert bundleInfo['annualPercentageReturn'] == filterAnnualPercentageReturn

    assert bundleInfo['capitalSupportedByStaking'] == riskpool.getBundleCapitalCap()
    assert bundleInfo['capital'] == capital
    assert bundleInfo['lockedCapital'] == lockedCapital
    assert bundleInfo['balance'] == balance
    assert bundleInfo['createdAt'] == createdAt


def test_create_name_validation(
    instance,
    instanceService,
    instanceOperator,
    investor,
    riskpool,
):
    instanceWallet = instanceService.getInstanceWallet()
    riskpoolWallet = instanceService.getRiskpoolWallet(riskpool.getId())
    tokenAddress = instanceService.getComponentToken(riskpool.getId())
    token = interface.IERC20(tokenAddress)

    bundle_funding = 10000

    # check initialized riskpool
    assert instanceService.bundles() == 0

    bundleName = ''
    bundleLifetimeDays = 30
    minProtectedBalance = 2000
    maxProtectedBalance = 10000
    minDurationDays = 14
    maxDurationDays = 60
    aprPercentage = 5.0

    bundleId1 =