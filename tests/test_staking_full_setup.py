import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    chain,
    GifStaking,
    DIP,
    USD2
)

from scripts.setup import (
    create_bundle, 
    apply_for_policy
)

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


def test_staking_full_setup(
    instance,
    instanceOperator,
    product,
    customer,
    investor,
    riskpool,
    instanceService,
    gifStaking: GifStaking,
    stakerWithDips,
    usd2: USD2,
    dip: DIP,
):
    print('--- create bundle ---')
    bundleFunding = 15000 * 10**usd2.decimals()
    bundleMaxSumInsured = bundleFunding 
    instanceId = instanceService.getInstanceId()
    bundleId = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool, 
        funding=bundleFunding,
        maxSumInsured=bundleMaxSumInsured)

    bundle = instanceService.getBundle(bundleId).dict()

    print('--- link gif staking to riskpool ---')
    riskpool.setStakingDataProvider(gifStaking)

    print('--- link gif staking to gif instance ---')
    gifStaking.registerToken(riskpool.getErc20Token())
    gifStaking.updateBundleState(instanceId, bundleId)

    print('--- setup token exchange rate ---')
    chainId = instanceService.getChainId()
    leverageFactor = 0.1
    stakingRate = leverageFactor * gifStaking.getDipToTokenParityLevel() # 1 dip unlocks 10 cents (usd1)
    usd2Decimals = 1 # just dummy value, real value will be picked up on-chain
    
    gifStaking.setDipContract(dip.address, {'from': instanceOperator})
    gifStaking.setStakingRate(
        usd2.address, 
        chainId, 
        stakingRate,
        {'from': instanceOperator})

    print('--- attempt to buy a policy with insufficient staking ---')
    assert gifStaking.getBundleStakes(instanceId, bundleId) == 0
    assert gifStaking.getBundleCapitalSupport(instanceId, bundleId) == 0

    bundleInfo = riskpool.getBundleInfo(bundleId)
    print('bundleInfo {}'.format(bundleInfo))

    assert bundleInfo['bundleId'] == bundleId
    assert bundleInfo['capitalSupportedByStaking'] == 0
    assert bundleInfo['capital'] > 0.9 * bundleFunding

    sumInsured = 4000 * 10**usd2.decimals()
    durationDays = 60
    maxPremium = 750 * 10**usd2.decimals()

    assert bundleInfo['lockedCapital'] == 0
    assert sumInsured < bundleInfo['capital']
    assert sumInsured > gifStaking.getBundleCapitalSupport(instanceId, bundleId)

    processId1 = apply_for_policy(
        instance, 
        instanceOperator, 
        product, 
        customer, 
        sumInsured, 
        durationDays, 
        maxPremium)

    metadata = instanceService.getMetadata(processId1)
    application = instanceService.getApplication(processId1)

    policy1 = instanceService.getPolicy(processId1).dict()
    assert policy1['premiumPaidAmount'] == policy1['premiumExpectedAmount']
    assert policy1['premiumPaidAmount'] > 0

    print('processId1 {}'.format(processId1))
    print('metadata {}'.format(metadata))
    print('application {}'.format(application))

    print('--- add bundle stakes and retry to buy a policy---')
    amountInUnits = 10**5
    stakingAmount = amountInUnits * 10**dip.decimals()
    gifStaking.stake(instanceId, bundleId, stakingAmount, {'from': stakerWithDips})

    # check conditions to allow for underwriting
    assert sumInsured <= gifStaking.getBundleCapitalSupport(instanceId, bundleId)
    assert sumInsured <= bundle['capital'] - bundle['lockedCapital']

    processId2 = apply_for_policy(
        instance, 
        instanceOperator, 
        product, 
        customer, 
        sumInsured, 
        durationDays, 
        maxPremium)

    metadata = instanceService.getMetadata(processId2)
    application = instanceService.getApplication(processId2)
    policy = instanceService.getPolicy(processId2)

    print('processId2 {}'.format(processId2))
    print('metadata2 {}'.format(metadata))
    print('application2 {}'.format(application))
    print('policy2 {}'.format(policy))

    # check updated bundleInfo
    bundleInfo2 = riskpool.getBundleInfo(bundleId)
    print('bundleInfo2 {}'.format(bundleInfo2))

    assert bundleInfo2['bundleId'] == bundleId
    assert bundleInfo2['capitalSupportedByStaking'] == gifStaking.getBundleCapitalSupport(instanceId, bundleId)
    assert bundleInfo2['capital'] == bundleInfo['capital']
    assert bundleInfo2['lockedCapital'] == 2 * sumInsured
