import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    USD1,
    USD2,
)

from scripts.depeg_product import (
    GifDepegProduct,
    GifDepegRiskpool,
)

from scripts.setup import create_bundle
from scripts.util import b2s


# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass

def test_riskpool_fixture(
    gifDepegProduct: GifDepegProduct,
    riskpoolWallet: Account,
    usd1: USD1,
    usd2: USD2,
):
    product = gifDepegProduct.getContract()
    riskpool = gifDepegProduct.getRiskpool().getContract()

    print('product {}'.format(product))
    print('riskpool {}'.format(riskpool))
    print('riskpool.getToken() {}'.format(riskpool.getErc20Token()))
    print('usd1 {}'.format(usd1))
    print('riskpoolWallet {}'.format(riskpoolWallet))

    print('product {} id {} name {}'.format(
        product,
        product.getId(),
        b2s(product.getName())
    ))

    print('riskpool {} id {} name {}'.format(
        riskpool,
        riskpool.getId(),
        b2s(riskpool.getName())
    ))


def test_riskpool_setting_caps(
    gifDepegProduct: GifDepegProduct,
    riskpoolKeeper,
    customer,
    usd2: USD2
):
    riskpool = gifDepegProduct.getRiskpool().getContract()
    pool_cap_old = riskpool.getRiskpoolCapitalCap()
    bundle_cap_old = riskpool.getBundleCapitalCap()

    assert pool_cap_old == riskpool.getSumOfSumInsuredCap()
    assert bundle_cap_old == pool_cap_old / 10

    riskpool_cap = int(riskpool.getRiskpoolCapitalCap() / 200)
    bundle_cap = int(riskpool_cap / 2)

    assert bundle_cap < riskpool_cap
    assert riskpool_cap < pool_cap_old
    assert bundle_cap < bundle_cap_old

    # check setting caps is restricted to riskpool keeper
    with brownie.reverts('Ownable: caller is not the owner'):
        riskpool.setCapitalCaps(
            riskpool_cap,
            bundle_cap,
            {'from': customer})

    tx = riskpool.setCapitalCaps(
        riskpool_cap,
        bundle_cap,
        {'from': riskpoolKeeper})

    assert 'LogRiskpoolCapitalSet' in tx.events
    assert tx.events['LogRiskpoolCapitalSet']['poolCapitalOld'] == pool_cap_old
    assert tx.events['LogRiskpoolCapitalSet']['poolCapitalNew'] == riskpool_cap
    
    assert 'LogBundleCapitalSet' in tx.events
    assert tx.events['LogBundleCapitalSet']['bundleCapitalOld'] == bundle_cap_old
    assert tx.events['LogBundleCapitalSet']['bundleCapitalNew'] == bundle_cap

    assert riskpool.getRiskpoolCapitalCap() == riskpool_cap
    assert riskpool.getBundleCapitalCap() == bundle_cap


def test_riskpool_enforcing_caps_simple(
    riskpool,
    riskpoolKeeper,
    riskpoolWallet,
    instance,
    instanceService,
    instanceOperator,
    investor,
    usd2,
):
    riskpool_cap = 10000
    bundle_cap = int(riskpool_cap / 1) - 1
    tf = 10 ** usd2.decimals()

    riskpool.setCapitalCaps(
        riskpool_cap * tf,
        bundle_cap * tf,
        {'from': riskpoolKeeper})

    # case 1: attempt to created bundle > pool cap
    with brownie.reverts('ERROR:DRP-027:RISK_CAPITAL_INVALID'):
        create_bundle(
            instance, 
            instanceOperator, 
            investor, 
            riskpool,
            maxProtectedBalance = bundle_cap - 1,
            funding = riskpool_cap + 1)

    # case 2: attempt to create bundle > bundle cap
    with brownie.reverts('ERROR:DRP-027:RISK_CAPITAL_INVALID'):
        create_bundle(
            instance, 
            instanceOperator, 
            investor, 
            riskpool,
            maxProtectedBalance = bundle_cap - 1,
            funding=riskpool_cap)

    # case 3: create bundle == bundle cap
    bundle_id = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool,
        maxProtectedBalance = bundle_cap - 1,
        funding=bundle_cap)

    bundle = instanceService.getBundle(bundle_id).dict()
    assert bundle['capital'] == bundle_cap * tf
    assert bundle['balance'] == bundle_cap * tf

    # attempt to increase bundle capital via bundle funding
    increase_amount = 10 * 10 ** usd2.decimals()

    with brownie.reverts('ERROR:DRP-100:FUNDING_EXCEEDS_BUNDLE_CAPITAL_CAP'):
        riskpool.fundBundle(
            bundle_id,
            increase_amount,
            {'from': investor})

    # check that defunding, then funding again works
    delta_amount = 5 * 10 ** usd2.decimals()

    riskpool.defundBundle(
        bundle_id,
        delta_amount,
        {'from': investor})
    assert instanceService.getBundle(bundle_id).dict()['capital'] == bundle_cap * tf - delta_amount

    # double caps and try again
    riskpool.setCapitalCaps(
        2 * riskpool_cap * tf,
        int(riskpool_cap / 3) * tf,
        {'from': riskpoolKeeper})

    with brownie.reverts('ERROR:DRP-027:RISK_CAPITAL_INVALID'):
        create_bundle(
            instance, 
            instanceOperator, 
            investor, 
            riskpool,
            maxProtectedBalance = bundle_cap - 1,
            funding=riskpool_cap * 4)