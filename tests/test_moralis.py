import pytest

from moralis import evm_api

from scripts.util_moralis import (
    get_block_number,
    get_erc20_balance
)

PRICE_POINT_USDC = "36893488147419103255 100802792 1618719123 1618719123 36893488147419103255 2 23"

PRICE_POINT_TOKS = PRICE_POINT_USDC.split(' ')
PRICE_POINT_ROUND = int(PRICE_POINT_TOKS[0])
PRICE_POINT_PRICE = int(PRICE_POINT_TOKS[1])
PRICE_POINT_TIME = int(PRICE_POINT_TOKS[2])

PRICE_POINT_BLOCK_EXPECTED = 12261893
# verified /w etherscan https://etherscan.io/block/12261893
PRICE_POINT_BLOCK_TIMESTAMP_EXPECTED = '2021-04-18T04:12:03.000Z'

# chainlink usdc/usd price feed contract (only hands through getLatestRound)
# https://docs.chain.link/data-feeds/price-feeds/addresses
# https://etherscan.io/address/0x8fffffd4afb6115b954bd326cbe7b4ba576818f6#readContract
# EACAggregatorProxy is AggregatorProxy
#     AggregatorProxy is AggregatorV2V3Interface
#         Phase private currentPhase //   struct Phase { uint16 id; AggregatorV2V3Interface aggregator; }
#         function latestRoundData() ... = current.aggregator.latestRoundData();
#         function aggregator() ... return address(currentPhase.aggregator);
#             -> 0x789190466E21a8b78b8027866CBBDc151542A26C
#         function setAggregator(address _aggregator) ... currentPhase = Phase(id, AggregatorV2V3Interface(_aggregator));
#
# https://etherscan.io/address/0x789190466E21a8b78b8027866CBBDc151542A26C#code
# AccessControlledOffchainAggregator is OffchainAggregator
#     OffchainAggregator is Owned, OffchainAggregatorBilling, AggregatorV2V3Interface {
#         struct Transmission { int192 answer; /* 192 bits ought to be enough for anyone */ uint64 timestamp; }   
#         mapping(uint32 /* aggregator round ID */ => Transmission) internal s_transmissions;
#         function latestRoundData() ...  roundId = s_hotVars.latestAggregatorRoundId; ... Transmission memory transmission = s_transmissions[uint32(roundId)];
#         function transmit( ... transmission/price data set thourgh this function
#             this function also sorts various input price data and determines the median
#             the result of this proceess is likely the exact data that is retuned with get/latestRoundData  
#
# https://etherscan.io/tx/0x712a1e4825c99cbacc2aed603fdbe165729ca0f2b8f4051e1881526a29d982ef#eventlog
#     NewTransmission event /w answer 100802792 (matches with price)
#     NewRound event ?
#     AnswerUpdated event /w answerUpdated 1618719123 (matches with updatedAt)
 
TRANSMIT_TX_HASH = 'https://etherscan.io/tx/0x712a1e4825c99cbacc2aed603fdbe165729ca0f2b8f4051e1881526a29d982ef'


# test usdc setup on mumbay
MUMBAI_USDC_ADDRESS = '0x4B41f2599863F566b4E80318479b6bC5af2E5b0F'
MUMBAI_ACCOUNT_1 = '0x80404EA0e3C9092dDbbFD94AE6BE037504eD3d29'
MUMBAI_ACCOUNT_2 = '0x066d2f22a65f15EDE94D236C2CfF150dAb2ED01D'

# steps on mumbai (2.2.2023)
# usdc = USD1.deploy({'from':io}, publish_source=True)
# io.transfer(a1, 100000 * web3.eth.gas_price)
# io.transfer(a2, 100000 * web3.eth.gas_price)
# tx1 = usdc.transfer(a1, amount1, {'from':io})
# tx2 = usdc.transfer(a2, amount2, {'from':a1})

# timestamp -> blocknumber
MUMBAI_BLOCK_NUMBERS = {
    1675361221: 31666399, # block time wrong
    1675361291: 31666416,
    1675361813: 31666581,
    1675362009: 31666644,
}

# blocknumber -> usdc.balanceOf(MUMBAI_ACCOUNT_1)
MUMBAI_ACCOUNT_1_BALANCE_HISTORY = {
    31666399: 0,
    31666416: 987000000, # https://mumbai.polygonscan.com/tx/0xf6ef74391062eb91a663e726dad754e062925698133145c3071872eddf8bc8d0#eventlog
    31666581: 787000000, # https://mumbai.polygonscan.com/tx/0xea048946b787f53af42039dc5812051e1cb556690fc80909dba820acea455f28#eventlog
    31666644: 787000001, # https://mumbai.polygonscan.com/tx/0x6e0ab69c15527b2a42eeff5e2c278b5034e1ccfde293923ed1faf0e766b69f68#eventlog
}

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


def test_blocknumber_eth(moralis_api_key):

    params = {
        "date": str(PRICE_POINT_TIME),
        "chain": "eth"
    }

    response = evm_api.block.get_date_to_block(
        api_key=moralis_api_key,
        params=params)

    print('evm_api.block.get_date_to_block {}'.format(response))

    assert response['block'] == PRICE_POINT_BLOCK_EXPECTED
    assert response['timestamp'] == PRICE_POINT_TIME
    assert response['block_timestamp'] == PRICE_POINT_BLOCK_TIMESTAMP_EXPECTED


def test_erc20_balance_mumbai_single(moralis_api_key, usd1):

    # step 1) timestamp -> blocknumber
    timestamp = 1675361813

    params = { 'date': str(timestamp), 'chain': 'mumbai' }
    response1 = evm_api.block.get_date_to_block(
        api_key=moralis_api_key,
        params=params)

    block_number = response1['block']
    assert block_number == 31666581

    # step 2) blocknumber -> balance for block number
    params = {
        'token_addresses': [MUMBAI_USDC_ADDRESS],
        'address': MUMBAI_ACCOUNT_1,
        'to_block': block_number,
        'chain': 'mumbai'
    }

    response2 = evm_api.token.get_wallet_token_balances(
        api_key=moralis_api_key,
        params=params)

    assert len(response2) == 1

    usdc_response = response2[0]
    assert usdc_response['symbol'] == usd1.symbol()
    assert usdc_response['decimals'] == usd1.decimals()
    assert usdc_response['balance'] == str(787000000)


def test_blocknumber_mumbai(moralis_api_key):

    assert len(MUMBAI_BLOCK_NUMBERS) == 4
    checks = 0

    for (timestamp, block_number_expected) in MUMBAI_BLOCK_NUMBERS.items():
        block_number = get_block_number(
            'mumbai', 
            timestamp, 
            moralis_api_key)

        assert block_number == block_number_expected
        checks += 1

    assert checks == len(MUMBAI_BLOCK_NUMBERS)


def test_erc20_balance_mumbai(moralis_api_key):

    assert len(MUMBAI_BLOCK_NUMBERS) == 4
    assert len(MUMBAI_ACCOUNT_1_BALANCE_HISTORY) == len(MUMBAI_BLOCK_NUMBERS)
    checks = 0

    for (timestamp, block_number) in MUMBAI_BLOCK_NUMBERS.items():

        balance = get_erc20_balance(
            'mumbai',
            MUMBAI_USDC_ADDRESS,
            MUMBAI_ACCOUNT_1,
            timestamp,
            moralis_api_key)

        expected_balance = MUMBAI_ACCOUNT_1_BALANCE_HISTORY[block_number]
        assert balance == expected_balance
        checks += 1

    assert checks == len(MUMBAI_BLOCK_NUMBERS)


# def get_erc20_balance(
#     chain:str,
#     token_address:str,
#     wallet_address:str,
#     timestamp:int,
#     api_key:str
# ) -> int:

#     block_number = get_block_number(chain, timestamp, api_key)

#     balance_params = {
#         'token_addresses': [token_address],
#         'address': wallet_address,
#         'to_block': block_number,
#         'chain': chain }

#     balance_response = evm_api.token.get_wallet_token_balances(
#         api_key=api_key, params=balance_params)

#     # [] returned prior to first balance tx
#     if len(balance_response) == 0:
#         return 0

#     # normal case for address with some coin related balance
#     if len(balance_response) == 1:
#         return int(balance_response[0]['balance'])

#     # should never happen
#     assert False


# def get_block_number(
#     chain:str,
#     timestamp:int,
#     api_key:str
# ):
#     block_params = {
#         'date': str(timestamp),
#         'chain': chain }

#     block_response = evm_api.block.get_date_to_block(
#         api_key=api_key, params=block_params)

#     return block_response['block']
