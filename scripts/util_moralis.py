from moralis import evm_api

def get_erc20_balance(
    chain:str,
    token_address:str,
    wallet_address:str,
    timestamp:int,
    api_key:str
) -> int:

    block_number = get_block_number(chain, timestamp, api_key)

    balance_params = {
        'token_addresses': [token_address],
        'address': wallet_address,
        'to_block': block_number,
        'chain': chain }

    balance_response = evm_api.token.get_wallet_token_balances(
        api_key=api_key, params=balance_params)

    # [] returned prior to first balance tx
    if len(balance_response) == 0:
        return 0

    # normal case for address with some coin related balance
    if len(balance_response) == 1:
        return int(balance_response[0]['balance'])

    # should never happen
    assert False


def get_block_number(
    chain:str,
    timestamp:int,
    api_key:str
):
    block_params = {
        'date': str(timestamp),
        'chain': chain }

    block_response = evm_api.block.get_date_to_block(
        api_key=api_key, params=block_params)

    return block_response['block']
