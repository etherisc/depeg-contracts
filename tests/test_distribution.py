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

COMMISSION_RATE_DEFAULT = 0.05
COMMISSION_RATE_MAX = 0.33
COMMISSION_TOLERANCE = 10 ** -9

def test_deploy_distribution(
    product20,
    riskpool20,
    productOwner,
    distributor,
    theOutsider,
    usd1: USD1,
    usd2: USD2,
):
    distribution = _deploy_distribution(product20, productOwner)

    assert distribution.owner() == productOwner
    assert distribution.getToken() == product20.getToken()
    assert distribution.getToken() == usd2

    assert distribution.COMMISSION_RATE_DEFAULT() / 10**distribution.DECIMALS() == COMMISSION_RATE_DEFAULT
    assert distribution.COMMISSION_RATE_MAX() / 10 ** distribution.DECIMALS() == COMMISSION_RATE_MAX

    assert distribution.distributors() == 0
    assert not distribution.isDistributor(distributor)
    assert distribution.getCommissionRate(distributor) == 0
    assert distribution.getCommissionBalance(distributor) == 0
    assert distribution.getPoliciesSold(distributor) == 0

    assert not distribution.isDistributor(theOutsider)


def test_create_distributor_happy_case(
    product20,
    riskpool20,
    productOwner,
    distributor,
    theOutsider,
    usd1: USD1,
    usd2: USD2,
):
    distribution = _deploy_distribution(product20, productOwner)
    distribution.createDistributor(distributor, {'from': productOwner})

    assert distribution.distributors() == 1
    assert distribution.isDistributor(distributor)
    assert distribution.getCommissionRate(distributor) > 0
    assert distribution.getCommissionRate(distributor) == distribution.COMMISSION_RATE_DEFAULT()
    assert distribution.getCommissionBalance(distributor) == 0
    assert distribution.getPoliciesSold(distributor) == 0

    net_premium_100 = 100 * 10 ** usd2.decimals()
    commission = distribution.calculateCommission(distributor, net_premium_100)
    full_premium = net_premium_100 + commission

    commission_rate = distribution.getCommissionRate(distributor)
    assert commission == full_premium * commission_rate / 10 ** distribution.DECIMALS()

    assert not distribution.isDistributor(theOutsider)


def test_set_commission_rate_happy_case(
    product20,
    productOwner,
    distributor,
):
    distribution = _deploy_distribution(product20, productOwner)
    distribution.createDistributor(distributor, {'from': productOwner})

    # check initial setting
    assert distribution.getCommissionRate(distributor) == distribution.COMMISSION_RATE_DEFAULT()

    # set to higher rate
    commission_rate_new = 12 * 10 ** (distribution.DECIMALS() - 2);
    distribution.setCommissionRate(distributor, commission_rate_new, {'from': productOwner})

    assert commission_rate_new > distribution.COMMISSION_RATE_DEFAULT()
    assert distribution.getCommissionRate(distributor) == commission_rate_new

    # set to max rate
    distribution.setCommissionRate(distributor, distribution.COMMISSION_RATE_MAX(), {'from': productOwner})

    assert distribution.getCommissionRate(distributor) == distribution.COMMISSION_RATE_MAX()

    # set rate to zero
    commission_rate_zero = 0;
    distribution.setCommissionRate(distributor, commission_rate_zero, {'from': productOwner})

    assert distribution.getCommissionRate(distributor) == commission_rate_zero


def test_set_commission_rate_too_high(
    product20,
    productOwner,
    distributor,
):
    distribution = _deploy_distribution(product20, productOwner)
    distribution.createDistributor(distributor, {'from': productOwner})

    # check initial setting
    assert distribution.getCommissionRate(distributor) == distribution.COMMISSION_RATE_DEFAULT()

    # set to higher rate
    commission_rate_too_high = distribution.COMMISSION_RATE_MAX() + 1
    with brownie.reverts("ERROR:DST-031:COMMISSION_RATE_TOO_HIGH"):
        distribution.setCommissionRate(distributor, commission_rate_too_high, {'from': productOwner})


def test_set_commission_rate_authz(
    product20,
    productOwner,
    distributor,
    theOutsider
):
    distribution = _deploy_distribution(product20, productOwner)
    distribution.createDistributor(distributor, {'from': productOwner})

    # set to new rate
    new_rate = 12 * 10 ** (distribution.DECIMALS() - 2);

    # attempt to set rate by distributor itself
    with brownie.reverts("Ownable: caller is not the owner"):
        distribution.setCommissionRate(distributor, new_rate, {'from': distributor})

    # attempt to set rate by outsider
    with brownie.reverts("Ownable: caller is not the owner"):
        distribution.setCommissionRate(distributor, new_rate, {'from': theOutsider})


def test_create_distributor_authz(
    product20,
    riskpool20,
    productOwner,
    distributor,
    theOutsider,
    usd1: USD1,
    usd2: USD2,
):
    distribution = _deploy_distribution(product20, productOwner)

    # attempt to self create distributor
    with brownie.reverts('Ownable: caller is not the owner'):
        distribution.createDistributor(distributor, {'from': distributor})


def test_sell_policy_trough_distributor(
    instance,
    instanceService,
    instanceOperator,
    instanceWallet,
    productOwner,
    distributor,
    investor,
    customer,
    protectedWallet,
    product20,
    riskpool20,
    riskpoolWallet,
    usd1: USD1,
    usd2: USD2,
):
    distribution = _deploy_distribution(product20, productOwner)
    distribution.createDistributor(distributor, {'from': productOwner})

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
    protected_balance = 5000 * tf
    usd1.transfer(protectedWallet, protected_balance, {'from': instanceOperator})

    # buy policy for wallet to be protected
    duration_days = 60
    max_premium = 100
    duration_seconds = duration_days * 24 * 3600

    (
        total_premium,
        commission
    ) = distribution.calculatePrice(
        distributor,
        protected_balance,
        duration_seconds,
        bundle_id
    )

    # fund customer
    usd2.transfer(customer, total_premium, {'from': instanceOperator})
    usd2.approve(distribution, total_premium, {'from': customer})

    assert usd2.balanceOf(customer) == total_premium
    assert usd2.balanceOf(distribution) == 0

    # check distributor book keeping (before policy sale)
    assert distribution.getCommissionBalance(distributor) == 0
    assert distribution.getPoliciesSold(distributor) == 0

    tx = distribution.createPolicy(
        customer,
        protectedWallet,
        protected_balance,
        duration_seconds,
        bundle_id,
        {'from': distributor})

    process_id = tx.events['LogApplicationCreated']['processId']

    assert usd2.balanceOf(customer) == 0
    assert usd2.balanceOf(distribution) == commission

    # check owner of policy is distribution contract
    # customer from above is only used to pull premium
    meta_data = instanceService.getMetadata(process_id).dict()
    assert meta_data['owner'] != customer
    assert meta_data['owner'] == distribution

    # check distributor book keeping (after policy sale)
    assert distribution.getCommissionBalance(distributor) == commission
    assert distribution.getPoliciesSold(distributor) == 1

    # check that all other policy properties match the direct sale setup
    # see test_product_20.py::test_product_20_create_policy
    protected_amount = protected_balance
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

    assert application['sumInsuredAmount'] == riskpool20.calculateSumInsured(protected_amount)
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


def test_withdrawal_distributor_happy_case(
    instance,
    instanceService,
    instanceOperator,
    instanceWallet,
    productOwner,
    distributor,
    investor,
    customer,
    protectedWallet,
    product20,
    riskpool20,
    riskpoolWallet,
    usd1: USD1,
    usd2: USD2,
):
    (
        distribution,
        commission
    ) = _createCommisssionSetup(
        instance,
        instanceService,
        instanceOperator,
        instanceWallet,
        productOwner,
        distributor,
        investor,
        customer,
        protectedWallet,
        product20,
        riskpool20,
        riskpoolWallet,
        usd1,
        usd2
    )

    assert usd2.balanceOf(distributor) == 0
    assert usd2.balanceOf(distribution) == commission

    withdrawal_amount = 100000
    remaining_commission = commission - withdrawal_amount
    tx = distribution.withdrawCommission(withdrawal_amount, {'from': distributor})

    # check updated book keeping
    assert distribution.getCommissionBalance(distributor) == remaining_commission

    # check actual token balances
    assert usd2.balanceOf(distributor) == withdrawal_amount
    assert usd2.balanceOf(distribution) == remaining_commission


def test_withdrawal_distributor_amount_too_big(
    instance,
    instanceService,
    instanceOperator,
    instanceWallet,
    productOwner,
    distributor,
    investor,
    customer,
    protectedWallet,
    product20,
    riskpool20,
    riskpoolWallet,
    usd1: USD1,
    usd2: USD2,
):
    (
        distribution,
        commission
    ) = _createCommisssionSetup(
        instance,
        instanceService,
        instanceOperator,
        instanceWallet,
        productOwner,
        distributor,
        investor,
        customer,
        protectedWallet,
        product20,
        riskpool20,
        riskpoolWallet,
        usd1,
        usd2
    )

    assert usd2.balanceOf(distributor) == 0
    assert usd2.balanceOf(distribution) == commission

    # amount larger than accumulated commission
    with brownie.reverts("ERROR:DST-050:AMOUNT_TOO_LARGE"):
        distribution.withdrawCommission(commission + 1, {'from': distributor})

    # reduce commission balance of distribution contract
    distribution.withdraw(commission - 1000, {'from': productOwner})

    # amount smaller accumulated commission
    with brownie.reverts("ERROR:DST-051:BALANCE_INSUFFICIENT"):
        distribution.withdrawCommission(commission - 1, {'from': distributor})


def test_withdrawal_not_distributor(
    instance,
    instanceService,
    instanceOperator,
    instanceWallet,
    productOwner,
    distributor,
    investor,
    customer,
    theOutsider,
    protectedWallet,
    product20,
    riskpool20,
    riskpoolWallet,
    usd1: USD1,
    usd2: USD2,
):
    (
        distribution,
        commission
    ) = _createCommisssionSetup(
        instance,
        instanceService,
        instanceOperator,
        instanceWallet,
        productOwner,
        distributor,
        investor,
        customer,
        protectedWallet,
        product20,
        riskpool20,
        riskpoolWallet,
        usd1,
        usd2
    )

    assert usd2.balanceOf(distributor) == 0
    assert usd2.balanceOf(distribution) == commission

    with brownie.reverts("ERROR:DST-001:NOT_DISTRIBUTOR"):
        distribution.withdrawCommission(commission + 1, {'from': productOwner})

    with brownie.reverts("ERROR:DST-001:NOT_DISTRIBUTOR"):
        distribution.withdrawCommission(commission + 1, {'from': theOutsider})

    # now, make the outsider to distributor - but not the one that owns the one with the commission
    distribution.createDistributor(theOutsider, {'from': productOwner})

    # amount larger than accumulated commission
    with brownie.reverts("ERROR:DST-050:AMOUNT_TOO_LARGE"):
        distribution.withdrawCommission(commission + 1, {'from': theOutsider})


def test_withdrawal_owner_happy_case(
    productOwner,
    instanceOperator,
    product20,
    usd2: USD2,
):
    distribution = _deploy_distribution(product20, productOwner)

    some_amount = 1000 * 10 ** usd2.decimals()
    usd2.transfer(distribution, some_amount, {'from': instanceOperator})

    # check balances before withdrawal
    assert usd2.balanceOf(distribution) == some_amount
    assert usd2.balanceOf(productOwner) == 0

    other_amount = 200 * 10 ** usd2.decimals()
    distribution.withdraw(other_amount, {'from': productOwner})

    # check balances after withdrawal
    assert usd2.balanceOf(distribution) == some_amount - other_amount
    assert usd2.balanceOf(productOwner) == other_amount


def test_withdrawal_non_owner(
    productOwner,
    instanceOperator,
    distributor,
    theOutsider,
    product20,
    usd2: USD2,
):
    distribution = _deploy_distribution(product20, productOwner)
    distribution.createDistributor(distributor, {'from': productOwner})

    some_amount = 1000 * 10 ** usd2.decimals()
    usd2.transfer(distribution, some_amount, {'from': instanceOperator})

    # check balances before withdrawal
    assert usd2.balanceOf(distribution) == some_amount
    assert usd2.balanceOf(productOwner) == 0

    other_amount = 200 * 10 ** usd2.decimals()

    # attempt withdrawal by outsider
    with brownie.reverts("Ownable: caller is not the owner"):
        distribution.withdraw(other_amount, {'from': theOutsider})

    # attempt withdrawal by distributor
    with brownie.reverts("Ownable: caller is not the owner"):
        distribution.withdraw(other_amount, {'from': distributor})


def test_withdrawal_amount_too_big(
    productOwner,
    instanceOperator,
    product20,
    usd2: USD2,
):
    distribution = _deploy_distribution(product20, productOwner)

    some_amount = 1000 * 10 ** usd2.decimals()
    usd2.transfer(distribution, some_amount, {'from': instanceOperator})

    # check balances before withdrawal
    assert usd2.balanceOf(distribution) == some_amount
    assert usd2.balanceOf(productOwner) == 0

    # amount larger than balance
    other_amount = some_amount + 1

    # attempt withdrawal by too large amount
    with brownie.reverts("ERROR:DST-040:BALANCE_INSUFFICIENT"):
        distribution.withdraw(other_amount, {'from': productOwner})


def _createCommisssionSetup(
    instance,
    instanceService,
    instanceOperator,
    instanceWallet,
    productOwner,
    distributor,
    investor,
    customer,
    protectedWallet,
    product20,
    riskpool20,
    riskpoolWallet,
    usd1: USD1,
    usd2: USD2,
):
    distribution = _deploy_distribution(product20, productOwner)
    distribution.createDistributor(distributor, {'from': productOwner})

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
    protected_balance = 5000 * tf
    usd1.transfer(protectedWallet, protected_balance, {'from': instanceOperator})

    # buy policy for wallet to be protected
    duration_days = 60
    duration_seconds = duration_days * 24 * 3600

    (
        total_premium,
        commission
    ) = distribution.calculatePrice(
        distributor,
        protected_balance,
        duration_seconds,
        bundle_id
    )

    # fund customer
    usd2.transfer(customer, total_premium, {'from': instanceOperator})
    usd2.approve(distribution, total_premium, {'from': customer})

    tx = distribution.createPolicy(
        customer,
        protectedWallet,
        protected_balance,
        duration_seconds,
        bundle_id,
        {'from': distributor})

    return (
        distribution,
        commission
    )


def _deploy_distribution(
    product,
    productOwner,
):
    return DepegDistribution.deploy(
        product,
        product.getId(),
        {'from': productOwner})
