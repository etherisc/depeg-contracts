import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    chain,
    history,
    interface,
    UsdcPriceDataProvider,
    USD1,
    USD2,
    DIP,
    DepegDistribution
)

from scripts.util import (
    b2s,
    contract_from_address
)
from scripts.depeg_product import (
    GifDepegProduct,
    GifDepegRiskpool,
)

from scripts.deploy_depeg import get_setup

from scripts.price_data import (
    STATE_PRODUCT,
    PERFECT_PRICE,
    TRIGGER_PRICE,
    # RECOVERY_PRICE,
    inject_and_process_data,
    generate_next_data,
)

from scripts.setup import (
    create_bundle, 
    apply_for_policy_with_bundle,
)

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


def test_deploy_distributor(
    product20,
    riskpool20,
    productOwner,
    distributor,
    theOutsider,
    usd1: USD1,
    usd2: USD2,
):
    distribution = _deploy_distribution(product20, riskpool20, productOwner)

    assert distribution.owner() == productOwner
    assert distribution.getToken() == product20.getToken()
    assert distribution.getToken() == usd2

    assert distribution.distributors() == 0
    assert not distribution.isDistributor(distributor)
    assert distribution.getCommissionRate(distributor) == 0
    assert distribution.getCommissionBalance(distributor) == 0
    assert distribution.getPoliciesSold(distributor) == 0

    assert not distribution.isDistributor(theOutsider)


def test_sell_policy_trough_distributor(
    instance,
    instanceService,
    instanceOperator,
    instanceWallet,
    productOwner,
    investor,
    customer,
    protectedWallet,
    product20,
    riskpool20,
    riskpoolWallet,
    usd1: USD1,
    usd2: USD2,
):
    tf = 10**usd2.decimals()
    max_protected_balance = 10000
    bundle_funding = (max_protected_balance * 2) / 5
    bundle_id = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool20,
        maxProtectedBalance = max_protected_balance,
        funding = bundle_funding)

    # setup up wallet to protect with some coins
    protected_balance = 5000
    usd1.transfer(protectedWallet, protected_balance * tf, {'from': instanceOperator})

    # buy policy for wallet to be protected
    duration_days = 60
    max_premium = 100

    process_id = apply_for_policy_with_bundle(
        instance,
        instanceOperator,
        product20,
        customer,
        bundle_id,
        protectedWallet,
        protected_balance,
        duration_days,
        max_premium)

    protected_amount = protected_balance * tf
    sum_insured_amount = protected_amount / 5
    net_premium_amount = product20.calculateNetPremium(sum_insured_amount, duration_days * 24 * 3600, bundle_id)
    premium_amount = product20.calculatePremium(net_premium_amount)

    # check application event data
    events = history[-1].events
    app_evt = dict(events['LogDepegApplicationCreated'])
    assert app_evt['protectedBalance'] == protected_amount
    assert app_evt['sumInsuredAmount'] == sum_insured_amount
    assert app_evt['premiumAmount'] == premium_amount

    # check application data
    application = instanceService.getApplication(process_id).dict()
    application_data = riskpool20.decodeApplicationParameterFromData(application['data']).dict()

    assert application['sumInsuredAmount'] == riskpool20.calculateSumInsured(protected_balance * tf)
    assert application['sumInsuredAmount'] == sum_insured_amount
    assert application_data['protectedBalance'] == protected_amount

    # check policy
    policy = instanceService.getPolicy(process_id).dict()

    assert policy['premiumExpectedAmount'] == premium_amount
    assert policy['premiumPaidAmount'] == premium_amount
    assert policy['payoutMaxAmount'] == sum_insured_amount
    assert policy['payoutAmount'] == 0

    # check bundle data
    bundle = instanceService.getBundle(bundle_id).dict()
    funding_amount = bundle_funding * tf

    assert bundle['balance'] == funding_amount + net_premium_amount
    assert bundle['capital'] == funding_amount
    assert bundle['lockedCapital'] == sum_insured_amount

    # check riskpool numbers
    assert riskpool20.getBalance() == bundle['balance']
    assert riskpool20.getTotalValueLocked() == sum_insured_amount
    assert riskpool20.getCapacity() == funding_amount - sum_insured_amount

    # check riskpool wallet
    assert usd2.balanceOf(riskpoolWallet) == riskpool20.getBalance()


def _deploy_distribution(
    product,
    riskpool,
    productOwner,
):
    return DepegDistribution.deploy(
        product,
        riskpool,
        product.getId(),
        {'from': productOwner})
