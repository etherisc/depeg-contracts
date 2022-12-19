import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    web3,
    GifStaking,
    DIP,
    USD1,
    USD3
)

from scripts.const import ZERO_ADDRESS
from scripts.setup import create_bundle

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


def test_register_token_happy_path(
    gifStaking: GifStaking,
    usd1: USD1,
    usd3: USD3,
    dip: DIP,
):
    assert gifStaking.tokens() == 0

    # register token on same chain
    gifStaking.registerToken(usd1.address)

    assert gifStaking.tokens() == 1

    token_key = gifStaking.getTokenKey(0).dict()
    token = gifStaking.getTokenInfo(token_key['token']).dict()
    print('token_key {}'.format(token_key))
    print('token {}'.format(token))

    # check token key
    assert token_key['token'] == usd1
    assert token_key['chainId'] == web3.chain_id

    # check token attributes
    assert token['key'][0] == token_key['token']
    assert token['key'][1] == token_key['chainId']
    assert token['decimals'] == usd1.decimals()
    assert token['symbol'] == usd1.symbol()
    assert token['createdAt'] > 0


    # register same token on some other chain
    some_other_chain = web3.chain_id + 1
    gifStaking.registerToken(
        usd1.address,
        some_other_chain,
        usd1.decimals(),
        usd1.symbol(),
    )

    assert gifStaking.tokens() == 2

    # register other token on some other chain
    gifStaking.registerToken(
        usd3.address,
        some_other_chain,
        usd3.decimals(),
        usd3.symbol(),
    )

    assert gifStaking.tokens() == 3

    token2_key = gifStaking.getTokenKey(2).dict()
    token2 = gifStaking.getTokenInfo(token2_key['token'], token2_key['chainId']).dict()
    print('token2_key {}'.format(token2_key))
    print('token2 {}'.format(token2))

    # check token key
    assert token2_key['token'] == usd3
    assert token2_key['chainId'] == some_other_chain

    # check token attributes
    assert token2['key'][0] == token2_key['token']
    assert token2['key'][1] == token2_key['chainId']
    assert token2['decimals'] == usd3.decimals()
    assert token2['symbol'] == usd3.symbol()
    assert token2['createdAt'] > 0


def test_registration_failure_modes(
    gifStaking: GifStaking,
    usd1: USD1,
    usd3: USD3,
    dip: DIP
):
    assert gifStaking.tokens() == 0

    # on same chain only registerToken(tokenAddress) may be used
    with brownie.reverts("ERROR:STK-005:TOKEN_ON_THIS_CHAIN"):
        gifStaking.registerToken(
            usd1.address,
            web3.chain_id,
            usd1.decimals(),
            usd1.symbol()
        )

    assert gifStaking.tokens() == 0

    gifStaking.registerToken(usd1.address)

    with brownie.reverts("ERROR:STK-100:TOKEN_ALREADY_REGISTERED"):
        gifStaking.registerToken(usd1.address)

    assert gifStaking.tokens() == 1

    with brownie.reverts("ERROR:STK-101:TOKEN_ADDRESS_ZERO"):
        gifStaking.registerToken(
            ZERO_ADDRESS,
            web3.chain_id + 1,
            usd1.decimals(),
            usd1.symbol()
        )

    assert gifStaking.tokens() == 1

    with brownie.reverts("ERROR:STK-102:CHAIN_ID_ZERO"):
        gifStaking.registerToken(
            usd1.address,
            0,
            usd1.decimals(),
            usd1.symbol()
        )

    assert gifStaking.tokens() == 1

    with brownie.reverts("ERROR:STK-103:DECIMALS_ZERO"):
        gifStaking.registerToken(
            usd1.address,
            web3.chain_id + 1,
            0,
            usd1.symbol()
        )

    assert gifStaking.tokens() == 1

    with brownie.reverts("ERROR:STK-104:DECIMALS_TOO_LARGE"):
        gifStaking.registerToken(
            usd1.address,
            web3.chain_id + 1,
            dip.decimals() + 1,
            usd1.symbol()
        )

    assert gifStaking.tokens() == 1
