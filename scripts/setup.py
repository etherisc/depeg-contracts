from brownie.network.account import Account

from brownie import (
    interface,
    DepegProduct,
    DepegRiskpool
)

from scripts.instance_test import GifInstance
from scripts.util import contract_from_address


DEFAULT_BUNDLE_FUNDING = 100000
DEFAULT_MIN_SUM_INSURED =  5000
DEFAULT_MAX_SUM_INSURED = 20000
DEFAULT_MIN_DURATION_DAYS =  30
DEFAULT_MAX_DURATION_DAYS =  90
DEFAULT_APR_PERCENTAGE =    5.0

DEFAULT_SUM_INSURED = 10000
DEFAULT_DURATION_DAYS =  60
DEFAULT_MAX_PREMIUM =    75

def fund_account(
    instance: GifInstance, 
    owner: Account,
    account: Account,
    token: interface.IERC20,
    amount: int
):
    token.transfer(account, amount, {'from': owner})
    token.approve(instance.getTreasury(), amount, {'from': account})


def create_bundle(
    instance: GifInstance, 
    instanceOperator: Account,
    investor: Account,
    riskpool: DepegRiskpool,
    funding: int = DEFAULT_BUNDLE_FUNDING,
    minSumInsured: int = DEFAULT_MIN_SUM_INSURED,
    maxSumInsured: int = DEFAULT_MAX_SUM_INSURED,
    minDurationDays: int = DEFAULT_MIN_DURATION_DAYS,
    maxDurationDays: int = DEFAULT_MAX_DURATION_DAYS,
    aprPercentage: float = DEFAULT_APR_PERCENTAGE
) -> int:
    tokenAddress = riskpool.getErc20Token()
    token = contract_from_address(interface.IERC20, tokenAddress)

    token.transfer(investor, funding, {'from': instanceOperator})
    token.approve(instance.getTreasury(), funding, {'from': investor})

    apr100level = riskpool.getApr100PercentLevel();
    apr = apr100level * aprPercentage / 100

    spd = 24*3600
    tx = riskpool.createBundle(
        minSumInsured,
        maxSumInsured,
        minDurationDays * spd,
        maxDurationDays * spd,
        apr,
        funding, 
        {'from': investor})

    # returns bundleId
    return tx.return_value


def apply_for_policy(
    instance: GifInstance, 
    instanceOperator: Account,
    product: DepegProduct, 
    customer: Account,
    sumInsured: int = DEFAULT_SUM_INSURED,
    durationDays: int = DEFAULT_DURATION_DAYS,
    maxPremium: int = DEFAULT_MAX_PREMIUM,
):
    tokenAddress = product.getToken()
    token = contract_from_address(interface.IERC20, tokenAddress)

    # transfer premium funds to customer and create allowance
    token.transfer(customer, maxPremium, {'from': instanceOperator})
    token.approve(instance.getTreasury(), maxPremium, {'from': customer})

    tx = product.applyForPolicy(
        sumInsured,
        durationDays * 24 * 3600,
        maxPremium, 
        {'from': customer})

    # returns policy id
    return tx.return_value
