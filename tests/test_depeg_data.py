import csv
import pytest
import random

from brownie import (
    chain,
    interface,
    web3,
    UsdcPriceDataProvider,
    USD1,
)

from brownie.network.account import Account

from scripts.util import contract_from_address

MAINNET = 1
CHAINLINK_USDC_USD_FEED_MAINNET = '0x8fFfFfd4AfB6115b954Bd326cbe7B4BA576818f6'

DEPEG_DATA_230312 = './tests/data/usdc_usd_depeg_230312.csv'

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass

# use the settings below to run this against mainnet
# brownie test tests/test_depeg_data.py::test_depeg_data_on_mainnet --interactive --network=mainnet-fork
def test_depeg_data_on_mainnet(usdc_feeder: UsdcPriceDataProvider):

    if web3.chain_id != MAINNET:
        print('test case only relevant when executed on mainnet')
        return

    assert usdc_feeder.isMainnetProvider()

    chainlink_aggregator = contract_from_address(
        interface.AggregatorV2V3Interface,
        usdc_feeder.getChainlinkAggregatorAddress())

    assert chainlink_aggregator.address == CHAINLINK_USDC_USD_FEED_MAINNET

    # get expected data
    (header, keys, data) = get_price_data(DEPEG_DATA_230312)
    assert len(keys) == 400
    assert keys[0] == '36893488147419103978'
    assert keys[-1] == '36893488147419104377'

    # sample random subset
    checks = 30
    check_set = set(range(len(keys)))
    sample_set = random.sample(check_set, checks)

    for sample in sample_set:
        key = keys[sample]
        check_sample(key, data, chainlink_aggregator)


def test_usdc_depeg_run(
    usdc_feeder: UsdcPriceDataProvider,
    productOwner: Account
):

    if web3.chain_id == MAINNET:
        print('test case only relevant when executed on ganache')
        return

    (header, keys, data) = get_price_data(DEPEG_DATA_230312)
    assert len(keys) == 400
    assert keys[0] == '36893488147419103978'
    assert keys[-1] == '36893488147419104377'

    trigger_id = 36893488147419104091
    trigger_value = 99209183
    triggered_at = 1678497491

    depeg_id = 36893488147419104334
    depeg_value = 97530000
    depegged_at = 1678583975

    event_update = 1
    event_trigger = 2
    event_recover = 3
    event_depeg = 4

    for i, key in enumerate(keys):
        inject_data(usdc_feeder, key, data, productOwner)

        (new_event, price_info, time_since) = usdc_feeder.isNewPriceInfoEventAvailable()

        pi = price_info.dict()
        round_id = pi['id']

        # initial check (5 is kind of arbitrary)
        if i == 5:
            depeg_price = usdc_feeder.getDepegPriceInfo().dict()
            assert depeg_price['id'] == 0
            assert depeg_price['depeggedAt'] == 0
            assert depeg_price['price'] == 0

        # check before trigger event
        if round_id < trigger_id:
            assert new_event is False
            assert pi['eventType'] == event_update
            assert pi['triggeredAt'] == 0
            assert pi['depeggedAt'] == 0
            
            assert usdc_feeder.getTriggeredAt() == 0
            assert usdc_feeder.getDepeggedAt() == 0

        # check trigger event
        elif round_id == trigger_id:
            assert new_event is True
            assert pi['eventType'] == event_trigger
            assert pi['triggeredAt'] == triggered_at
            assert pi['depeggedAt'] == 0
            assert pi['price'] == trigger_value

            usdc_feeder.processLatestPriceInfo()
            (new_event, price_info, time_since) = usdc_feeder.isNewPriceInfoEventAvailable()

            assert new_event is False
            assert usdc_feeder.getTriggeredAt() == triggered_at
            assert usdc_feeder.getDepeggedAt() == 0

            depeg_price = usdc_feeder.getDepegPriceInfo().dict()
            assert depeg_price['id'] == 0
            assert depeg_price['depeggedAt'] == 0
            assert depeg_price['price'] == 0
        else:
            # check before depeg event
            if round_id < depeg_id:
                assert new_event is False
                assert pi['eventType'] == event_update
                assert pi['triggeredAt'] == triggered_at
                assert pi['depeggedAt'] == 0

                assert usdc_feeder.getTriggeredAt() == triggered_at
                assert usdc_feeder.getDepeggedAt() == 0
            # check depeg event
            elif round_id == depeg_id:
                assert new_event is True
                assert pi['eventType'] == event_depeg
                assert pi['triggeredAt'] == triggered_at
                assert pi['depeggedAt'] == depegged_at
                assert pi['price'] == depeg_value

                usdc_feeder.processLatestPriceInfo()
                (new_event, price_info, time_since) = usdc_feeder.isNewPriceInfoEventAvailable()

                assert new_event is False
                assert usdc_feeder.getTriggeredAt() == triggered_at
                assert usdc_feeder.getDepeggedAt() == depegged_at

                depeg_price = usdc_feeder.getDepegPriceInfo().dict()
                assert depeg_price['id'] == depeg_id
                assert depeg_price['depeggedAt'] == depegged_at
                assert depeg_price['price'] == depeg_value
            else:
                assert new_event is False
                assert pi['eventType'] == event_update
                assert pi['triggeredAt'] == triggered_at
                assert pi['depeggedAt'] == depegged_at

    depeg_price = usdc_feeder.getDepegPriceInfo().dict()
    assert depeg_price['id'] == depeg_id
    assert depeg_price['depeggedAt'] == depegged_at
    assert depeg_price['price'] == depeg_value


def inject_data(
    usdc_feeder,
    key,
    data,
    owner,
    sleep=False
):
    (
        round_id,
        answer,
        started_at,
        updated_at,
        answered_in_round
    ) = to_round_data(key, data)

    if sleep:
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
        {'from': owner})


def to_round_data(key, data):
    round_id = key
    answer = data[key]['answer']
    updated_at = data[key]['updatedAt']

    return (
        round_id,
        answer,
        updated_at,
        updated_at,
        round_id
    )


def check_sample(key, data, chainlink):
    expected = data[key]
    actual = chainlink.getRoundData(key).dict()

    assert actual['answeredInRound'] == key
    assert actual['answer'] == expected['answer']
    assert actual['updatedAt'] == expected['updatedAt']


def get_price_data(csv_file_name, comment_chars=['#', '/']):
    header = []
    keys = []
    data = {}

    with open(csv_file_name, 'r') as csv_file:
        csv_reader = csv.reader(csv_file)
        header = None

        for row in csv_reader:
            key = row[0]

            # skip comment lines
            if key[0] not in comment_chars:
                if not header:
                    header = row
                else:
                    keys.append(key)
                    row_data = {}

                    for i, attribute in enumerate(header[1:]):
                        row_data[attribute] = row[i+1]

                    data[key] = row_data

    return (header, keys, data)