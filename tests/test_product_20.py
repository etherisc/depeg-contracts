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
)

from scripts.util import b2s
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

def test_product_sandbox(
    instance,
    instanceOperator: Account,
    gifDepegProduct20: GifDepegProduct,
    productOwner: Account,
    riskpoolKeeper: Account,
    riskpoolWallet: Account,
    investor: Account,
    customer: Account,
):
    product20 = gifDepegProduct20.getContract()

    (
        setup_before,
        product,
        feeder,
        riskpool,
        usdt,
        instance_service
    ) = get_setup(product20)

    max_protected_balance = 10000
    bundle_funding = (max_protected_balance * 2) / 5

    bundle_id = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool,
        bundleName = 'bundle-1',
        maxProtectedBalance = max_protected_balance,
        funding = bundle_funding)
    
    bundle = instance_service.getBundle(bundle_id).dict()
    bundle_filter = riskpool.decodeBundleParamsFromFilter(bundle['filter']).dict()

    # buy policy for wallet to be protected
    protected_wallet = customer
    protected_balance = 5000
    duration_days = 60
    max_premium = 100

    process_id = apply_for_policy_with_bundle(
        instance,
        instanceOperator,
        product,
        customer,
        bundle_id,
        protected_wallet,
        protected_balance,
        duration_days,
        max_premium)

    metadata = instance_service.getMetadata(process_id).dict()
    application = instance_service.getApplication(process_id).dict()
    application_data = riskpool.decodeApplicationParameterFromData(application['data']).dict()
    policy = instance_service.getPolicy(process_id).dict()      

    (
        setup,
        product,
        feeder,
        riskpool,
        usdt,
        instance_service
    ) = get_setup(product20)

    # to use sandboxr:
    # - uncomment 'assert False' below
    # - run brownie command below
    # brownie test tests/test_product_20.py::test_product_sandbox --interactive

    # assert False


def test_product_20_deploy(
    instanceService,
    instanceOperator,
    productOwner,
    riskpoolKeeper,
    usdc_feeder,
    product20,
    riskpool20,
    riskpoolWallet: Account,
    usd1: USD1,
    usd2: USD2,
):
    # check role assignements
    poRole = instanceService.getProductOwnerRole()
    rkRole = instanceService.getRiskpoolKeeperRole()

    assert instanceService.getInstanceOperator() == instanceOperator
    assert instanceService.hasRole(poRole, productOwner)
    assert instanceService.hasRole(rkRole, riskpoolKeeper)

    # check deployed product, oracle
    assert instanceService.products() == 1
    assert instanceService.oracles() == 0
    assert instanceService.riskpools() == 1

    assert instanceService.getComponent(product20.getId()) == product20
    assert instanceService.getComponent(riskpool20.getId()) == riskpool20 

    # check token
    assert usdc_feeder.getToken() == usd1
    assert usd1.symbol() == 'USDC'
    assert usd2.symbol() == 'USDT'

    # check product
    assert product20.getPriceDataProvider() == usdc_feeder
    assert product20.getProtectedToken() == usd1 # usdc
    assert product20.getToken() == usd2 # usdt
    assert product20.getRiskpoolId() == riskpool20.getId()

    # check riskpool
    assert riskpool20.getWallet() == riskpoolWallet
    assert riskpool20.getErc20Token() == usd2 # usdt

    # sum insured % checks
    percentage = 20
    target_price = product20.getTargetPrice()
    protected_price = ((100 - percentage) * target_price) / 100
    protected_balance = 5000 * 10 ** usd1.decimals()
    sum_insured = (percentage * protected_balance) / 100

    assert target_price == 10 ** usdc_feeder.decimals()
    assert protected_balance == 5 * sum_insured
    assert protected_price == 0.8 * target_price

    assert riskpool20.getSumInsuredPercentage() == percentage
    assert riskpool20.calculateSumInsured(protected_balance) == sum_insured
    assert riskpool20.getProtectedMinDepegPrice(target_price) == protected_price

    assert riskpool20.depegPriceIsBelowProtectedDepegPrice(protected_price + 1, target_price) is False
    assert riskpool20.depegPriceIsBelowProtectedDepegPrice(protected_price + 0, target_price) is False
    assert riskpool20.depegPriceIsBelowProtectedDepegPrice(protected_price - 1, target_price) is True
    assert riskpool20.depegPriceIsBelowProtectedDepegPrice(protected_price / 2, target_price) is True


def test_product_20_create_policy(
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
    usd2: USD2,
):
    protected_token_address = product20.getProtectedToken()
    protected_token = interface.IERC20Metadata(protected_token_address)
    tf = 10 ** protected_token.decimals()

    riskpool_id = riskpool20.getId()
    token_address = instanceService.getComponentToken(riskpool_id)
    token = interface.IERC20Metadata(token_address)

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
    protected_token.transfer(protectedWallet, protected_balance * tf, {'from': instanceOperator})

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
    assert app_evt['netPremiumAmount'] == net_premium_amount

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


def test_product_20_depeg_normal(
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
    usd2: USD2,
):
    protected_token_address = product20.getProtectedToken()
    protected_token = interface.IERC20Metadata(protected_token_address)
    tf = 10 ** protected_token.decimals()

    riskpool_id = riskpool20.getId()
    token_address = instanceService.getComponentToken(riskpool_id)
    token = interface.IERC20Metadata(token_address)

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
    protected_token.transfer(protectedWallet, protected_balance * tf, {'from': instanceOperator})

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

    # TODO continue here
    # - create depeg normal (depeg price == 0.8)
    # - create claim/payout
    # - check full payout


def test_product_20_depeg_below_80(
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
    usd2: USD2,
):
    protected_token_address = product20.getProtectedToken()
    protected_token = interface.IERC20Metadata(protected_token_address)
    tf = 10 ** protected_token.decimals()

    riskpool_id = riskpool20.getId()
    token_address = instanceService.getComponentToken(riskpool_id)
    token = interface.IERC20Metadata(token_address)

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
    protected_token.transfer(protectedWallet, protected_balance * tf, {'from': instanceOperator})

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

    # TODO continue here
    # - create depeg ouside sum insured (depeg price < 0.8)
    # - create claim/payout
    # - check capped payout
