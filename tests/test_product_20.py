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
    DIP
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


def test_premium_payment(
    instance,
    instanceService,
    instanceOperator,
    instanceWallet,
    productOwner,
    investor,
    theOutsider,
    product20,
    riskpool20,
    riskpoolWallet,
    usd1: USD1,
    usd2: USD2,
):
    tf = 10**usd2.decimals()
    max_protected_balance = 10000
    bundle_funding = (max_protected_balance * 2) / 5
    bundle_amount = bundle_funding * tf

    bundle_id = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool20,
        maxProtectedBalance = max_protected_balance,
        funding = bundle_funding)

    # policy application setup
    duration_days = 30
    protected_balance = 5000
    (premium, net_premium, protected_amount, sum_insured, duration) = calculate_premium(protected_balance, duration_days, bundle_id, product20, riskpool20, usd2)

    # setup with correct balance and allowance
    usd2.transfer(theOutsider, premium, {'from': instanceOperator})
    usd2.approve(instance.getTreasury(), premium, {'from': theOutsider})

    # check actual account balances before 
    assert usd2.balanceOf(theOutsider) == premium
    assert usd2.balanceOf(instanceWallet) == 0
    assert usd2.balanceOf(riskpoolWallet) == bundle_amount

    tx = product20.applyForPolicyWithBundle(
        theOutsider,
        protected_amount,
        duration,
        bundle_id, 
        {'from': theOutsider})

    # check account balances after 
    assert usd2.balanceOf(theOutsider) == 0
    assert usd2.balanceOf(instanceWallet) == premium - net_premium
    assert usd2.balanceOf(riskpoolWallet) == bundle_amount + net_premium

    # check policy book keeping
    assert 'LogDepegPolicyCreated' in tx.events

    process_id = tx.events['LogDepegPolicyCreated']['processId']
    policy = instanceService.getPolicy(process_id).dict()
    assert policy['premiumExpectedAmount'] == premium
    assert policy['premiumPaidAmount'] == policy['premiumExpectedAmount']

    # check bundle book keeping
    bundle = instanceService.getBundle(bundle_id).dict()
    assert bundle['capital'] == bundle_amount
    assert bundle['balance'] == bundle_amount + net_premium
    assert bundle['lockedCapital'] == sum_insured


def test_create_policy_bad_balance_or_allowance(
    instance,
    instanceService,
    instanceOperator,
    instanceWallet,
    productOwner,
    investor,
    theOutsider,
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

    # policy application setup
    duration_days = 30
    protected_balance = 5000
    (premium, net_premium, protected_amount, sum_insured, duration) = calculate_premium(protected_balance, duration_days, bundle_id, product20, riskpool20, usd2)

    # set balance and allowance
    missing_from_balance = 1
    missing_from_allowance = 1

    # failure case 1: balance too small, allowance ok
    usd2.transfer(theOutsider, premium - missing_from_balance, {'from': instanceOperator})
    usd2.approve(instance.getTreasury(), premium, {'from': theOutsider})

    with brownie.reverts('ERROR:DP-014:BALANCE_INSUFFICIENT'):
        product20.applyForPolicyWithBundle(
            theOutsider,
            protected_amount,
            duration,
            bundle_id, 
            {'from': theOutsider})

    # failure case 2: balance and allowance too small
    usd2.approve(instance.getTreasury(), premium - missing_from_allowance, {'from': theOutsider})

    with brownie.reverts('ERROR:DP-014:BALANCE_INSUFFICIENT'):
        product20.applyForPolicyWithBundle(
            theOutsider,
            protected_amount,
            duration,
            bundle_id, 
            {'from': theOutsider})

    # failure case 3: balance ok, allowance too small
    usd2.transfer(theOutsider, missing_from_balance, {'from': instanceOperator})

    with brownie.reverts('ERROR:DP-015:ALLOWANCE_INSUFFICIENT'):
        product20.applyForPolicyWithBundle(
            theOutsider,
            protected_amount,
            duration,
            bundle_id, 
            {'from': theOutsider})

    # ok case 1: balance ok,, allowance ok
    usd2.approve(instance.getTreasury(), premium, {'from': theOutsider})

    tx = product20.applyForPolicyWithBundle(
        theOutsider,
        protected_amount,
        duration,
        bundle_id, 
        {'from': theOutsider})

    assert 'LogDepegPolicyCreated' in tx.events


def calculate_premium(protected_balance, duration_days, bundle_id, product20, riskpool20, usd2):
    protected_amount = protected_balance * 10**usd2.decimals()
    duration = duration_days * 24 * 3600
    sum_insured = int(riskpool20.getSumInsuredPercentage() * protected_amount / 100)
    net_premium = product20.calculateNetPremium(sum_insured, duration, bundle_id)
    premium = product20.calculatePremium(net_premium)

    return (
        premium,
        net_premium,
        protected_amount,
        sum_insured,
        duration
    )


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

    # create token allowance for payouts
    max_protected_balance = 10000
    max_payout_amount = max_protected_balance
    token.approve(
        instanceService.getTreasuryAddress(), 
        max_payout_amount * tf, 
        {'from': riskpoolWallet})

    # create bundle
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

    # create depeg at 80% of target price (= 30% loss on protected funds)
    depeg_exchange_rate = 0.8
    depeg_price = int(depeg_exchange_rate * product20.getTargetPrice())
    (timestamp_trigger, timestamp_depeg) = force_product_into_depegged_state(product20, productOwner, depeg_price)

    depeg_info = product20.getDepegPriceInfo().dict()
    assert depeg_info['triggeredAt'] == timestamp_trigger
    assert depeg_info['depeggedAt'] == timestamp_depeg
    assert depeg_info['price'] == depeg_price

    # create claim from protected wallet
    tx = product20.createDepegClaim(
        process_id,
        {'from': protectedWallet})

    assert 'LogDepegClaimCreated' in tx.events

    evt = dict(tx.events['LogDepegClaimCreated'])
    claim_id = 0
    claim_amount = round((1 - depeg_exchange_rate) * protected_balance * tf)
    assert evt['claimId'] == claim_id
    assert evt['claimAmount'] == claim_amount

    # this number needs to be determined via moralis using the depeg timestamp via getDepeggedAt()
    depeg_block_number = 1000
    depeg_block_number_comment = "block number for timsteamp xyz"

    tx = product20.setDepeggedBlockNumber(
        depeg_block_number,
        depeg_block_number_comment,
        {'from': productOwner})

    # inject balance data for depegged time for protected wallet
    wallet_balance = protected_token.balanceOf(protectedWallet)
    depeg_balance = product20.createDepegBalance(
        protectedWallet,
        depeg_block_number,
        wallet_balance)

    # only product owner can do this
    tx = product20.addDepegBalances(
        [depeg_balance],
        {'from': productOwner})

    # check product claim amaount calculation
    payout_id = 0
    target_price = product20.getTargetPrice()
    payout_amount_expected = int(wallet_balance * (target_price - depeg_price) / target_price)

    assert product20.calculateClaimAmount(wallet_balance) == payout_amount_expected

    # record customer usdt balance before payout
    customer_usdt_blanace_before = usd2.balanceOf(customer)

    # process payout
    assert product20.getProcessedBalance(protectedWallet) == 0
    # anybody can do this (and has to pay tx fees)
    tx = product20.processPolicies([process_id])
    assert product20.getProcessedBalance(protectedWallet) == wallet_balance

    # check payout log
    assert 'LogPayoutCreated' in tx.events
    assert tx.events['LogPayoutCreated']['processId'] == process_id
    assert tx.events['LogPayoutCreated']['claimId'] == claim_id
    assert tx.events['LogPayoutCreated']['payoutId'] == payout_id
    assert tx.events['LogPayoutCreated']['amount'] == payout_amount_expected

    # check payout book keeping
    payout = instanceService.getPayout(process_id, payout_id).dict()
    assert payout['claimId'] == claim_id
    assert payout['state'] == 1
    assert payout['amount'] == payout_amount_expected

    # check actual payout in usdt token
    assert usd2.balanceOf(customer) == customer_usdt_blanace_before + payout_amount_expected


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

    # create token allowance for payouts
    max_protected_balance = 10000
    max_payout_amount = max_protected_balance
    token.approve(
        instanceService.getTreasuryAddress(), 
        max_payout_amount * tf, 
        {'from': riskpoolWallet})

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

    # create depeg at 50% of target price (= 50% loss on protected funds)
    depeg_exchange_rate = 0.5
    depeg_price = int(depeg_exchange_rate * product20.getTargetPrice())
    (timestamp_trigger, timestamp_depeg) = force_product_into_depegged_state(product20, productOwner, depeg_price)

    depeg_info = product20.getDepegPriceInfo().dict()
    assert depeg_info['triggeredAt'] == timestamp_trigger
    assert depeg_info['depeggedAt'] == timestamp_depeg
    assert depeg_info['price'] == depeg_price

    # create claim from protected wallet
    tx = product20.createDepegClaim(
        process_id,
        {'from': protectedWallet})

    assert 'LogDepegClaimCreated' in tx.events

    evt = dict(tx.events['LogDepegClaimCreated'])
    claim_id = 0
    claim_amount = min(round((1 - 0.8) * protected_balance * tf), round((1 - depeg_exchange_rate) * protected_balance * tf))
    assert claim_amount == product20.calculateClaimAmount(protected_balance * tf)
    assert evt['claimId'] == claim_id
    assert evt['claimAmount'] == claim_amount

    # this number needs to be determined via moralis using the depeg timestamp via getDepeggedAt()
    depeg_block_number = 1000
    depeg_block_number_comment = "block number for timsteamp xyz"

    tx = product20.setDepeggedBlockNumber(
        depeg_block_number,
        depeg_block_number_comment,
        {'from': productOwner})

    # inject balance data for depegged time for protected wallet
    wallet_balance = protected_token.balanceOf(protectedWallet)
    depeg_balance = product20.createDepegBalance(
        protectedWallet,
        depeg_block_number,
        wallet_balance)

    # only product owner can do this
    tx = product20.addDepegBalances(
        [depeg_balance],
        {'from': productOwner})

    # check product claim amaount calculation
    payout_id = 0
    target_price = product20.getTargetPrice()
    payout_amount_expected = product20.calculateClaimAmount(wallet_balance)

    # record customer usdt balance before payout
    customer_usdt_blanace_before = usd2.balanceOf(customer)

    # process payout
    assert product20.getProcessedBalance(protectedWallet) == 0
    # anybody can do this (and has to pay tx fees)
    tx = product20.processPolicies([process_id])
    assert product20.getProcessedBalance(protectedWallet) == wallet_balance

    # check payout log
    assert 'LogPayoutCreated' in tx.events
    assert tx.events['LogPayoutCreated']['processId'] == process_id
    assert tx.events['LogPayoutCreated']['claimId'] == claim_id
    assert tx.events['LogPayoutCreated']['payoutId'] == payout_id
    assert tx.events['LogPayoutCreated']['amount'] == payout_amount_expected

    # check payout book keeping
    payout = instanceService.getPayout(process_id, payout_id).dict()
    assert payout['claimId'] == claim_id
    assert payout['state'] == 1
    assert payout['amount'] == payout_amount_expected

    # check actual payout in usdt token
    assert usd2.balanceOf(customer) == customer_usdt_blanace_before + payout_amount_expected


def force_product_into_depegged_state(product, productOwner, depeg_price):

    timestamp_trigger = force_product_into_triggered_state(product, productOwner)

    # check pre-conditions (product is triggered now)
    assert product.getTriggeredAt() == timestamp_trigger
    assert product.getDepeggedAt() == 0
    assert product.getDepegState() == STATE_PRODUCT['Paused']

    # obtain data provider contract from product
    data_provider = get_data_provider(product)

    # move into depegged state by staying triggered for > 24h
    # set price usdc to 0.91 cents
    depeg_data = generate_next_data(
        6,
        price = depeg_price,
        last_update = timestamp_trigger,
        delta_time = 24 * 3600 + 1)

    (round_id, price, timestamp) = depeg_data.split()[:3]
    timestamp = int(timestamp)
    timestamp_depeg = timestamp

    tx = inject_and_process_data(product, data_provider, depeg_data, productOwner)

    assert product.getTriggeredAt() == timestamp_trigger
    assert product.getDepeggedAt() == timestamp_depeg
    assert product.getDepegState() == STATE_PRODUCT['Depegged']

    return (timestamp_trigger, timestamp_depeg)


def force_product_into_triggered_state(product, productOwner):

    # check pre conditions (product is active)
    assert product.getTriggeredAt() == 0
    assert product.getDepeggedAt() == 0
    assert product.getDepegState() == STATE_PRODUCT['Active']

    # obtain data provider contract from product
    data_provider = get_data_provider(product)

    # inject some initial price data
    for i in range(5):
        inject_and_process_data(product, data_provider, generate_next_data(i), productOwner)

    # check we're still good
    assert product.getTriggeredAt() == 0
    assert product.getDepeggedAt() == 0
    assert product.getDepegState() == STATE_PRODUCT['Active']

    # move into triggered (paused) state
    trigger_data = generate_next_data(
        5,
        price = TRIGGER_PRICE,
        delta_time = 12 * 3600)

    (round_id, price, timestamp) = trigger_data.split()[:3]
    timestamp = int(timestamp)
    timestamp_trigger = timestamp

    tx = inject_and_process_data(product, data_provider, trigger_data, productOwner)

    assert product.getTriggeredAt() == timestamp_trigger
    assert product.getDepeggedAt() == 0
    assert product.getDepegState() == STATE_PRODUCT['Paused']

    return timestamp_trigger


def get_data_provider(product):
    return contract_from_address(
        UsdcPriceDataProvider,
        product.getPriceDataProvider())
