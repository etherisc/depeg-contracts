import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    chain,
    history,
    interface
)

from scripts.util import b2s

from scripts.depeg_product import (
    GifDepegProduct,
    GifDepegRiskpool,
)

from scripts.setup import (
    create_bundle, 
    apply_for_policy_with_bundle,
)

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass

def test_create_application(
    instance,
    instanceService,
    instanceOperator,
    instanceWallet,
    investor,
    customer,
    protectedWallet,
    product,
    riskpool
):
    instanceWallet = instanceService.getInstanceWallet()
    riskpoolWallet = instanceService.getRiskpoolWallet(riskpool.getId())
    tokenAddress = instanceService.getComponentToken(riskpool.getId())
    token = interface.IERC20Metadata(tokenAddress)
    tf = 10 ** token.decimals()

    bundleId = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool)

    riskpoolBalanceBefore = instanceService.getBalance(riskpool.getId())
    instanceBalanceBefore = token.balanceOf(instanceWallet)

    protectedBalance = 10000
    sumInsured = riskpool.calculateSumInsured(protectedBalance)
    durationDays = 60
    maxPremium = 750

    processId = apply_for_policy_with_bundle(
        instance,
        instanceOperator,
        product,
        customer,
        bundleId,
        protectedWallet,
        protectedBalance,
        durationDays,
        maxPremium)

    tx = history[-1]
    assert 'LogDepegApplicationCreated' in tx.events
    assert tx.events['LogDepegApplicationCreated']['processId'] == processId
    assert tx.events['LogDepegApplicationCreated']['policyHolder'] == customer
    assert tx.events['LogDepegApplicationCreated']['protectedWallet'] == protectedWallet
    assert tx.events['LogDepegApplicationCreated']['sumInsuredAmount'] == sumInsured * tf
    assert tx.events['LogDepegApplicationCreated']['premiumAmount'] <= maxPremium * tf

    # check collateralization with specified bundle
    appl_bundle_id = get_bundle_id(instanceService, riskpool, processId)
    assert appl_bundle_id == bundleId
    assert 'LogBundlePolicyCollateralized' in tx.events
    assert tx.events['LogBundlePolicyCollateralized']['bundleId'] == bundleId

    assert 'LogDepegPolicyCreated' in tx.events
    assert tx.events['LogDepegPolicyCreated']['processId'] == processId
    assert tx.events['LogDepegPolicyCreated']['policyHolder'] == customer
    assert tx.events['LogDepegPolicyCreated']['sumInsuredAmount'] == sumInsured * tf

    metadata = instanceService.getMetadata(processId).dict()
    application = instanceService.getApplication(processId).dict()
    policy = instanceService.getPolicy(processId).dict()

    print('policy {} created'.format(processId))
    print('metadata {}'.format(metadata))
    print('application {}'.format(application))
    print('policy {}'.format(policy))

    # check metadata
    assert metadata['owner'] == customer
    assert metadata['productId'] == product.getId()

    # check application
    premium = application['premiumAmount']
    assert premium <= maxPremium * tf
    assert application['sumInsuredAmount'] == sumInsured * tf

    riskpoolBalanceAfter = instanceService.getBalance(riskpool.getId())
    instanceBalanceAfter = token.balanceOf(instanceWallet)

    fixedFee = 0
    fractionalFee = 0.05
    premiumFees = fractionalFee * premium + fixedFee
    netPremium = premium - premiumFees

    (
        wallet,
        protected_balance,
        applicationDuration,
        applicationBundleId,
        applicationMaxPremium
    ) = riskpool.decodeApplicationParameterFromData(application['data'])

    assert wallet == protectedWallet
    assert protected_balance == protectedBalance * tf
    assert applicationDuration == durationDays * 24 * 3600
    assert applicationBundleId == bundleId
    assert applicationMaxPremium == netPremium

    # check policy
    assert policy['premiumExpectedAmount'] == premium
    assert policy['premiumPaidAmount'] == premium
    assert policy['claimsCount'] == 0
    assert policy['openClaimsCount'] == 0
    assert policy['payoutMaxAmount'] == sumInsured * tf
    assert policy['payoutAmount'] == 0

    # check wallet balances against premium payment
    assert riskpoolBalanceAfter == riskpoolBalanceBefore + netPremium
    assert instanceBalanceAfter == instanceBalanceBefore + premiumFees



def test_application_with_expired_bundle(
    instance,
    instanceService,
    instanceOperator,
    instanceWallet,
    investor,
    customer,
    protectedWallet,
    protectedWallet2,
    product,
    riskpool,
    usd1,
    usd2
):
    instanceWallet = instanceService.getInstanceWallet()
    riskpoolWallet = instanceService.getRiskpoolWallet(riskpool.getId())
    tokenAddress = instanceService.getComponentToken(riskpool.getId())
    token = interface.IERC20(tokenAddress)

    bundleId = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool)

    protectedBalance = 10000
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

    print('application1: {}'.format(instanceService.getApplication(processId1).dict()))
    print('policy1: {}'.format(instanceService.getPolicy(processId1).dict()))

    chain.sleep(riskpool.getMaxBundleLifetime() + 1)
    chain.mine(1)

    with brownie.reverts("ERROR:DP-014:UNDERWRITING_FAILED"):
        apply_for_policy_with_bundle(
            instance, 
            instanceOperator,
            product,
            customer,
            bundleId,
            protectedWallet2,
            protectedBalance,
            durationDays,
            maxPremium)


def get_bundle_id(
    instance_service,
    riskpool,
    process_id
):
    data = instance_service.getApplication(process_id).dict()['data']
    params = riskpool.decodeApplicationParameterFromData(data).dict()
    return params['bundleId']