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

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


def test_feeder_fixture(
    usdcFeeder: UsdcPriceDataProvider,
    usd1: USD1
):
    assert usdcFeeder.getAggregatorDecimals() == 8

    if web3.chain_id == GANACHE:
        assert usdcFeeder.getAggregatorAddress() == usdcFeeder.address
        assert usdcFeeder.getTokenAddress() == usd1.address
    elif web3.chain_id == MAINNET:
        assert usdcFeeder.getAggregatorAddress() == CHAINLINK_USDC_USD_FEED_MAINNET
        assert usdcFeeder.getTokenAddress() == USDC_CONTACT_ADDRESS
    else:
        print('ERROR chain_id {} not supported'.format(web3.chain_id))
        assert False


def test_test_data_ganache(usdcFeeder: UsdcPriceDataProvider):

    if web3.chain_id == GANACHE:
        print('on ganache we need to populate usdc aggregator data first')
        injectDataToFeeder(usdcFeeder)

    for i in range(len(USDC_CHAINLINK_DATA)):
        expectedData = data2roundData(i)
        actualData = usdcFeeder.getRoundData(expectedData[0])
        checkRound(actualData, expectedData)

    if web3.chain_id == GANACHE:
        expectedData = data2roundData(len(USDC_CHAINLINK_DATA) - 1)
        actualData = usdcFeeder.latestRoundData()
        checkRound(actualData, expectedData)


def checkRound(actualData, expectedData):
    (
        roundId,
        answer,
        startedAt,
        updatedAt,
        answeredInRound
    ) = actualData
    
    (
        expectedRoundId,
        expectedAnswer,
        expectedStartedAt,
        expectedUpdatedAt,
        expectedAnsweredInRound
    ) = expectedData

    assert roundId == expectedRoundId
    assert answer == expectedAnswer
    assert startedAt == expectedStartedAt
    assert updatedAt == expectedUpdatedAt
    assert answeredInRound == expectedAnsweredInRound


def injectDataToFeeder(usdcFeeder):
    for i in range(len(USDC_CHAINLINK_DATA)):
        (
            roundId,
            answer,
            startedAt,
            updatedAt,
            answeredInRound
        ) = data2roundData(i)

        usdcFeeder.setRoundData(
            roundId,
            answer,
            startedAt,
            updatedAt,
            answeredInRound
        )


def data2roundData(i:int):
    data = USDC_CHAINLINK_DATA[i]
    roundData = data.split()
    roundId = int(roundData[0])
    answer = int(roundData[1])
    startedAt = int(roundData[2])
    updatedAt = int(roundData[3])
    answeredInRound = int(roundData[4])

    return (
        roundId,
        answer,
        startedAt,
        updatedAt,
        answeredInRound
    )
