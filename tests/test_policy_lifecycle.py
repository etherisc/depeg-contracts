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
    apply_for_policy_with_bundle,
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
    tf = 10 ** protected_token.decimals()

    # create token allowance for payouts
    max_payout_amount = 100000
    token.approve(
        instanceService.getTreasuryAddress(), 
        max_payout_amount * tf, 
        {'from': riskpool_wallet})

    # setup riskpool with a single risk bundle
    bundle_funding = 10000
    min_protected_balance = 2000
    max_protected_balance = 10000

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
        minProtectedBalance=min_protected_balance,
        maxProtectedBalance=max_protected_balance)

    # check actual balances of riskpool, protected wallet and policy holder
    assert protected_token.balanceOf(protectedWallet) == 0
    assert token.balanceOf(instanceWallet) == 0 # zero fee for risk capital staking
    assert token.balanceOf(riskpoolWallet) == bundle_funding * tf
    assert token.balanceOf(protectedWallet) == 0
    assert token.balanceOf(customer) == 0
    assert token.balanceOf(investor) == 0

    # check effect on riskpoool
    assert instanceService.getBalance(riskpool_id) == bundle_funding * tf 
    assert instanceService.getCapital(riskpool_id) == bundle_funding * tf
    assert instanceService.getTotalValueLocked(riskpool_id) == 0

    # setup up wallet to protect with some coins
    wallet_balance = 4051
    protected_token.transfer(protectedWallet, wallet_balance * tf, {'from': instanceOperator})
    assert wallet_balance < max_payout_amount # protection: amounts need to stay in relation to each other

    # set application parameters
    protected_balance = wallet_balance
    sum_insured = riskpool.calculateSumInsured(protected_balance)
    duration_days = 60
    max_premium = 42 # might need to actually calculate this ...

    riskpool_balance_before = instanceService.getBalance(riskpool_id)
    instance_balance_before = token.balanceOf(instance_wallet)

    # check effect on riskpoool status
    assert instanceService.getBalance(riskpool_id) == bundle_funding * tf
    assert instanceService.getCapital(riskpool_id) == bundle_funding * tf
    assert instanceService.getTotalValueLocked(riskpool_id) == 0

    process_id = apply_for_policy_with_bundle(
        instance,
        instanceOperator,
        product,
        customer,
        bundle_id,
        protectedWallet,
        protected_balance,
        duration_days,
        max_premium)

    tx = history[-1]
    assert 'LogTreasuryPremiumTransferred' in tx.events
    assert 'LogTreasuryFeesTransferred' in tx.events

    net_premium = tx.events['LogTreasuryPremiumTransferred']['amount']
    premium_fee = tx.events['LogTreasuryFeesTransferred']['amount']
    premium = net_premium + premium_fee
    assert net_premium + premium_fee <= max_premium * tf

    # check actual balances of riskpool, protected wallet and policy holder
    assert protected_token.balanceOf(protectedWallet) == wallet_balance * tf
    assert token.balanceOf(instanceWallet) == premium_fee # some fee for premium payment
    assert token.balanceOf(riskpoolWallet) == bundle_funding * tf + net_premium
    assert token.balanceOf(protectedWallet) == 0
    assert token.balanceOf(customer) == max_premium * tf - premium
    assert token.balanceOf(investor) == 0

    # check effect on riskpoool status
    assert instanceService.getBalance(riskpool_id) == bundle_funding * tf + net_premium
    assert instanceService.getCapital(riskpool_id) == bundle_funding * tf
    assert instanceService.getTotalValueLocked(riskpool_id) == sum_insured * tf

    riskpool_balance_after = instanceService.getBalance(riskpool_id)
    instance_balance_after = token.balanceOf(instanceWallet)

    tx = history[-1]
    assert 'LogDepegApplicationCreated' in tx.events
    assert tx.events['LogDepegApplicationCreated']['processId'] == process_id
    assert tx.events['LogDepegApplicationCreated']['policyHolder'] == customer
    assert tx.events['LogDepegApplicationCreated']['protectedWallet'] == protectedWallet
    assert tx.events['LogDepegApplicationCreated']['sumInsuredAmount'] == sum_insured * tf
    assert tx.events['LogDepegApplicationCreated']['premiumAmount'] == premium

    assert 'LogDepegPolicyCreated' in tx.events
    assert tx.events['LogDepegPolicyCreated']['processId'] == process_id
    assert tx.events['LogDepegPolicyCreated']['policyHolder'] == customer
    assert tx.events['LogDepegPolicyCreated']['sumInsuredAmount'] == sum_insured * tf

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
    assert application['premiumAmount'] == premium
    assert application['sumInsuredAmount'] == sum_insured * tf

    # check policy
    assert policy['premiumExpectedAmount'] == premium
    assert policy['premiumPaidAmount'] == premium
    assert policy['payoutMaxAmount'] == sum_insured * tf
    assert policy['payoutAmount'] == 0
    assert policy['claimsCount'] == 0
    assert policy['openClaimsCount'] == 0

    # check claimed balance
    assert product.getProcessedBalance(protectedWallet) == 0

    fixed_fee = 0
    fractional_fee = 0.05

    assert int(fractional_fee * premium + fixed_fee) == premium_fee
    assert net_premium == premium - premium_fee

    (
        wallet,
        protected_balance,
        application_duration,
        application_bundle_id,
        application_max_net_premium
    ) = riskpool.decodeApplicationParameterFromData(application['data'])

    assert wallet == protectedWallet
    assert protected_balance == sum_insured * tf
    assert application_duration == duration_days * 24 * 3600
    assert application_bundle_id == 1
    assert application_max_net_premium == net_premium

    # check wallet balances against premium payment
    assert riskpool_balance_after == riskpool_balance_before + net_premium
    assert instance_balance_after == instance_balance_before + premium_fee

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

    # check claimed balance
    assert product.getProcessedBalance(protectedWallet) == 0

    # calcuate expected claim amount
    target_price = product.getTargetPrice()
    claim_amount_expected = int(sum_insured * tf * (target_price - depeg_price) / target_price)

    # check product claim amaount calculation
    assert product.calculateClaimAmount(sum_insured * tf) == claim_amount_expected

    # create claim from protected wallet
    tx = product.createDepegClaim(
        process_id,
        {'from': protectedWallet})

    # check claimed balance
    assert product.getProcessedBalance(protectedWallet) == 0

    # check actual balances of riskpool, protected wallet and policy holder
    assert protected_token.balanceOf(protectedWallet) == wallet_balance * tf
    assert token.balanceOf(instanceWallet) == premium_fee # some fee for premium payment
    assert token.balanceOf(riskpoolWallet) == bundle_funding * tf + net_premium
    assert token.balanceOf(protectedWallet) == 0
    assert token.balanceOf(customer) == max_premium * tf - premium
    assert token.balanceOf(investor) == 0

    # check zero effect on riskpoool status
    assert instanceService.getBalance(riskpool_id) == bundle_funding * tf + net_premium
    assert instanceService.getCapital(riskpool_id) == bundle_funding * tf
    assert instanceService.getTotalValueLocked(riskpool_id) == sum_insured * tf

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
    assert policy['payoutMaxAmount'] == sum_insured * tf
    assert policy['payoutAmount'] == 0 # payout amount
    assert policy['claimsCount'] == 1 # claims count
    assert policy['openClaimsCount'] == 1 # open claims count

    # process policy
    # in this case balance of wallet at depeg time 
    # exactly matches with the amount protected for that wallet
    payout_id = 0
    depegged_at_balance = sum_insured * tf
    payout_amount_expected = claim_amount_expected

    assert protected_token.balanceOf(protectedWallet) == depegged_at_balance
    assert token.balanceOf(protectedWallet) == 0

    # this number needs to be determined via moralis using the depeg timestamp via getDepeggedAt()
    depeg_block_number = 1000
    depeg_block_number_comment = "block number for timsteamp xyz"

    assert product.getDepeggedBlockNumber() == 0

    # check that customer cannot set depegged block number
    with brownie.reverts('Ownable: caller is not the owner'):
        product.setDepeggedBlockNumber(
            depeg_block_number,
            depeg_block_number_comment,
            {'from': customer})

    # check product owner can set depeg block number
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

    # check that customer cannot set depegged balance
    with brownie.reverts('Ownable: caller is not the owner'):
        product.addDepegBalances(
            [depeg_balance],
            {'from': customer})

    # check that product owner can set depeg balances
    tx = product.addDepegBalances(
        [depeg_balance],
        {'from': productOwner})

    assert 'LogDepegDepegBalanceAdded' in tx.events
    assert tx.events['LogDepegDepegBalanceAdded']['wallet'] == protectedWallet
    assert tx.events['LogDepegDepegBalanceAdded']['blockNumber'] == depeg_block_number
    assert tx.events['LogDepegDepegBalanceAdded']['balance'] == depegged_at_balance

    assert product.getProcessedBalance(protectedWallet) == 0

    tx = product.processPolicies([process_id])

    assert product.getProcessedBalance(protectedWallet) == wallet_balance * tf

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
    assert policy['payoutMaxAmount'] == sum_insured * tf
    assert policy['payoutAmount'] == payout_amount_expected # payout amount
    assert policy['claimsCount'] == 1 # claims count
    assert policy['openClaimsCount'] == 0 # open claims count

    # check effect on token balance after payout
    # depeg protection has max 1 payout, after execution of payout policy is closed, 
    # this results in 0 locked capital afterwards
    assert instanceService.getBalance(riskpool_id) == bundle_funding * tf + net_premium - payout_amount_expected
    assert instanceService.getCapital(riskpool_id) == bundle_funding * tf - payout_amount_expected
    assert instanceService.getTotalValueLocked(riskpool_id) == 0

    # check actual balances of riskpool, protected wallet and policy holder at end of happy case
    assert protected_token.balanceOf(protectedWallet) == wallet_balance * tf
    assert token.balanceOf(instanceWallet) == premium_fee # some fee for premium payment
    assert token.balanceOf(riskpoolWallet) == bundle_funding * tf + net_premium - payout_amount_expected
    assert token.balanceOf(protectedWallet) == 0
    assert token.balanceOf(customer) == payout_amount_expected + max_premium * tf - premium
    assert token.balanceOf(investor) == 0

    # investor may now burn bundle and claim the remaining balance
    bundle_balance_remaining = instanceService.getBalance(riskpool_id)

    # bundle needs to be closed before it can be burned
    riskpool.closeBundle(bundle_id, {'from': investor})

    # check actual balances of riskpool, protected wallet and policy holder at end of happy case
    assert protected_token.balanceOf(protectedWallet) == wallet_balance * tf
    assert token.balanceOf(instanceWallet) == premium_fee # some fee for premium payment
    assert token.balanceOf(riskpoolWallet) == bundle_balance_remaining
    assert token.balanceOf(protectedWallet) == 0
    assert token.balanceOf(customer) == payout_amount_expected + max_premium * tf - premium
    assert token.balanceOf(investor) == 0

    info_closed = riskpool.getBundleInfo(bundle_id).dict()
    assert info_closed['bundleId'] == bundle_id
    assert info_closed['owner'] == investor
    assert info_closed['state'] == 2 # enum BundleState { Active, Locked, Closed, Burned }
    assert info_closed['lockedCapital'] == 0
    assert info_closed['balance'] == bundle_balance_remaining

    tx = riskpool.burnBundle(bundle_id, {'from': investor})

    assert 'LogTreasuryWithdrawalTransferred' in tx.events
    assert tx.events['LogTreasuryWithdrawalTransferred']['riskpoolWalletAddress'] == riskpool_wallet
    assert tx.events['LogTreasuryWithdrawalTransferred']['to'] == investor
    assert tx.events['LogTreasuryWithdrawalTransferred']['amount'] == bundle_balance_remaining

    assert 'LogRiskpoolBundleBurned' in tx.events
    assert tx.events['LogRiskpoolBundleBurned']['bundleId'] == bundle_id

    # check actual balances of riskpool, protected wallet and policy holder at end of happy case
    assert protected_token.balanceOf(protectedWallet) == wallet_balance * tf
    assert token.balanceOf(instanceWallet) == premium_fee # some fee for premium payment
    assert token.balanceOf(riskpoolWallet) == 0
    assert token.balanceOf(protectedWallet) == 0
    assert token.balanceOf(customer) == payout_amount_expected + max_premium * tf - premium
    assert token.balanceOf(investor) == bundle_balance_remaining

    info_burned = riskpool.getBundleInfo(bundle_id).dict()
    assert info_burned['bundleId'] == bundle_id
    assert info_burned['owner'] == '0x0000000000000000000000000000000000000000'
    assert info_burned['state'] == 3 # enum BundleState { Active, Locked, Closed, Burned }
    assert info_burned['lockedCapital'] == 0
    assert info_burned['balance'] == 0


def test_over_protected_with_single_policy(
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
    token_address = instanceService.getComponentToken(riskpool_id)
    token = interface.IERC20Metadata(token_address)
    protected_token_address = product.getProtectedToken()
    protected_token = interface.IERC20Metadata(protected_token_address)
    tf = 10 ** protected_token.decimals()

    # create token allowance for payouts
    max_payout_amount = 100000
    token.approve(
        instanceService.getTreasuryAddress(), 
        max_payout_amount * tf, 
        {'from': riskpool_wallet})

    # setup riskpool with a single risk bundle
    bundle_funding = 15000
    min_protected_balance = 2000
    max_protected_balance = 10000

    bundle_id = create_bundle(
        instance,
        instanceOperator,
        investor,
        riskpool,
        funding=bundle_funding,
        minProtectedBalance=min_protected_balance,
        maxProtectedBalance=max_protected_balance)

    # setup up wallet to protect with some coins
    wallet_balance = 5000
    protected_token.transfer(protectedWallet, wallet_balance * tf, {'from': instanceOperator})
    assert wallet_balance < max_payout_amount # protection: amounts need to stay in relation to each other

    # buy protection for double of the wallet balance
    protected_balance = 2 * wallet_balance
    duration_days = 60
    max_premium = 80 # might need to actually calculate this ...

    process_id = apply_for_policy_with_bundle(
        instance,
        instanceOperator,
        product,
        customer,
        bundle_id,
        protectedWallet,
        protected_balance,
        duration_days,
        max_premium)

    tx = history[-1]
    assert 'LogDepegPolicyCreated' in tx.events
    assert tx.events['LogDepegApplicationCreated']['processId'] == process_id

    # create depeg at 90% of target price (= 10% loss on protected funds)
    depeg_price = int(0.9 * product.getTargetPrice())
    (timestamp_trigger, timestamp_depeg) = force_product_into_depegged_state(product, productOwner, depeg_price)

    depeg_info = product.getDepegPriceInfo().dict()
    assert depeg_info['triggeredAt'] == timestamp_trigger
    assert depeg_info['depeggedAt'] == timestamp_depeg
    assert depeg_info['price'] == depeg_price

    # create claim from protected wallet
    tx = product.createDepegClaim(
        process_id,
        {'from': protectedWallet})

    # this number needs to be determined via moralis using the depeg timestamp via getDepeggedAt()
    depeg_block_number = 1000
    depeg_block_number_comment = "block number for timsteamp xyz"

    tx = product.setDepeggedBlockNumber(
        depeg_block_number,
        depeg_block_number_comment,
        {'from': productOwner})

    # inject balance data for depegged time for protected wallet
    depegged_at_balance = protected_token.balanceOf(protectedWallet)
    depeg_balance = product.createDepegBalance(
        protectedWallet,
        depeg_block_number,
        depegged_at_balance)

    # needs to be protected
    tx = product.addDepegBalances(
        [depeg_balance],
        {'from': productOwner})

    # check product claim amaount calculation
    payout_id = 0
    target_price = product.getTargetPrice()
    payout_amount_expected = int(depegged_at_balance * (target_price - depeg_price) / target_price)

    assert product.calculateClaimAmount(wallet_balance * tf) == payout_amount_expected

    # process payout
    assert product.getProcessedBalance(protectedWallet) == 0
    tx = product.processPolicies([process_id])
    assert product.getProcessedBalance(protectedWallet) == wallet_balance * tf

    # check amount adustment
    assert 'LogDepegProtectedAmountReduction' in tx.events
    assert 'LogDepegProcessedAmountReduction' not in tx.events

    evt = tx.events['LogDepegProtectedAmountReduction']
    assert evt['protectedAmount'] == protected_balance * tf
    assert evt['depegBalance'] == depegged_at_balance
    assert protected_balance * tf == 2 * depegged_at_balance

    assert 'LogPayoutCreated' in tx.events
    assert tx.events['LogPayoutCreated']['amount'] == int(0.1 * depegged_at_balance)


def test_over_protected_with_multiple_policies(
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
    token_address = instanceService.getComponentToken(riskpool_id)
    token = interface.IERC20Metadata(token_address)
    protected_token_address = product.getProtectedToken()
    protected_token = interface.IERC20Metadata(protected_token_address)
    tf = 10 ** protected_token.decimals()

    # create token allowance for payouts
    max_payout_amount = 100000
    token.approve(
        instanceService.getTreasuryAddress(), 
        max_payout_amount * tf, 
        {'from': riskpool_wallet})

    # setup riskpool with a single risk bundle
    bundle_funding = 15000 + 1
    min_protected_balance = 2000
    max_protected_balance = 10000

    bundle_id = create_bundle(
        instance,
        instanceOperator,
        investor,
        riskpool,
        funding=bundle_funding,
        minProtectedBalance=min_protected_balance,
        maxProtectedBalance=max_protected_balance)

    # setup up wallet to protect with some coins
    wallet_balance = 8000
    protected_token.transfer(protectedWallet, wallet_balance * tf, {'from': instanceOperator})
    assert wallet_balance < max_payout_amount # protection: amounts need to stay in relation to each other

    # buy .3 policies to cover 15000 (a wallet with a balance of 8000)
    protected_balance = 5000
    duration_days = 60
    max_premium = 80 # might need to actually calculate this ...

    process_id1 = apply_for_policy_with_bundle(
        instance,
        instanceOperator,
        product,
        customer,
        bundle_id,
        protectedWallet,
        protected_balance,
        duration_days,
        max_premium)

    process_id2 = apply_for_policy_with_bundle(
        instance,
        instanceOperator,
        product,
        customer,
        bundle_id,
        protectedWallet,
        protected_balance,
        duration_days,
        max_premium)

    process_id3 = apply_for_policy_with_bundle(
        instance,
        instanceOperator,
        product,
        customer,
        bundle_id,
        protectedWallet,
        protected_balance,
        duration_days,
        max_premium)

    # check we have 3 active policies
    assert instanceService.getPolicy(process_id1).dict()['state'] == 0
    assert instanceService.getPolicy(process_id2).dict()['state'] == 0
    assert instanceService.getPolicy(process_id3).dict()['state'] == 0

    # create depeg at 90% of target price (= 10% loss on protected funds)
    depeg_price = int(0.9 * product.getTargetPrice())
    (timestamp_trigger, timestamp_depeg) = force_product_into_depegged_state(product, productOwner, depeg_price)

    depeg_info = product.getDepegPriceInfo().dict()
    assert depeg_info['triggeredAt'] == timestamp_trigger
    assert depeg_info['depeggedAt'] == timestamp_depeg
    assert depeg_info['price'] == depeg_price

    # create 3 claims for protected wallet
    product.createDepegClaim(process_id1, {'from': protectedWallet})
    product.createDepegClaim(process_id2, {'from': protectedWallet})
    product.createDepegClaim(process_id3, {'from': protectedWallet})

    # check we have the claims
    assert instanceService.claims(process_id1) == 1
    assert instanceService.claims(process_id2) == 1
    assert instanceService.claims(process_id3) == 1

    # this number needs to be determined via moralis using the depeg timestamp via getDepeggedAt()
    depeg_block_number = 1000
    depeg_block_number_comment = "block number for timsteamp xyz"

    tx = product.setDepeggedBlockNumber(
        depeg_block_number,
        depeg_block_number_comment,
        {'from': productOwner})

    # inject balance data for depegged time for protected wallet
    depegged_at_balance = protected_token.balanceOf(protectedWallet)
    depeg_balance = product.createDepegBalance(
        protectedWallet,
        depeg_block_number,
        depegged_at_balance)

    # needs to be protected
    tx = product.addDepegBalances(
        [depeg_balance],
        {'from': productOwner})

    # process 1st payout
    assert product.getProcessedBalance(protectedWallet) == 0
    tx = product.processPolicy(process_id1)
    assert product.getProcessedBalance(protectedWallet) == protected_balance * tf

    assert 'LogDepegProtectedAmountReduction' not in tx.events
    assert 'LogDepegProcessedAmountReduction' not in tx.events

    # process 2nd payout
    tx = product.processPolicy(process_id2)
    assert product.getProcessedBalance(protectedWallet) == depeg_balance.dict()['balance']

    assert 'LogDepegProtectedAmountReduction' not in tx.events
    assert 'LogDepegProcessedAmountReduction' in tx.events

    evt = dict(tx.events['LogDepegProcessedAmountReduction'])
    assert evt['processId'] == process_id2
    assert evt['protectedAmount'] == protected_balance * tf
    assert evt['amountLeftToProcess'] == depegged_at_balance - protected_balance * tf

    # re-check that full wallet balance has already be processed
    assert product.getProcessedBalance(protectedWallet) == depegged_at_balance

    # attempt to process 3rd payout
    with brownie.reverts('ERROR:DP-045:PROTECTED_BALANCE_PROCESSED_ALREADY'):
        product.processPolicy(process_id3)


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
