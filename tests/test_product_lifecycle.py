import brownie
import pytest

from brownie import (
    chain,
    history,
    UsdcPriceDataProvider,
)

from scripts.price_data import (
    STATE_PRODUCT,
    EVENT_TYPE,
    STATE_COMPLIANCE,
    STATE_STABILITY,
    PERFECT_PRICE,
    TRIGGER_PRICE,
    RECOVERY_PRICE,
    generate_next_data,
    inject_data,
)

from scripts.setup import (
    create_bundle, 
    apply_for_policy,
)

from scripts.util import (
    contract_from_address
)

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


def test_generate_data():
    for i in range(4):
        generate_next_data(i)

    # check default increasing data
    data_baseline = generate_next_data(4)
    data_next = generate_next_data(5)

    (round_id, answer, started_at) = data_next.split()[:3]
    assert int(round_id) - 1 == int(data_baseline.split()[0])
    assert abs(int(answer) - PERFECT_PRICE) <= 10
    assert abs(int(started_at) - (int(data_baseline.split()[2]) + 24 * 3600)) <= 240

    # check fully specified data
    data_latest = generate_next_data(
        6,
        price=PERFECT_PRICE+42,
        last_update=int(started_at),
        delta_time=12345)

    (round_id_latest, answer_latest, started_at_latest) = data_latest.split()[:3]
    assert int(round_id_latest) == int(round_id) + 1 
    assert int(answer_latest) == PERFECT_PRICE+42
    assert int(started_at_latest) == int(started_at) + 12345


def test_product_lifecycle_startup(
    instanceOperator,
    productOwner,
    product,
    usd1
):
    # check initial lifecycle state
    assert product.getDepegState() == STATE_PRODUCT['Active']

    # initially no new price info expected
    event_info = product.isNewPriceInfoEventAvailable().dict()
    print('isNewPriceInfoEventAvailable {}'.format(event_info))

    assert event_info['newEvent'] is False
    assert event_info['timeSinceEvent'] == 0

    # get and check price data provider contract
    price_data_provider = contract_from_address(UsdcPriceDataProvider, product.getPriceDataProvider())    
    assert price_data_provider.getToken() == usd1

    # check price info from product with one from the provider
    price_info = event_info['priceInfo'].dict()
    price_info_feeder = price_data_provider.getLatestPriceInfo().dict()

    for key in price_info.keys():
        assert price_info[key] == price_info_feeder[key]

    # create initial data point and inject to pr
    data = generate_next_data(0)
    inject_data(price_data_provider, data, productOwner, sleep=True)

    # check again
    event_info = product.isNewPriceInfoEventAvailable().dict()
    print('isNewPriceInfoEventAvailable {}'.format(event_info))

    (price_id, price, timestamp) = data.split()[:3]
    assert event_info['newEvent'] is False
    assert event_info['timeSinceEvent'] <= 1

    price_info = event_info['priceInfo'].dict()
    assert price_info['id'] == price_id
    assert price_info['price'] == price
    assert price_info['eventType'] == EVENT_TYPE['Update']
    assert price_info['compliance'] == STATE_COMPLIANCE['Initializing']
    assert price_info['stability'] == STATE_STABILITY['Stable']
    assert price_info['triggeredAt'] == 0
    assert price_info['depeggedAt'] == 0
    assert price_info['createdAt'] == timestamp

    # process new price info
    tx = product.processLatestPriceInfo()

    # check price update log entry (no new event case)
    assert len(tx.events) == 2
    assert 'LogDepegPriceEvent' in tx.events
    assert 'LogPriceDataProcessed' in tx.events
    assert tx.events['LogPriceDataProcessed']['priceId'] == price_id
    assert tx.events['LogPriceDataProcessed']['price'] == price
    assert tx.events['LogPriceDataProcessed']['createdAt'] == timestamp

    # create 2nd data point and inject to pr
    data = generate_next_data(1)
    inject_data(price_data_provider, data, productOwner, sleep=True)

    # check again
    event_info = product.isNewPriceInfoEventAvailable().dict()
    print('isNewPriceInfoEventAvailable {}'.format(event_info))

    (price_id2, price2, timestamp2) = data.split()[:3]
    assert event_info['newEvent'] is False
    assert event_info['timeSinceEvent'] <= 1

    price_info = event_info['priceInfo'].dict()
    assert price_info['id'] == price_id2
    assert price_info['price'] == price2
    assert price_info['eventType'] == EVENT_TYPE['Update']
    assert price_info['compliance'] == STATE_COMPLIANCE['Valid']
    assert price_info['stability'] == STATE_STABILITY['Stable']
    assert price_info['triggeredAt'] == 0
    assert price_info['depeggedAt'] == 0
    assert price_info['createdAt'] == timestamp2

    # check depeg state is still fine
    assert product.getDepegState() == STATE_PRODUCT['Active']


def test_product_lifecycle_trigger(
    instance,
    instanceOperator,
    investor,
    riskpool,
    productOwner,
    product,
    customer,
    protectedWallet,
):
    # fund riskpool
    create_bundle(
        instance,
        instanceOperator,
        investor,
        riskpool)

    # obtain data provider contract from product
    data_provider = contract_from_address(
        UsdcPriceDataProvider,
        product.getPriceDataProvider())

    # inject some initial price data
    for i in range(5):
        inject_and_process_data(product, data_provider, generate_next_data(i), productOwner)

    # check base line
    assert product.getDepegState() == STATE_PRODUCT['Active']

    price_info = product.getLatestPriceInfo().dict()
    print('priceInfo {}'.format(price_info))

    # generate pre-trigger and trigger data
    print('--- test price at depeg trigger threshold + 1 ---')
    above_trigger_data = generate_next_data(
        5,
        price = TRIGGER_PRICE + 1,
        delta_time = 12 * 3600
        )

    tx = inject_and_process_data(product, data_provider, above_trigger_data, productOwner)
    assert 'LogPriceDataProcessed' in tx.events
    assert 'LogDepegProductPaused' not in tx.events
    assert product.getDepegState() == STATE_PRODUCT['Active']

    (price_id, price, timestamp) = above_trigger_data.split()[:3]
    price_info = product.getLatestPriceInfo().dict()
    print('priceInfo {}'.format(price_info))

    assert price_info['id'] == price_id
    assert price_info['price'] == price
    assert price_info['eventType'] == EVENT_TYPE['Update']
    assert price_info['compliance'] in [STATE_COMPLIANCE['FailedOnce'], STATE_COMPLIANCE['FailedMultipleTimes']]
    assert price_info['stability'] == STATE_STABILITY['Stable']
    assert price_info['triggeredAt'] == 0
    assert price_info['depeggedAt'] == 0
    assert price_info['createdAt'] == timestamp

    # verify that it's still possible to underwrite a new policy
    sumInsured = 10000
    durationDays = 60
    maxPremium = 750

    process_id_1 = apply_for_policy(
        instance,
        instanceOperator,
        product,
        customer,
        protectedWallet,
        sumInsured,
        durationDays,
        maxPremium)

    instanceService = instance.getInstanceService()
    application = instanceService.getApplication(process_id_1).dict()
    policy = instanceService.getPolicy(process_id_1).dict()
    print('application {}'.format(application))
    print('policy {}'.format(policy))

    assert application['createdAt'] >= price_info['createdAt']
    assert policy['createdAt'] == application['createdAt']

    # generate pre-trigger and trigger data
    print('--- triggering depeg product ---')
    trigger_data = generate_next_data(
        6,
        price = TRIGGER_PRICE,
        delta_time = 12 * 3600
        )

    (round_id, price, timestamp) = trigger_data.split()[:3]
    timestamp = int(timestamp)

    tx = inject_and_process_data(product, data_provider, trigger_data, productOwner)
    assert len(tx.events) == 3
    assert 'LogPriceDataTriggered' in tx.events
    assert 'LogDepegPriceEvent' in tx.events
    assert tx.events['LogDepegPriceEvent']['priceId'] == round_id
    assert tx.events['LogDepegPriceEvent']['price'] == price
    assert tx.events['LogDepegPriceEvent']['eventType'] == EVENT_TYPE['TriggerEvent']
    assert tx.events['LogDepegPriceEvent']['triggeredAt'] == timestamp
    assert tx.events['LogDepegPriceEvent']['depeggedAt'] == 0
    assert tx.events['LogDepegPriceEvent']['createdAt'] == timestamp

    assert 'LogDepegProductPaused' in tx.events
    assert tx.events['LogDepegProductPaused']['priceId'] == round_id
    assert abs(tx.events['LogDepegProductPaused']['pausedAt'] - timestamp) <= 5

    price_info = product.getLatestPriceInfo().dict()
    print('priceInfo {}'.format(price_info))

    assert product.getDepegState() == STATE_PRODUCT['Paused']

    # verify that it's not possible to underwrite a new policy
    with brownie.reverts('ERROR:DP-011:PRODUCT_NOT_ACTIVE'):
        apply_for_policy(
            instance,
            instanceOperator,
            product,
            customer,
            protectedWallet,
            sumInsured,
            durationDays,
            maxPremium)


def test_product_lifecycle_trigger_and_recover(
    instance,
    instanceOperator,
    investor,
    riskpool,
    productOwner,
    product,
    customer,
    protectedWallet,
):
    # fund riskpool
    create_bundle(
        instance,
        instanceOperator,
        investor,
        riskpool)

    # obtain data provider contract from product
    data_provider = contract_from_address(
        UsdcPriceDataProvider, 
        product.getPriceDataProvider())

    # inject some initial price data
    for i in range(5):
        inject_and_process_data(product, data_provider, generate_next_data(i), productOwner)

    # check base line
    assert product.getTriggeredAt() == 0
    assert product.getDepeggedAt() == 0
    assert product.getDepegState() == STATE_PRODUCT['Active']

    # generate trigger data
    print('--- triggering depeg product ---')
    trigger_data = generate_next_data(
        5,
        price = TRIGGER_PRICE,
        delta_time = 12 * 3600)

    (round_id, price, timestamp) = trigger_data.split()[:3]
    timestamp = int(timestamp)
    timestamp_triggered = timestamp
    assert timestamp_triggered > 0

    tx = inject_and_process_data(product, data_provider, trigger_data, productOwner)
    assert len(tx.events) == 3
    assert 'LogPriceDataTriggered' in tx.events
    assert 'LogDepegProductPaused' in tx.events

    assert product.getTriggeredAt() == timestamp_triggered
    assert product.getDepeggedAt() == 0
    assert product.getDepegState() == STATE_PRODUCT['Paused']

    # verify that it's not possible to underwrite a new policy
    sumInsured = 10000
    durationDays = 60
    maxPremium = 750

    with brownie.reverts('ERROR:DP-011:PRODUCT_NOT_ACTIVE'):
        apply_for_policy(
            instance,
            instanceOperator,
            product,
            customer,
            protectedWallet,
            sumInsured,
            durationDays,
            maxPremium)

    # new data (remaining in triggered state)
    trigger_data = generate_next_data(
        6,
        price=TRIGGER_PRICE + 100,
        last_update=timestamp,
        delta_time=12 * 3600)

    (round_id, price, timestamp) = trigger_data.split()[:3]
    timestamp = int(timestamp)

    tx = inject_and_process_data(product, data_provider, trigger_data, productOwner)
    assert len(tx.events) == 2
    assert 'LogPriceDataProcessed' in tx.events
    assert 'LogDepegPriceEvent' in tx.events

    assert product.getTriggeredAt() == timestamp_triggered
    assert product.getDepeggedAt() == 0
    assert product.getDepegState() == STATE_PRODUCT['Paused']

    with brownie.reverts('ERROR:DP-011:PRODUCT_NOT_ACTIVE'):
        apply_for_policy(
            instance,
            instanceOperator,
            product,
            customer,
            protectedWallet,
            sumInsured,
            durationDays,
            maxPremium)

    # new data (recover from triggered state)
    trigger_data = generate_next_data(
        7,
        price = RECOVERY_PRICE,
        last_update=timestamp,
        delta_time = 11 * 3600)

    (round_id, price, timestamp) = trigger_data.split()[:3]
    timestamp = int(timestamp)

    tx = inject_and_process_data(product, data_provider, trigger_data, productOwner)
    assert len(tx.events) == 3
    assert 'LogPriceDataRecovered' in tx.events
    assert 'LogDepegPriceEvent' in tx.events
    assert 'LogDepegProductUnpaused' in tx.events
    assert tx.events['LogDepegProductUnpaused']['priceId'] == round_id
    assert abs(tx.events['LogDepegProductUnpaused']['unpausedAt'] - timestamp) <= 5

    # check that depeg state is active again
    assert product.getTriggeredAt() == 0
    assert product.getDepeggedAt() == 0
    assert product.getDepegState() == STATE_PRODUCT['Active']

    price_info = product.getLatestPriceInfo().dict()
    print('priceInfo {}'.format(price_info))

    # check that it's again possible to buy a policy
    sumInsured = 10000
    durationDays = 60
    maxPremium = 750

    process_id_1 = apply_for_policy(
        instance,
        instanceOperator,
        product,
        customer,
        protectedWallet,
        sumInsured,
        durationDays,
        maxPremium)

    instanceService = instance.getInstanceService()
    application = instanceService.getApplication(process_id_1).dict()
    policy = instanceService.getPolicy(process_id_1).dict()
    print('application {}'.format(application))
    print('policy {}'.format(policy))

    assert application['createdAt'] >= price_info['createdAt']
    assert policy['createdAt'] == application['createdAt']


def test_product_lifecycle_depeg_and_reactivate(
    instance,
    instanceOperator,
    investor,
    riskpool,
    productOwner,
    product,
    customer,
    protectedWallet,
):
    # fund riskpool
    create_bundle(
        instance,
        instanceOperator,
        investor,
        riskpool)

    # obtain data provider contract from product
    data_provider = contract_from_address(
        UsdcPriceDataProvider,
        product.getPriceDataProvider())

    # inject some initial price data
    for i in range(5):
        inject_and_process_data(product, data_provider, generate_next_data(i), productOwner)

    # check base line
    assert product.getTriggeredAt() == 0
    assert product.getDepeggedAt() == 0
    assert product.getDepegState() == STATE_PRODUCT['Active']

    # generate trigger data
    print('--- set price to trigger price ---')
    trigger_data = generate_next_data(
        5,
        price = TRIGGER_PRICE,
        delta_time = 12 * 3600)

    (round_id, price, timestamp) = trigger_data.split()[:3]
    timestamp = int(timestamp)
    timestamp_trigger = timestamp

    tx = inject_and_process_data(product, data_provider, trigger_data, productOwner)
    assert len(tx.events) == 3
    assert 'LogPriceDataTriggered' in tx.events
    assert 'LogDepegPriceEvent' in tx.events
    assert 'LogDepegProductPaused' in tx.events

    assert product.getTriggeredAt() == timestamp_trigger
    assert product.getDepeggedAt() == 0
    assert product.getDepegState() == STATE_PRODUCT['Paused']

    print('--- keep price at trigger price ---')
    trigger_data = generate_next_data(
        6,
        price = TRIGGER_PRICE,
        last_update=timestamp,
        delta_time = 23 * 3600)

    (round_id, price, timestamp) = trigger_data.split()[:3]
    timestamp = int(timestamp)

    assert timestamp > timestamp_trigger

    tx = inject_and_process_data(product, data_provider, trigger_data, productOwner)
    assert len(tx.events) == 2
    assert 'LogPriceDataProcessed' in tx.events
    assert 'LogDepegPriceEvent' in tx.events

    assert product.getTriggeredAt() == timestamp_trigger
    assert product.getDepeggedAt() == 0
    assert product.getDepegState() == STATE_PRODUCT['Paused']

    print('--- move into depeg state (stay triggered for >= 24h) ---')
    depeg_data = generate_next_data(
        7,
        price = TRIGGER_PRICE,
        last_update=timestamp,
        delta_time = 2 * 3600)

    (round_id, price, timestamp) = depeg_data.split()[:3]
    timestamp = int(timestamp)
    timestamp_depeg = timestamp

    tx = inject_and_process_data(product, data_provider, depeg_data, productOwner)

    # check that we're depegged now
    assert product.getTriggeredAt() == timestamp_trigger
    assert product.getDepeggedAt() == timestamp_depeg
    assert product.getDepegState() == STATE_PRODUCT['Depegged']

    assert len(tx.events) == 3
    assert 'LogPriceDataDepegged' in tx.events
    assert 'LogDepegPriceEvent' in tx.events

    assert tx.events['LogDepegPriceEvent']['priceId'] == round_id
    assert tx.events['LogDepegPriceEvent']['price'] == TRIGGER_PRICE
    assert tx.events['LogDepegPriceEvent']['triggeredAt'] == timestamp_trigger
    assert tx.events['LogDepegPriceEvent']['depeggedAt'] == timestamp_depeg
    assert tx.events['LogDepegPriceEvent']['createdAt'] == timestamp

    assert 'LogDepegProductDeactivated' in tx.events
    assert tx.events['LogDepegProductDeactivated']['priceId'] == round_id
    assert abs(int(tx.events['LogDepegProductDeactivated']['deactivatedAt']) - timestamp_depeg) <= 5

    # check that no polcy can be created in depeg state
    sumInsured = 10000
    durationDays = 60
    maxPremium = 750

    with brownie.reverts('ERROR:DP-011:PRODUCT_NOT_ACTIVE'):
        apply_for_policy(
            instance,
            instanceOperator,
            product,
            customer,
            protectedWallet,
            sumInsured,
            durationDays,
            maxPremium)

    print('--- remain in depeg state (with recovered price) ---')
    recovered_data = generate_next_data(
        8,
        price = RECOVERY_PRICE + 10,
        last_update=timestamp,
        delta_time = 10 * 3600)

    tx = inject_and_process_data(product, data_provider, recovered_data, productOwner)

    # check we're still in depeg state
    assert product.getTriggeredAt() == timestamp_trigger
    assert product.getDepeggedAt() == timestamp_depeg
    assert product.getDepegState() == STATE_PRODUCT['Depegged']

    # check that recovered price does not mean creating policies is working again
    with brownie.reverts('ERROR:DP-011:PRODUCT_NOT_ACTIVE'):
        apply_for_policy(
            instance,
            instanceOperator,
            product,
            customer,
            protectedWallet,
            sumInsured,
            durationDays,
            maxPremium)

    # reactivate price feed
    # verify that calling price feed reset is only allowed for owner
    with brownie.reverts('Ownable: caller is not the owner'):
        data_provider.resetDepeg({'from': instanceOperator})

    # check that owner can reset price feed
    tx = data_provider.resetDepeg({'from': productOwner})
    assert 'LogUsdcProviderResetDepeg' in tx.events

    # reactivate product
    # verify that calling reactivation is only allowed for owner
    with brownie.reverts('Ownable: caller is not the owner'):
        product.reactivateProduct({'from': instanceOperator})

    # check that owner can reactivate
    tx = product.reactivateProduct({'from': productOwner})
    assert 'LogDepegProductReactivated' in tx.events

    # check we're active and well again
    assert product.getTriggeredAt() == 0
    assert product.getDepeggedAt() == 0
    assert product.getDepegState() == STATE_PRODUCT['Active']

    # check that policies can be bought again
    process_id = apply_for_policy(
        instance,
        instanceOperator,
        product,
        customer,
        protectedWallet,
        sumInsured,
        durationDays,
        maxPremium)

    tx = history[-1]
    assert 'LogDepegPolicyCreated' in tx.events
    assert tx.events['LogDepegPolicyCreated']['processId'] == process_id


def inject_and_process_data(product, usdc_feeder, data, owner):
    inject_data(usdc_feeder, data, owner, sleep=True)
    return product.processLatestPriceInfo()
