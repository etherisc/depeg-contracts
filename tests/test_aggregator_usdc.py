import brownie
import pytest

from brownie import (
    web3,
    UsdcPriceDataProvider,
    USD1,
)

MAINNET = 1
GANACHE = 1337

USDC_CONTACT_ADDRESS = '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'
CHAINLINK_USDC_USD_FEED_MAINNET = '0x8fFfFfd4AfB6115b954Bd326cbe7B4BA576818f6'

# actual chainlink aggregator data, may be validated against
# https://etherscan.io/address/0x8fFfFfd4AfB6115b954Bd326cbe7B4BA576818f6#readContract
USDC_CHAINLINK_DATA = [
    # roundId             qnswer    startedAt  updatedAt  answeredInRound
    '36893488147419103822 100000017 1660297306 1660297306 36893488147419103822',
    '36893488147419103823 100008784 1660383738 1660383738 36893488147419103823',
    '36893488147419103824 100000000 1660383820 1660383820 36893488147419103824',
    '36893488147419103825 99985387 1660470242 1660470242 36893488147419103825',
    '36893488147419103826 99989424 1660556656 1660556656 36893488147419103826',
    '36893488147419103827 100017933 1660643065 1660643065 36893488147419103827',
    '36893488147419103828 100007204 1660729494 1660729494 36893488147419103828',
    '36893488147419103829 100000000 1660815929 1660815929 36893488147419103829',
    '36893488147419103830 100002388 1660902349 1660902349 36893488147419103830',
    '36893488147419103831 100000554 1660988749 1660988749 36893488147419103831',
    '36893488147419103832 99990785 1661075158 1661075158 36893488147419103832',
]

# for usdc/usd quality promise by chainlink see https://docs.chain.link/data-feeds/price-feeds/addresses
# 'hacked' price feed to force heatbeat violation
# ie duration between consecuteve createdAt/updatedAt timestamps > 24h + margin
USDC_CHAINLINK_DATA_HEARTBEAT_VIOLATED = [
    '36893488147419103822 100000017 1660297306 1660297306 36893488147419103822',
    '36893488147419103823 100008784 1660383807 1660383807 36893488147419103823',
    '36893488147419103824 100000000 1660470308 1660470308 36893488147419103824',
    '36893488147419103825 99985387 1660506308 1660506308 36893488147419103825',
]

# 'hacked' price feed to force deviation violation
# ie price difference between two rounds larger than 0.25%
USDC_CHAINLINK_DATA_DEVIATION_VIOLATED = [
    '36893488147419103822 100000017 1660297306 1660297306 36893488147419103822',
    '36893488147419103823 100260000 1660383738 1660383738 36893488147419103823',
    '36893488147419103824 100000000 1660383820 1660383820 36893488147419103824',
    '36893488147419103825 99985387 1660470242 1660470242 36893488147419103825',
]

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


def test_feeder_fixture(
    usdc_feeder: UsdcPriceDataProvider,
    usd1: USD1
):
    assert usdc_feeder.getDecimals() == 8
    assert usdc_feeder.getHeartbeat() == 24 * 3600
    assert usdc_feeder.getDeviation() == 0.0025 * 10**8

    if web3.chain_id == GANACHE:
        assert usdc_feeder.getAggregatorAddress() == usdc_feeder.address
        assert usdc_feeder.getToken() == usd1
    elif web3.chain_id == MAINNET:
        assert usdc_feeder.getAggregatorAddress() == CHAINLINK_USDC_USD_FEED_MAINNET
        assert usdc_feeder.getToken().address == USDC_CONTACT_ADDRESS
    else:
        print('ERROR chain_id {} not supported'.format(web3.chain_id))
        assert False


def test_test_data(usdc_feeder: UsdcPriceDataProvider):

    if web3.chain_id == GANACHE:
        print('on ganache we need to populate usdc aggregator data first')

        for data in USDC_CHAINLINK_DATA:
            inject_data(usdc_feeder, data)

    for data in USDC_CHAINLINK_DATA:
        expected_data = data_to_round_data(data)
        round_id = expected_data[0]
        actual_data = usdc_feeder.getRoundData(round_id)
        check_round(actual_data, expected_data)

    if web3.chain_id == GANACHE:
        expected_data = data_to_round_data(USDC_CHAINLINK_DATA[-1])
        actual_data = usdc_feeder.latestRoundData()
        check_round(actual_data, expected_data)


def test_price_data_valid(usdc_feeder: UsdcPriceDataProvider):

    if web3.chain_id != GANACHE:
        print('unsupported test case for chain_id {}'.format(web3.chain_id))

    for i, data in enumerate(USDC_CHAINLINK_DATA):
        inject_data(usdc_feeder, data)

        price_id = data_to_round_data(data)[0]
        tx = usdc_feeder.getPriceInfo(price_id)
        price_info = tx.return_value.dict()
        print('price_info[{}] {}'.format(i, price_info))

        if i == 0:
            assert price_info['compliance'] == 0 # Initializing
            assert price_info['stability'] == 0 # Initializing
        else:
            assert price_info['compliance'] == 1 # Valid
            assert price_info['stability'] == 1 # Stable


def test_price_data_heatbeat_error(usdc_feeder: UsdcPriceDataProvider):

    if web3.chain_id != GANACHE:
        print('unsupported test case for chain_id {}'.format(web3.chain_id))

    for i, data in enumerate(USDC_CHAINLINK_DATA_HEARTBEAT_VIOLATED):
        inject_data(usdc_feeder, data)

        price_id = data_to_round_data(data)[0]
        tx = usdc_feeder.getPriceInfo(price_id)

        print('LogPriceDataHeartbeatExceeded in tx.events {} events {}'.format(
            'LogPriceDataHeartbeatExceeded' in tx.events,
            tx.events
        ))

        price_info = tx.return_value.dict()
        print('price_info[{}] {}'.format(i, price_info))

        if i == 0:
            assert 'LogPriceDataDeviationExceeded' not in tx.events
            assert 'LogPriceDataHeartbeatExceeded' not in tx.events
            assert price_info['compliance'] == 0 # Initializing
            assert price_info['stability'] == 0 # Initializing
        elif i == 1:
            assert 'LogPriceDataDeviationExceeded' not in tx.events
            assert 'LogPriceDataHeartbeatExceeded' in tx.events
            assert price_info['compliance'] == 2 # FailedOnce
            assert price_info['stability'] == 1 # Stable
        elif i == 2:
            assert 'LogPriceDataDeviationExceeded' not in tx.events
            assert 'LogPriceDataHeartbeatExceeded' in tx.events
            assert price_info['compliance'] == 3 # FailedMultipleTimes
            assert price_info['stability'] == 1 # Stable
        elif i == 3:
            assert 'LogPriceDataDeviationExceeded' not in tx.events
            assert 'LogPriceDataHeartbeatExceeded' not in tx.events
            assert price_info['compliance'] == 1 # Valid
            assert price_info['stability'] == 1 # Stable


def test_price_data_deviation_error(usdc_feeder: UsdcPriceDataProvider):

    if web3.chain_id != GANACHE:
        print('unsupported test case for chain_id {}'.format(web3.chain_id))

    for i, data in enumerate(USDC_CHAINLINK_DATA_DEVIATION_VIOLATED):
        inject_data(usdc_feeder, data)

        price_id = data_to_round_data(data)[0]
        tx = usdc_feeder.getPriceInfo(price_id)

        print('LogPriceDataDeviationExceeded in tx.events {} events {}'.format(
            'LogPriceDataDeviationExceeded' in tx.events,
            tx.events
        ))

        price_info = tx.return_value.dict()
        print('price_info[{}] {}'.format(i, price_info))

        if i == 0:
            assert 'LogPriceDataHeartbeatExceeded' not in tx.events
            assert 'LogPriceDataDeviationExceeded' not in tx.events
            assert price_info['compliance'] == 0 # Initializing
            assert price_info['stability'] == 0 # Initializing
        elif i == 1:
            assert 'LogPriceDataHeartbeatExceeded' not in tx.events
            assert 'LogPriceDataDeviationExceeded' in tx.events
            assert price_info['compliance'] == 2 # FailedOnce
            assert price_info['stability'] == 1 # Stable
        elif i == 2:
            assert 'LogPriceDataHeartbeatExceeded' not in tx.events
            assert 'LogPriceDataDeviationExceeded' in tx.events
            assert price_info['compliance'] == 3 # FailedMultipleTimes
            assert price_info['stability'] == 1 # Stable
        elif i == 3:
            assert 'LogPriceDataHeartbeatExceeded' not in tx.events
            assert 'LogPriceDataDeviationExceeded' not in tx.events
            assert price_info['compliance'] == 1 # Valid
            assert price_info['stability'] == 1 # Stable


def check_round(actual_data, expected_data):
    (
        round_id,
        answer,
        started_at,
        updated_at,
        answered_in_round
    ) = actual_data

    (
        expected_round_id,
        expected_answer,
        expected_started_at,
        expected_updated_at,
        expected_answered_in_round
    ) = expected_data

    assert round_id == expected_round_id
    assert answer == expected_answer
    assert started_at == expected_started_at
    assert updated_at == expected_updated_at
    assert answered_in_round == expected_answered_in_round


def inject_data(usdc_feeder, data):
    (
        round_id,
        answer,
        started_at,
        updated_at,
        answered_in_round
    ) = data_to_round_data(data)

    usdc_feeder.setRoundData(
        round_id,
        answer,
        started_at,
        updated_at,
        answered_in_round
    )


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
