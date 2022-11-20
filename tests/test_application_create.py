import brownie
import pytest

from brownie.network.account import Account
from brownie import interface

from scripts.util import b2s

from scripts.depeg_product import (
    GifDepegProduct,
    GifDepegRiskpool,
)

from scripts.setup import (
    create_bundle, 
    apply_for_policy,
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
    product,
    riskpool
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

    riskpoolBalanceBefore = instanceService.getBalance(riskpool.getId())
    instanceBalanceBefore = token.balanceOf(instanceWallet)

    sumInsured = 10000
    durationDays = 60
    maxPremium = 750

    processId = apply_for_policy(
        instance, 
        instanceOperator, 
        product, 
        customer, 
        sumInsured, 
        durationDays, 
        maxPremium)

    metadata = instanceService.getMetadata(processId)
    application = instanceService.getApplication(processId)
    policy = instanceService.getPolicy(processId)

    print('policy {} created'.format(processId))
    print('metadata {}'.format(metadata))
    print('application {}'.format(application))
    print('policy {}'.format(policy))

    # check metadata
    assert metadata[0] == customer
    assert metadata[1] == product.getId()

    # check application
    assert application[1] == maxPremium
    assert application[2] == sumInsured

    riskpoolBalanceAfter = instanceService.getBalance(riskpool.getId())
    instanceBalanceAfter = token.balanceOf(instanceWallet)

    premiumFees = 0.1 * maxPremium + 3
    netPremium = maxPremium - premiumFees

    (
        applicationDuration,
        applicationMaxPremium
    ) = riskpool.decodeApplicationParameterFromData(application[3])

    assert applicationDuration == durationDays * 24 * 3600
    assert applicationMaxPremium == netPremium

    # check policy
    assert policy[1] == maxPremium # premium expected amouint
    assert policy[2] == maxPremium # premium paid amouint
    assert policy[3] == 0 # claims count
    assert policy[4] == 0 # open claims count
    assert policy[5] == sumInsured # payout max amount
    assert policy[6] == 0 # payout amount

    # check wallet balances against premium payment
    assert riskpoolBalanceAfter == riskpoolBalanceBefore + netPremium
    assert instanceBalanceAfter == instanceBalanceBefore + premiumFees
