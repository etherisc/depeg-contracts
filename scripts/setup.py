from brownie.network.account import Account

# pylint: disable-msg=E0611
from brownie import (
    interface,
    DepegProduct,
    DepegRiskpool
)

from scripts.instance import GifInstance
from scripts.util import contract_from_address


DEFAULT_BUNDLE_FUNDING = 100000
DEFAULT_MIN_PROTECTED_BALANCE =  2000
DEFAULT_MAX_PROTECTED_BALANCE = 50000
DEFAULT_MIN_DURATION_DAYS =  30
DEFAULT_MAX_DURATION_DAYS =  90
DEFAULT_APR_PERCENTAGE =    5.0

DEFAULT_PROTECTED_BALANCE = 10000
DEFAULT_DURATION_DAYS =  60
DEFAULT_MAX_PREMIUM =    75

USD2_DECIMALS = 6
FUNDING = 10000
BUNDLE_LIFETIME_DAYS = 100

MIN_PROTECTED_BALANCE = DEFAULT_MIN_PROTECTED_BALANCE
MAX_PROTECTED_BALANCE = 20000
MIN_DURATION_DAYS = 14
MAX_DURATION_DAYS = 120
ARP_PERCENTAGE = 3.1415


def fund_account(
    instance: GifInstance, 
    owner: Account,
    account: Account,
    token: interface.IERC20,
    amount: int
):
    token.transfer(account, amount, {'from': owner})
    token.approve(instance.getTreasury(), amount, {'from': account})


def new_bundle(
    instance,
    instanceOperator,
    investor,
    riskpool,
    bundleName, 
    bundleLifetimeDays=BUNDLE_LIFETIME_DAYS
):
    return create_bundle(
        instance,
        instanceOperator,
        investor,
        riskpool,
        FUNDING,
        bundleName,
        bundleLifetimeDays,
        MIN_PROTECTED_BALANCE,
        MAX_PROTECTED_BALANCE,
        MIN_DURATION_DAYS,
        MAX_DURATION_DAYS,
        ARP_PERCENTAGE)


def create_bundle(
    instance: GifInstance, 
    instanceOperator: Account,
    investor: Account,
    riskpool: DepegRiskpool,
    funding: int = DEFAULT_BUNDLE_FUNDING,
    bundleName: str = '',
    bundleLifetimeDays: int = 90,
    minProtectedBalance: int = DEFAULT_MIN_PROTECTED_BALANCE,
    maxProtectedBalance: int = DEFAULT_MAX_PROTECTED_BALANCE,
    minDurationDays: int = DEFAULT_MIN_DURATION_DAYS,
    maxDurationDays: int = DEFAULT_MAX_DURATION_DAYS,
    aprPercentage: float = DEFAULT_APR_PERCENTAGE
) -> int:
    tokenAddress = riskpool.getErc20Token()
    token = contract_from_address(interface.IERC20Metadata, tokenAddress)
    tf = 10 ** token.decimals()

    instanceService = instance.getInstanceService()
    token.transfer(investor, funding * tf, {'from': instanceOperator})
    token.approve(instanceService.getTreasuryAddress(), funding * tf, {'from': investor})

    apr100level = riskpool.getApr100PercentLevel();
    apr = apr100level * aprPercentage / 100
    spd = 24 * 3600

    tx = riskpool.createBundle(
        bundleName,
        bundleLifetimeDays * spd,
        minProtectedBalance * tf,
        maxProtectedBalance * tf,
        minDurationDays * spd,
        maxDurationDays * spd,
        apr,
        funding * tf, 
        {'from': investor})

    return tx.events['LogRiskpoolBundleCreated']['bundleId']


def apply_for_policy_with_bundle(
    instance: GifInstance, 
    instanceOperator: Account,
    product: DepegProduct, 
    customer: Account,
    bundleId: int,
    wallet: Account = None,
    protectedBalance: int = DEFAULT_PROTECTED_BALANCE,
    durationDays: int = DEFAULT_DURATION_DAYS,
    maxPremium: int = DEFAULT_MAX_PREMIUM,
):
    tokenAddress = product.getToken()
    token = contract_from_address(interface.IERC20Metadata, tokenAddress)
    tf = 10 ** token.decimals()

    # transfer premium funds to customer and create allowance
    token.transfer(customer, maxPremium * tf, {'from': instanceOperator})
    token.approve(instance.getTreasury(), maxPremium * tf, {'from': customer})

    if not wallet:
        wallet = customer

    tx = product.applyForPolicyWithBundle(
        wallet,
        protectedBalance * tf,
        durationDays * 24 * 3600,
        bundleId, 
        {'from': customer})

    return tx.events['LogApplicationCreated']['processId']
