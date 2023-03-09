import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    interface,
)

from scripts.util import b2s

from scripts.depeg_product import (
    GifDepegProduct,
    GifDepegRiskpool,
)

from scripts.setup import create_bundle

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


def test_create_whitelisting_story(
    instance,
    instanceService,
    instanceOperator,
    investor,
    riskpool,
    riskpoolKeeper
):
    instanceWallet = instanceService.getInstanceWallet()
    riskpoolWallet = instanceService.getRiskpoolWallet(riskpool.getId())
    tokenAddress = instanceService.getComponentToken(riskpool.getId())
    token = interface.IERC20(tokenAddress)

    bundle_funding = 100000

    bundle_name1 = 'my bundle 1'
    bundleLifetimeDays = 90
    minSumInsured =  1000
    maxSumInsured = 10000
    minDurationDays = 14
    maxDurationDays = 60
    aprPercentage = 5.0

    assert riskpool.isAllowAllAccountsEnabled() is True
    assert riskpool.isAllowed(investor) is True

    # check bundle creation works per default (whitelisting disabled)
    bundle_id1 = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool, 
        bundle_funding, 
        bundle_name1,
        bundleLifetimeDays,
        minSumInsured, 
        maxSumInsured, 
        minDurationDays, 
        maxDurationDays, 
        aprPercentage)

    # attempt to enable whitelisting
    with brownie.reverts('Ownable: caller is not the owner'):
        riskpool.setAllowAllAccounts(False, {'from': investor})
    
    assert riskpool.isAllowAllAccountsEnabled() is True

    # riskpool owner enables whitelisting
    riskpool.setAllowAllAccounts(False, {'from': riskpoolKeeper})

    assert riskpool.isAllowAllAccountsEnabled() is False
    assert riskpool.isAllowed(investor) is False

    # check that bundle creation no longer works for non-whitelistened accounts (initially all of them)
    with brownie.reverts('ERROR:DRP-001:ACCOUNT_NOT_ALLOWED_FOR_BUNDLE_CREATION'):
        create_bundle(
            instance, 
            instanceOperator, 
            investor, 
            riskpool, 
            bundle_funding, 
            bundle_name1,
            bundleLifetimeDays,
            minSumInsured, 
            maxSumInsured, 
            minDurationDays, 
            maxDurationDays, 
            aprPercentage)

    # investor attempts to whitelist herself
    with brownie.reverts('Ownable: caller is not the owner'):
        riskpool.setAllowAccount(investor, True, {'from': investor})

    assert riskpool.isAllowed(investor) is False

    # whitelisting by riskpool owner
    riskpool.setAllowAccount(investor, True, {'from': riskpoolKeeper})

    assert riskpool.isAllowed(investor) is True

    # check that bundle creation works again for investor
    bundle_name2 = 'my bundle 2'
    bundle_id2 = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool, 
        bundle_funding, 
        bundle_name2,
        bundleLifetimeDays,
        minSumInsured, 
        maxSumInsured, 
        minDurationDays, 
        maxDurationDays, 
        aprPercentage)

    # remove whitelisting of investor
    riskpool.setAllowAccount(investor, False, {'from': riskpoolKeeper})

    assert riskpool.isAllowed(investor) is False

    # check that investor is no longer allowed to create bundle
    with brownie.reverts('ERROR:DRP-001:ACCOUNT_NOT_ALLOWED_FOR_BUNDLE_CREATION'):
        create_bundle(
            instance, 
            instanceOperator, 
            investor, 
            riskpool, 
            bundle_funding, 
            bundle_name2,
            bundleLifetimeDays,
            minSumInsured, 
            maxSumInsured, 
            minDurationDays, 
            maxDurationDays, 
            aprPercentage)

    # riskpool owner disables whitelisting
    riskpool.setAllowAllAccounts(True, {'from': riskpoolKeeper})

    assert riskpool.isAllowAllAccountsEnabled() is True
    assert riskpool.isAllowed(investor) is True

    # check that bundle creation works again for investor
    bundle_name3 = 'my bundle 3'
    bundle_id3 = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool, 
        bundle_funding, 
        bundle_name3,
        bundleLifetimeDays,
        minSumInsured, 
        maxSumInsured, 
        minDurationDays, 
        maxDurationDays, 
        aprPercentage)

    # sanity check for the 3 bundles created
    assert riskpool.getBundleInfo(bundle_id1).dict()['name'] == bundle_name1
    assert riskpool.getBundleInfo(bundle_id2).dict()['name'] == bundle_name2
    assert riskpool.getBundleInfo(bundle_id3).dict()['name'] == bundle_name3
