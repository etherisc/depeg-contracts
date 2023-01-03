import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    chain,
    web3,
    InstanceRegistry,
    DIP,
    USD1,
    USD3
)

from scripts.const import ZERO_ADDRESS

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


def test_register_token_happy_path(
    instanceRegistry: InstanceRegistry,
    usd1: USD1,
    usd3: USD3,
    dip: DIP,
):
    assert instanceRegistry.tokens() == 0
    assert instanceRegistry.isRegisteredToken(usd1.address) == 0
    assert instanceRegistry.isRegisteredToken(usd1.address, web3.chain_id) == 0
    assert instanceRegistry.isRegisteredToken(usd1.address, web3.chain_id + 1) == 0

    # register token on same chain
    tx = instanceRegistry.registerToken(usd1.address)
    assert 'LogInstanceRegistryTokenRegistered' in tx.events
    assert tx.events['LogInstanceRegistryTokenRegistered']['token'] == usd1
    assert tx.events['LogInstanceRegistryTokenRegistered']['chainId'] == web3.chain_id
    assert tx.events['LogInstanceRegistryTokenRegistered']['state'] == 1 # Approved
    assert tx.events['LogInstanceRegistryTokenRegistered']['isNewToken'] == True

    assert instanceRegistry.tokens() == 1
    assert instanceRegistry.isRegisteredToken(usd1.address) == 1
    assert instanceRegistry.isRegisteredToken(usd1.address, web3.chain_id) == 1
    assert instanceRegistry.isRegisteredToken(usd1.address, web3.chain_id + 1) == 0

    (token_address, token_chain) = instanceRegistry.getTokenId(0)
    token = instanceRegistry.getTokenInfo(token_address).dict()
    print('token_id {}/{}'.format(token_address, token_chain))
    print('token {}'.format(token))

    # check token key
    assert token_address == usd1
    assert token_chain == web3.chain_id

    # check token attributes
    assert token['key'][0] == token_address
    assert token['key'][1] == token_chain
    assert token['decimals'] == usd1.decimals()
    assert token['symbol'] == usd1.symbol()
    assert token['createdAt'] > 0
    assert token['updatedAt'] == token['createdAt']

    chain.sleep(1)
    chain.mine(1)

    # re-register token on same chain
    tx = instanceRegistry.registerToken(usd1.address)
    assert 'LogInstanceRegistryTokenRegistered' in tx.events
    assert tx.events['LogInstanceRegistryTokenRegistered']['isNewToken'] == False

    token = instanceRegistry.getTokenInfo(token_address, token_chain).dict()
    assert token['updatedAt'] > token['createdAt']

    assert instanceRegistry.tokens() == 1
    assert instanceRegistry.isRegisteredToken(usd1.address) == 1
    assert instanceRegistry.isRegisteredToken(usd1.address, web3.chain_id) == 1
    assert instanceRegistry.isRegisteredToken(usd1.address, web3.chain_id + 1) == 0

    # register same token on some other chain
    some_other_chain = web3.chain_id + 1
    instanceRegistry.registerToken(
        usd1.address,
        some_other_chain,
        usd1.decimals(),
        usd1.symbol(),
    )

    assert instanceRegistry.tokens() == 2
    assert instanceRegistry.isRegisteredToken(usd1.address) == 1
    assert instanceRegistry.isRegisteredToken(usd1.address, web3.chain_id) == 1
    assert instanceRegistry.isRegisteredToken(usd1.address, web3.chain_id + 1) == 1

    # register other token on some other chain
    instanceRegistry.registerToken(
        usd3.address,
        some_other_chain,
        usd3.decimals(),
        usd3.symbol(),
    )

    assert instanceRegistry.tokens() == 3

    (token2_address, token2_chain) = instanceRegistry.getTokenId(2)
    token2 = instanceRegistry.getTokenInfo(token2_address, token2_chain).dict()
    print('token2_id {}/{}'.format(token2_address, token2_chain))
    print('token2 {}'.format(token2))

    # check token key
    assert token2_address == usd3
    assert token2_chain == some_other_chain

    # check token attributes
    assert token2['key'][0] == token2_address
    assert token2['key'][1] == token2_chain
    assert token2['decimals'] == usd3.decimals()
    assert token2['symbol'] == usd3.symbol()
    assert token2['createdAt'] > 0


def test_registration_failure_modes(
    instanceRegistry: InstanceRegistry,
    productOwner,
    usd1: USD1,
    usd3: USD3,
    dip: DIP
):
    assert instanceRegistry.tokens() == 0

    # attempt to register token as non-owner
    with brownie.reverts("Ownable: caller is not the owner"):
        instanceRegistry.registerToken(
            usd1.address,
            {'from':productOwner})

    with brownie.reverts("Ownable: caller is not the owner"):
        instanceRegistry.registerToken(
            usd1.address,
            web3.chain_id + 1,
            usd1.decimals(),
            usd1.symbol(),
            {'from':productOwner})

    # on same chain only registerToken(tokenAddress) may be used
    with brownie.reverts("ERROR:IRG-004:CALL_INVALID_FOR_SAME_CHAIN"):
        instanceRegistry.registerToken(
            usd1.address,
            web3.chain_id,
            usd1.decimals(),
            usd1.symbol()
        )

    assert instanceRegistry.tokens() == 0

    with brownie.reverts("ERROR:IRG-100:TOKEN_ADDRESS_ZERO"):
        instanceRegistry.registerToken(
            ZERO_ADDRESS,
            web3.chain_id + 1,
            usd1.decimals(),
            usd1.symbol()
        )

    assert instanceRegistry.tokens() == 0

    with brownie.reverts("ERROR:IRG-101:CHAIN_ID_ZERO"):
        instanceRegistry.registerToken(
            usd1.address,
            0,
            usd1.decimals(),
            usd1.symbol()
        )

    assert instanceRegistry.tokens() == 0

    with brownie.reverts("ERROR:IRG-102:DECIMALS_ZERO"):
        instanceRegistry.registerToken(
            usd1.address,
            web3.chain_id + 1,
            0,
            usd1.symbol()
        )

    assert instanceRegistry.tokens() == 0

    with brownie.reverts("ERROR:IRG-103:DECIMALS_TOO_LARGE"):
        instanceRegistry.registerToken(
            usd1.address,
            web3.chain_id + 1,
            dip.decimals() + 1,
            usd1.symbol()
        )

    assert instanceRegistry.tokens() == 0


def test_update_token_happy_path(
    instanceRegistry: InstanceRegistry,
    usd1: USD1
):
    instanceRegistry.registerToken(usd1.address)

    chain_id = web3.chain_id
    state_approved = 1
    state_suspended = 2

    tx = instanceRegistry.updateToken(
        usd1.address,
        chain_id,
        state_suspended
    )

    assert 'LogInstanceRegistryTokenStateUpdated' in tx.events
    assert tx.events['LogInstanceRegistryTokenStateUpdated']['token'] == usd1.address
    assert tx.events['LogInstanceRegistryTokenStateUpdated']['chainId'] == chain_id
    assert tx.events['LogInstanceRegistryTokenStateUpdated']['oldState'] == state_approved
    assert tx.events['LogInstanceRegistryTokenStateUpdated']['newState'] == state_suspended


def test_update_token_failure_modes(
    instanceRegistry: InstanceRegistry,
    usd1: USD1,
    usd3: USD3,
):
    instanceRegistry.registerToken(usd1.address)

    chain_id = web3.chain_id
    state_approved = 1
    state_undefined = 0

    with brownie.reverts('ERROR:IRG-011:TOKEN_STATE_INVALID'):
        instanceRegistry.updateToken(
            usd1.address,
            chain_id,
            state_undefined
        )

    state_suspended = 2

    with brownie.reverts('ERROR:IRG-001:TOKEN_NOT_REGISTERED'):
        instanceRegistry.updateToken(
            usd3.address,
            chain_id,
            state_suspended
        )
