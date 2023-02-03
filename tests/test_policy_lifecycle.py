import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    chain,
    history,
    interface,
    UsdcPriceDataProvider
)

from scripts.util import (
    b2s,
    contract_from_address
)

from scripts.depeg_product import (
    GifDepegProduct,
    GifDepegRiskpool,
)

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
    apply_for_policy,
)

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass

def test_happy_path(
    instance,
    instanceService,
    instanceOperator,
    instanceWallet,
    productOwner,
    investor,
    customer,
    protectedWallet,
    product,
    riskpool,
    riskpoolWallet
):
    riskpool_id = riskpool.getId()
    instance_wallet = instanceService.getInstanceWallet()
    riskpool_wallet = instanceService.getRiskpoolWallet(riskpool_id)
    assert riskpoolWallet == riskpool_wallet

    token_address = instanceService.getComponentToken(riskpool_id)
    token = interface.IERC20Metadata(token_address)

    protected_token_address = product.getProtectedToken()
    protected_token = interface.IERC20Metadata(protected_token_address)

    # create token allowance for payouts
    max_payout_amount = 100000 * 10 ** protected_token.decimals()
    token.approve(
        instanceService.getTreasuryAddress(), 
        max_payout_amount, 
        {'from': riskpool_wallet})

    # setup riskpool with a single risk bundle
    bundle_funding = 10000 * 10 ** protected_token.decimals()
    min_sum_insured = 2000 * 10 ** protected_token.decimals()
    max_sum_insured = 10000 * 10 ** protected_token.decimals()

    assert instanceService.getBalance(riskpool_id) == 0
    assert instanceService.getCapital(riskpool_id) == 0
    assert instanceService.getTotalValueLocked(riskpool_id) == 0

    # check actual balances of riskpool, protected wallet and policy holder
    assert protected_token.balanceOf(protectedWallet) == 0
    assert token.balanceOf(instanceWallet) == 0
    assert token.balanceOf(riskpoolWallet) == 0
    assert token.balanceOf(protectedWallet) == 0
    assert token.balanceOf(customer) == 0

    bundle_id = create_bundle(
        instance,
        instanceOperator,
        investor,
        riskpool,
        funding=bundle_funding,
        minSumInsured=min_sum_insured,
        maxSumInsured=max_sum_insured)

    # check actual balances of riskpool, protected wallet and policy holder
    assert protected_token.balanceOf(protectedWallet) == 0
    assert token.balanceOf(instanceWallet) == 0 # zero fee for risk capital staking
    assert token.balanceOf(riskpoolWallet) == bundle_funding
    assert token.balanceOf(protectedWallet) == 0
    assert token.balanceOf(customer) == 0
    assert token.balanceOf(investor) == 0

    # check effect on riskpoool
    assert instanceService.getBalance(riskpool_id) == bundle_funding
    assert instanceService.getCapital(riskpool_id) == bundle_funding
    assert instanceService.getTotalValueLocked(riskpool_id) == 0

    # setup up wallet to protect with some coins
    wallet_balance = 4051 * 10 ** protected_token.decimals()
    protected_token.transfer(protectedWallet, wallet_balance, {'from': instanceOperator})
    assert wallet_balance < max_payout_amount # protection: amounts need to stay in relation to each other

    # set application parameters
    sum_insured = wallet_balance
    duration_days = 60
    max_premium = 42 * 10 ** protected_token.decimals() # might need to actually calculate this ...

    riskpool_balance_before = instanceService.getBalance(riskpool_id)
    instance_balance_before = token.balanceOf(instance_wallet)

    # check effect on riskpoool status
    assert instanceService.getBalance(riskpool_id) == bundle_funding
    assert instanceService.getCapital(riskpool_id) == bundle_funding
    assert instanceService.getTotalValueLocked(riskpool_id) == 0

    process_id = apply_for_policy(
        instance,
        instanceOperator,
        product,
        customer,
        protectedWallet,
        sum_insured,
        duration_days,
        max_premium)

    tx = history[-1]
    assert 'LogTreasuryPremiumTransferred' in tx.events
    assert 'LogTreasuryFeesTransferred' in tx.events

    net_premium = tx.events['LogTreasuryPremiumTransferred']['amount']
    premium_fee = tx.events['LogTreasuryFeesTransferred']['amount']
    assert net_premium + premium_fee == max_premium

    # check actual balances of riskpool, protected wallet and policy holder
    assert protected_token.balanceOf(protectedWallet) == wallet_balance
    assert token.balanceOf(instanceWallet) == premium_fee # some fee for premium payment
    assert token.balanceOf(riskpoolWallet) == bundle_funding + net_premium
    assert token.balanceOf(protectedWallet) == 0
    assert token.balanceOf(customer) == 0
    assert token.balanceOf(investor) == 0

    # check effect on riskpoool status
    assert instanceService.getBalance(riskpool_id) == bundle_funding + net_premium
    assert instanceService.getCapital(riskpool_id) == bundle_funding
    assert instanceService.getTotalValueLocked(riskpool_id) == sum_insured

    riskpool_balance_after = instanceService.getBalance(riskpool_id)
    instance_balance_after = token.balanceOf(instanceWallet)

    tx = history[-1]
    assert 'LogDepegApplicationCreated' in tx.events
    assert tx.events['LogDepegApplicationCreated']['processId'] == process_id
    assert tx.events['LogDepegApplicationCreated']['policyHolder'] == customer
    assert tx.events['LogDepegApplicationCreated']['protectedWallet'] == protectedWallet
    assert tx.events['LogDepegApplicationCreated']['sumInsuredAmount'] == sum_insured
    assert tx.events['LogDepegApplicationCreated']['premiumAmount'] == max_premium

    assert 'LogDepegPolicyCreated' in tx.events
    assert tx.events['LogDepegPolicyCreated']['processId'] == process_id
    assert tx.events['LogDepegPolicyCreated']['policyHolder'] == customer
    assert tx.events['LogDepegPolicyCreated']['sumInsuredAmount'] == sum_insured

    metadata = instanceService.getMetadata(process_id).dict()
    application = instanceService.getApplication(process_id).dict()
    policy = instanceService.getPolicy(process_id).dict()

    print('policy {} created'.format(process_id))
    print('metadata {}'.format(metadata))
    print('application {}'.format(application))
    print('policy {}'.format(policy))

    # check metadata
    assert metadata['owner'] == customer
    assert metadata['productId'] == product.getId()

    # check application
    assert application['premiumAmount'] == max_premium
    assert application['sumInsuredAmount'] == sum_insured

    # check policy
    assert policy['premiumExpectedAmount'] == max_premium
    assert policy['premiumPaidAmount'] == max_premium
    assert policy['payoutMaxAmount'] == sum_insured
    assert policy['payoutAmount'] == 0 # payout amount
    assert policy['claimsCount'] == 0 # claims count
    assert policy['openClaimsCount'] == 0 # open claims count

    fixed_fee = 0
    fractional_fee = 0.1
    premium_fees = fractional_fee * max_premium + fixed_fee
    net_premium = max_premium - premium_fees

    (
        wallet,
        application_duration,
        application_bundle_id,
        application_max_net_premium
    ) = riskpool.decodeApplicationParameterFromData(application['data'])

    assert wallet == protectedWallet
    assert application_duration == duration_days * 24 * 3600
    assert application_bundle_id == 0
    assert application_max_net_premium == net_premium

    # check wallet balances against premium payment
    assert riskpool_balance_after == riskpool_balance_before + net_premium
    assert instance_balance_after == instance_balance_before + premium_fees

    # create depeg situation
    assert product.getDepegState() == STATE_PRODUCT['Active']
    depeg_price = int(0.91 * product.getTargetPrice())
    (timestamp_trigger, timestamp_depeg) = force_product_into_depegged_state(product, productOwner, depeg_price)

    # verify product is depegged now
    assert product.getTriggeredAt() == timestamp_trigger
    assert product.getDepeggedAt() == timestamp_depeg
    assert product.getDepegState() == STATE_PRODUCT['Depegged']

    depeg_info = product.getDepegPriceInfo().dict()
    assert depeg_info['triggeredAt'] == timestamp_trigger
    assert depeg_info['depeggedAt'] == timestamp_depeg
    assert depeg_info['price'] == depeg_price

    # no policy to process so far
    assert product.policiesToProcess() == 0
    assert instanceService.claims(process_id) == 0
    assert instanceService.payouts(process_id) == 0

    # calcuate expected claim amount
    target_price = product.getTargetPrice()
    claim_amount_expected = int(sum_insured * (target_price - depeg_price) / target_price)

    # check product claim amaount calculation
    assert product.calculateClaimAmount(sum_insured) == claim_amount_expected

    # create claim from protected wallet
    tx = product.createDepegClaim(
        process_id,
        {'from': protectedWallet})

    # check actual balances of riskpool, protected wallet and policy holder
    assert protected_token.balanceOf(protectedWallet) == wallet_balance
    assert token.balanceOf(instanceWallet) == premium_fee # some fee for premium payment
    assert token.balanceOf(riskpoolWallet) == bundle_funding + net_premium
    assert token.balanceOf(protectedWallet) == 0
    assert token.balanceOf(customer) == 0
    assert token.balanceOf(investor) == 0

    # check zero effect on riskpoool status
    assert instanceService.getBalance(riskpool_id) == bundle_funding + net_premium
    assert instanceService.getCapital(riskpool_id) == bundle_funding
    assert instanceService.getTotalValueLocked(riskpool_id) == sum_insured

    # verify claim details in logs
    assert 'LogDepegClaimCreated' in tx.events
    assert tx.events['LogDepegClaimCreated']['processId'] == process_id
    assert tx.events['LogDepegClaimCreated']['claimId'] == 0
    assert tx.events['LogDepegClaimCreated']['claimAmount'] == claim_amount_expected

    assert 'LogDepegPolicyExpired' in tx.events
    assert tx.events['LogDepegPolicyExpired']['processId'] == process_id

    # one policy to process now
    assert product.policiesToProcess() == 1
    (pid, wallet) = product.getPolicyToProcess(0)
    assert pid == process_id
    assert wallet == protectedWallet
    assert instanceService.claims(process_id) == 1
    assert instanceService.payouts(process_id) == 0

    # check claim data
    claim_id = 0
    claim = instanceService.getClaim(process_id, claim_id).dict()
    assert claim['claimAmount'] == claim_amount_expected
    assert claim['paidAmount'] == 0

    (claim_depeg_price, claim_depegged_at) = product.decodeClaimInfoFromData(claim['data'])
    assert claim_depeg_price == depeg_price
    assert claim_depegged_at == timestamp_depeg

    # check policy data
    policy = instanceService.getPolicy(process_id).dict()
    assert policy['state'] == 1 # enum PolicyState {Active, Expired, Closed}
    assert policy['payoutMaxAmount'] == sum_insured
    assert policy['payoutAmount'] == 0 # payout amount
    assert policy['claimsCount'] == 1 # claims count
    assert policy['openClaimsCount'] == 1 # open claims count

    # process policy
    # in this case balance of wallet at depeg time 
    # exactly matches with the amount protected for that wallet
    payout_id = 0
    depegged_at_balance = sum_insured
    payout_amount_expected = claim_amount_expected

    assert protected_token.balanceOf(protectedWallet) == depegged_at_balance
    assert token.balanceOf(protectedWallet) == 0

    # this number needs to be determined via moralis using the depeg timestamp via getDepeggedAt()
    depeg_block_number = 1000
    depeg_block_number_comment = "block number for timsteamp xyz"

    assert product.getDepeggedBlockNumber() == 0

    # needs to be protected
    tx = product.setDepeggedBlockNumber(
        depeg_block_number,
        depeg_block_number_comment,
        {'from': productOwner})

    assert 'LogDepegBlockNumberSet' in tx.events
    assert tx.events['LogDepegBlockNumberSet']['blockNumber'] == depeg_block_number
    assert tx.events['LogDepegBlockNumberSet']['comment'] == depeg_block_number_comment

    assert product.getDepeggedBlockNumber() == depeg_block_number

    # inject balance data for depegged time for protected wallet
    depeg_balance = product.createDepegBalance(
        protectedWallet,
        depeg_block_number,
        depegged_at_balance)

    # needs to be protected
    tx = product.addDepegBalances(
        [depeg_balance],
        {'from': productOwner})

    assert 'LogDepegDepegBalanceAdded' in tx.events
    assert tx.events['LogDepegDepegBalanceAdded']['wallet'] == protectedWallet
    assert tx.events['LogDepegDepegBalanceAdded']['blockNumber'] == depeg_block_number
    assert tx.events['LogDepegDepegBalanceAdded']['balance'] == depegged_at_balance

    tx = product.processPolicies([process_id])

    # check logs and info in logs
    assert 'LogDepegClaimConfirmed' in tx.events
    assert tx.events['LogDepegClaimConfirmed']['processId'] == process_id
    assert tx.events['LogDepegClaimConfirmed']['claimId'] == claim_id
    assert tx.events['LogDepegClaimConfirmed']['accountBalance'] == depegged_at_balance
    assert tx.events['LogDepegClaimConfirmed']['claimAmount'] == claim_amount_expected
    assert tx.events['LogDepegClaimConfirmed']['payoutAmount'] == payout_amount_expected

    assert 'LogDepegPayoutProcessed' in tx.events
    assert tx.events['LogDepegPayoutProcessed']['processId'] == process_id
    assert tx.events['LogDepegPayoutProcessed']['payoutId'] == payout_id
    assert tx.events['LogDepegPayoutProcessed']['claimId'] == claim_id
    assert tx.events['LogDepegPayoutProcessed']['payoutAmount'] == payout_amount_expected

    assert 'LogDepegPolicyClosed' in tx.events
    assert tx.events['LogDepegPolicyClosed']['processId'] == process_id

    # no more policies to process, 1 payout
    assert product.policiesToProcess() == 0
    assert instanceService.claims(process_id) == 1
    assert instanceService.payouts(process_id) == 1

    # check payout data
    payout_id = 0
    payout = instanceService.getPayout(process_id, payout_id).dict()
    assert payout['state'] == 1 # enum PayoutState {Expected, PaidOut}
    assert payout['claimId'] == claim_id
    assert payout['amount'] == payout_amount_expected

    # check claim data
    claim = instanceService.getClaim(process_id, claim_id).dict()
    assert claim['state'] == 3 # enum ClaimState {Applied, Confirmed, Declined, Closed}
    assert claim['claimAmount'] == claim_amount_expected
    assert claim['paidAmount'] == claim_amount_expected

    # check policy data
    policy = instanceService.getPolicy(process_id).dict()
    assert policy['state'] == 2 # enum PolicyState {Active, Expired, Closed}
    assert policy['payoutMaxAmount'] == sum_insured
    assert policy['payoutAmount'] == payout_amount_expected # payout amount
    assert policy['claimsCount'] == 1 # claims count
    assert policy['openClaimsCount'] == 0 # open claims count

    # check effect on token balance after payout
    # depeg protection has max 1 payout, after execution of payout policy is closed, 
    # this results in 0 locked capital afterwards
    assert instanceService.getBalance(riskpool_id) == bundle_funding + net_premium - payout_amount_expected
    assert instanceService.getCapital(riskpool_id) == bundle_funding - payout_amount_expected
    assert instanceService.getTotalValueLocked(riskpool_id) == 0

    # check actual balances of riskpool, protected wallet and policy holder at end of happy case
    assert protected_token.balanceOf(protectedWallet) == wallet_balance
    assert token.balanceOf(instanceWallet) == premium_fee # some fee for premium payment
    assert token.balanceOf(riskpoolWallet) == bundle_funding + net_premium - payout_amount_expected
    assert token.balanceOf(protectedWallet) == 0
    assert token.balanceOf(customer) == payout_amount_expected
    assert token.balanceOf(investor) == 0

    # investor may now burn bundle and claim the remaining balance
    bundle_balance_remaining = instanceService.getBalance(riskpool_id)

    # bundle needs to be closed before it can be burned
    riskpool.closeBundle(bundle_id, {'from': investor})

    # check actual balances of riskpool, protected wallet and policy holder at end of happy case
    assert protected_token.balanceOf(protectedWallet) == wallet_balance
    assert token.balanceOf(instanceWallet) == premium_fee # some fee for premium payment
    assert token.balanceOf(riskpoolWallet) == bundle_balance_remaining
    assert token.balanceOf(protectedWallet) == 0
    assert token.balanceOf(customer) == payout_amount_expected
    assert token.balanceOf(investor) == 0

    tx = riskpool.burnBundle(bundle_id, {'from': investor})

    assert 'LogTreasuryWithdrawalTransferred' in tx.events
    assert tx.events['LogTreasuryWithdrawalTransferred']['riskpoolWalletAddress'] == riskpool_wallet
    assert tx.events['LogTreasuryWithdrawalTransferred']['to'] == investor
    assert tx.events['LogTreasuryWithdrawalTransferred']['amount'] == bundle_balance_remaining

    assert 'LogRiskpoolBundleBurned' in tx.events
    assert tx.events['LogRiskpoolBundleBurned']['bundleId'] == bundle_id

    # check actual balances of riskpool, protected wallet and policy holder at end of happy case
    assert protected_token.balanceOf(protectedWallet) == wallet_balance
    assert token.balanceOf(instanceWallet) == premium_fee # some fee for premium payment
    assert token.balanceOf(riskpoolWallet) == 0
    assert token.balanceOf(protectedWallet) == 0
    assert token.balanceOf(customer) == payout_amount_expected
    assert token.balanceOf(investor) == bundle_balance_remaining


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
