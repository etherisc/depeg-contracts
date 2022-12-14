import brownie
import pytest
import random

from datetime import datetime

from brownie import (
    chain,
    UsdcPriceDataProvider,
)

from scripts.setup import (
    create_bundle, 
    apply_for_policy,
)

from scripts.util import (
    contract_from_address
)

ROUND_ID_INITIAL = 36893488147419103822

PERFECT_PRICE = 10**8 # == 10**usdc.decimals()
TRIGGER_PRICE = int(0.995 * PERFECT_PRICE)
RECOVERY_PRICE = int(0.999 * PERFECT_PRICE)

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
    productOwner,
    product,
    usd1
):
    # check initial lifecycle state
    assert product.getDepegState() == 0 #  enum DepegState { Active, Paused, Deactivated }

    # initially no new price info expected
    info = product.hasNewPriceInfo().dict()
    print('hasNewPriceInfo {}'.format(info))

    assert info['newInfoAvailable'] == False
    assert info['priceId'] == 0
    assert info['timeSinceLastUpdate'] == 0

    # get and check price data provider contract
    price_data_provider = contract_from_address(UsdcPriceDataProvider, product.getPriceDataProvider())
    assert price_data_provider.getToken() == usd1

    # create initial data point and inject to pr
    data = generate_next_data(0)
    inject_data(price_data_provider, data, productOwner)

    # check again
    info = product.hasNewPriceInfo().dict()
    print('hasNewPriceInfo {}'.format(info))

    (price_id, price, timestamp) = data.split()[:3]
    assert info['newInfoAvailable'] == True
    assert info['priceId'] == price_id
    assert info['timeSinceLastUpdate'] > 0

    # process new price info
    tx = product.updatePriceInfo()

    # check price update log entry
    assert len(tx.events) == 1
    assert 'LogDepegPriceInfoUpdated' in tx.events
    assert tx.events['LogDepegPriceInfoUpdated']['priceId'] == price_id
    assert tx.events['LogDepegPriceInfoUpdated']['price'] == price

    # check return value of price info getter
    price_info = product.getLatestPriceInfo().dict()
    print('priceInfo {}'.format(price_info))

    assert price_info['id'] == price_id
    assert price_info['price'] == price
    assert price_info['compliance'] == 0
    assert price_info['triggeredAt'] == 0
    assert price_info['depeggedAt'] == 0
    assert price_info['createdAt'] == timestamp

    # check depeg state is still fine
    assert product.getDepegState() == 0 #  enum DepegState { Active, Paused, Deactivated }


def test_product_lifecycle_trigger(
    instance,
    instanceOperator,
    investor,
    riskpool,
    productOwner,
    product,
    customer,
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
        inject_and_update_data(product, data_provider, generate_next_data(i), productOwner)

    # check base line
    assert product.getDepegState() == 0 #  enum DepegState { Active, Paused, Deactivated }

    price_info = product.getLatestPriceInfo().dict()
    print('priceInfo {}'.format(price_info))

    # generate pre-trigger and trigger data
    print('--- test price at depeg trigger threshold + 1 ---')
    above_trigger_data = generate_next_data(
        5,
        price = TRIGGER_PRICE + 1,
        delta_time = 12 * 3600
        )

    tx = inject_and_update_data(product, data_provider, above_trigger_data, productOwner)
    assert 'LogDepegPriceInfoUpdated' in tx.events
    assert 'LogDepegProductPaused' not in tx.events
    assert product.getDepegState() == 0 #  enum DepegState { Active, Paused, Deactivated }

    price_info = product.getLatestPriceInfo().dict()
    print('priceInfo {}'.format(price_info))

    # verify that it's still possible to underwrite a new policy
    sumInsured = 10000
    durationDays = 60
    maxPremium = 750

    process_id_1 = apply_for_policy(
        instance,
        instanceOperator,
        product,
        customer,
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

    tx = inject_and_update_data(product, data_provider, trigger_data, productOwner)
    assert len(tx.events) == 3
    assert 'LogPriceDataTriggered' in tx.events
    assert 'LogDepegPriceInfoUpdated' in tx.events
    assert tx.events['LogDepegPriceInfoUpdated']['priceId'] == round_id
    assert tx.events['LogDepegPriceInfoUpdated']['price'] == price
    assert tx.events['LogDepegPriceInfoUpdated']['triggeredAt'] == timestamp
    assert tx.events['LogDepegPriceInfoUpdated']['depeggedAt'] == 0
    assert tx.events['LogDepegPriceInfoUpdated']['createdAt'] == timestamp

    assert 'LogDepegProductPaused' in tx.events
    assert tx.events['LogDepegProductPaused']['priceId'] == round_id
    assert abs(tx.events['LogDepegProductPaused']['pausedAt'] - timestamp) <= 5

    price_info = product.getLatestPriceInfo().dict()
    print('priceInfo {}'.format(price_info))

    assert product.getDepegState() == 1 #  enum DepegState { Active, Paused, Deactivated }

    # verify that it's not possible to underwrite a new policy
    with brownie.reverts('ERROR:DP-010:PRODUCT_NOT_ACTIVE'):
        apply_for_policy(
            instance,
            instanceOperator,
            product,
            customer,
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
        inject_and_update_data(product, data_provider, generate_next_data(i), productOwner)

    # check base line
    assert product.getDepegState() == 0 #  enum DepegState { Active, Paused, Deactivated }

    # generate trigger data
    print('--- triggering depeg product ---')
    trigger_data = generate_next_data(
        5,
        price = TRIGGER_PRICE,
        delta_time = 12 * 3600)

    (round_id, price, timestamp) = trigger_data.split()[:3]
    timestamp = int(timestamp)

    tx = inject_and_update_data(product, data_provider, trigger_data, productOwner)
    assert len(tx.events) == 4
    assert 'LogPriceDataTriggered' in tx.events

    assert product.getDepegState() == 1 #  enum DepegState { Active, Paused, Deactivated }

    # verify that it's not possible to underwrite a new policy
    sumInsured = 10000
    durationDays = 60
    maxPremium = 750

    with brownie.reverts('ERROR:DP-010:PRODUCT_NOT_ACTIVE'):
        apply_for_policy(
            instance,
            instanceOperator,
            product,
            customer,
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

    tx = inject_and_update_data(product, data_provider, trigger_data, productOwner)
    assert len(tx.events) == 1
    assert 'LogDepegPriceInfoUpdated' in tx.events

    assert product.getDepegState() == 1 #  enum DepegState { Active, Paused, Deactivated }

    with brownie.reverts('ERROR:DP-010:PRODUCT_NOT_ACTIVE'):
        apply_for_policy(
            instance,
            instanceOperator,
            product,
            customer,
            sumInsured,
            durationDays,
            maxPremium)

    # new data (recover triggered state)
    trigger_data = generate_next_data(
        7,
        price = RECOVERY_PRICE,
        last_update=timestamp,
        delta_time = 11 * 3600)

    (round_id, price, timestamp) = trigger_data.split()[:3]
    timestamp = int(timestamp)

    tx = inject_and_update_data(product, data_provider, trigger_data, productOwner)
    assert len(tx.events) == 4
    assert 'LogPriceDataRecovered' in tx.events
    assert 'LogDepegPriceInfoUpdated' in tx.events
    assert 'LogDepegProductUnpaused' in tx.events
    assert tx.events['LogDepegProductUnpaused']['priceId'] == round_id
    assert abs(tx.events['LogDepegProductUnpaused']['unpausedAt'] - timestamp) <= 5

    # check that depeg state is active again
    assert product.getDepegState() == 0 #  enum DepegState { Active, Paused, Deactivated }

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


def test_product_lifecycle_depeg(
    instance,
    instanceOperator,
    investor,
    riskpool,
    productOwner,
    product,
    customer,
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
        inject_and_update_data(product, data_provider, generate_next_data(i), productOwner)

    # check base line
    assert product.getDepegState() == 0 #  enum DepegState { Active, Paused, Deactivated }

    # generate trigger data
    print('--- set price to trigger price ---')
    trigger_data = generate_next_data(
        5,
        price = TRIGGER_PRICE,
        delta_time = 12 * 3600)

    (round_id, price, timestamp) = trigger_data.split()[:3]
    timestamp = int(timestamp)
    timestemp_trigger = timestamp

    tx = inject_and_update_data(product, data_provider, trigger_data, productOwner)
    assert len(tx.events) == 4
    assert 'LogPriceDataTriggered' in tx.events

    assert product.getDepegState() == 1 #  enum DepegState { Active, Paused, Deactivated }

    print('--- keep price at trigger price ---')
    trigger_data = generate_next_data(
        6,
        price = TRIGGER_PRICE,
        last_update=timestamp,
        delta_time = 23 * 3600)

    (round_id, price, timestamp) = trigger_data.split()[:3]
    timestamp = int(timestamp)

    tx = inject_and_update_data(product, data_provider, trigger_data, productOwner)
    assert len(tx.events) == 1
    assert product.getDepegState() == 1 #  enum DepegState { Active, Paused, Deactivated }

    print('--- move into depeg state (stay triggered for >= 24h) ---')
    trigger_data = generate_next_data(
        7,
        price = TRIGGER_PRICE,
        last_update=timestamp,
        delta_time = 2 * 3600)

    (round_id, price, timestamp) = trigger_data.split()[:3]
    timestamp = int(timestamp)
    timestamp_depeg = timestamp

    tx = inject_and_update_data(product, data_provider, trigger_data, productOwner)
    assert product.getDepegState() == 2 #  enum DepegState { Active, Paused, Deactivated }

    assert len(tx.events) == 3
    assert 'LogPriceDataDepegged' in tx.events
    assert 'LogDepegPriceInfoUpdated' in tx.events
    assert tx.events['LogDepegPriceInfoUpdated']['priceId'] == round_id
    assert tx.events['LogDepegPriceInfoUpdated']['price'] == TRIGGER_PRICE
    assert tx.events['LogDepegPriceInfoUpdated']['triggeredAt'] == timestemp_trigger
    assert tx.events['LogDepegPriceInfoUpdated']['depeggedAt'] == timestamp_depeg
    assert tx.events['LogDepegPriceInfoUpdated']['createdAt'] == timestamp

    assert 'LogDepegProductDeactivated' in tx.events
    assert tx.events['LogDepegProductDeactivated']['priceId'] == round_id
    assert abs(int(tx.events['LogDepegProductDeactivated']['deactivatedAt']) - timestamp_depeg) <= 5

    # check that no polcy can be created in depeg state
    sumInsured = 10000
    durationDays = 60
    maxPremium = 750

    with brownie.reverts('ERROR:DP-010:PRODUCT_NOT_ACTIVE'):
        apply_for_policy(
            instance,
            instanceOperator,
            product,
            customer,
            sumInsured,
            durationDays,
            maxPremium)

    print('--- remain in depeg state (with recovered price) ---')
    trigger_data = generate_next_data(
        8,
        price = RECOVERY_PRICE + 10,
        last_update=timestamp,
        delta_time = 10 * 3600)

    tx = inject_and_update_data(product, data_provider, trigger_data, productOwner)
    # check we're still in depeg state
    assert product.getDepegState() == 2 #  enum DepegState { Active, Paused, Deactivated }

    # check that recovered price does not mean creating policies is working again
    with brownie.reverts('ERROR:DP-010:PRODUCT_NOT_ACTIVE'):
        apply_for_policy(
            instance,
            instanceOperator,
            product,
            customer,
            sumInsured,
            durationDays,
            maxPremium)


def inject_and_update_data(product, usdc_feeder, data, owner):
    inject_data(usdc_feeder, data, owner)
    return product.updatePriceInfo()


def inject_data(usdc_feeder, data, owner):
    (
        round_id,
        answer,
        started_at,
        updated_at,
        answered_in_round
    ) = data_to_round_data(data)

    # advance chain clock to updated_at
    sleep_time = updated_at - chain.time()
    assert sleep_time >= 0

    chain.sleep(sleep_time)
    chain.mine(1)

    usdc_feeder.setRoundData(
        round_id,
        answer,
        started_at,
        updated_at,
        answered_in_round,
        {'from': owner}
    )


def generate_next_data(
    i,
    price=None,
    last_update=None,
    delta_time=None
):
    round_id = ROUND_ID_INITIAL + i
    now = datetime.now()
    timestamp = int(datetime.timestamp(now))

    if price is None:
        price = PERFECT_PRICE + random.randint(-10, 10)

    if last_update is None:
        last_update = timestamp if i == 0 else timestamp + (i - 1) * 24 * 3600
    
    if delta_time is None:
        delta_time = 24 * 3600 + random.randint(-120, 120)

    startedAt = last_update if i == 0 else last_update + delta_time
    
    data = '{} {} {} {} {}'.format(
            round_id, # roundId
            price, # answer
            startedAt, # startedAt
            startedAt, # updatedAt
            round_id # answeredInRound
    )

    print('next_data[{}] {} - {}'.format(i, data, datetime.fromtimestamp(startedAt)))

    return data


def data_to_round_data(data):
    round_data = data.split()
    round_id = int(round_data[0])
    answer = int(round_data[1])
    started_at = int(round_data[2])
    updated_at = int(round_data[3])
    answered_in_round = int(round_data[4])

    return (
        round_id,
        answer,
        started_at,
        updated_at,
        answered_in_round
    )
