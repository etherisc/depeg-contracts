import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    exceptions,
    web3,
    BundleRegistry,
    Staking,
    DIP,
    USD1,
    USD3
)

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


def test_reward_rate_happy_case(
    registryOwner: Account,
    staking: Staking,
):
    exp = 4
    reward_rate_f = 0.2987 # apr is 29.87%
    reward_rate_i = reward_rate_f * 10 ** exp
    reward_rate = staking.toRate(reward_rate_i, -exp)
    reward = staking.fromRate(reward_rate).dict()

    assert reward['value']/reward['divisor'] == reward_rate_f

    reward_rate_initial = staking.getRewardRate()

    tx = staking.setRewardRate(reward_rate, {'from': registryOwner})
    reward_rate_now = staking.getRewardRate()

    # check event
    assert 'LogStakingRewardRateSet' in tx.events
    assert tx.events['LogStakingRewardRateSet']['oldRewardRate'] == reward_rate_initial
    assert tx.events['LogStakingRewardRateSet']['newRewardRate'] == reward_rate_now

    # check rate has been set properly
    assert reward_rate_now == reward_rate


def test_reward_rate_failure_modes(
    registryOwner,
    instanceOperator,
    staking: Staking,
):
    exp = 4
    reward_rate_f = 0.2987 # apr is 29.87%
    reward_rate_i = reward_rate_f * 10 ** exp
    reward_rate = staking.toRate(reward_rate_i, -exp)

    with brownie.reverts('Ownable: caller is not the owner'):
        staking.setRewardRate(reward_rate, {'from': instanceOperator})

    exp = 1
    reward_rate_f = 0.4 # apr is 40%
    reward_rate_i = reward_rate_f * 10 ** exp
    reward_rate = staking.toRate(reward_rate_i, -exp)

    with brownie.reverts('ERROR:STK-010:REWARD_EXCEEDS_MAX_VALUE'):
        staking.setRewardRate(reward_rate, {'from': registryOwner})


def test_staking_rate_happy_case(
    registryOwner: Account,
    bundleRegistry: BundleRegistry,
    staking: Staking,
    dip: DIP,
    usd1: USD1,
    usd3: USD3
):
    exp = 6
    staking_rate_f = 0.123456 # 1 dip unlocks 12.3456 cents (usd1)
    staking_rate_i = staking_rate_f * 10 ** exp
    staking_rate = staking.toRate(staking_rate_i, -exp)

    rate = staking.fromRate(staking_rate).dict()
    assert rate['value']/rate['divisor'] == staking_rate_f

    # register token and get initial rate
    bundleRegistry.registerToken(usd1.address, {'from': registryOwner})
    staking_rate_initial = staking.getStakingRate(usd1.address, web3.chain_id)

    assert staking.hasDefinedStakingRate(usd1.address, web3.chain_id) is False
    assert staking.hasDefinedStakingRate(usd3.address, web3.chain_id) is False

    # set staking rate for usd1
    tx = staking.setStakingRate(
        usd1.address,
        web3.chain_id,
        staking_rate,
        {'from': registryOwner})

    assert staking.hasDefinedStakingRate(usd1.address, web3.chain_id) is True
    assert staking.hasDefinedStakingRate(usd3.address, web3.chain_id) is False

    staking_rate_now = staking.getStakingRate(usd1.address, web3.chain_id)
    assert staking_rate_now == staking_rate

    # check event
    assert 'LogStakingStakingRateSet' in tx.events
    assert tx.events['LogStakingStakingRateSet']['token'] == usd1
    assert tx.events['LogStakingStakingRateSet']['chainId'] == web3.chain_id
    assert tx.events['LogStakingStakingRateSet']['oldStakingRate'] == staking_rate_initial
    assert tx.events['LogStakingStakingRateSet']['newStakingRate'] == staking_rate_now

    # set staking rate for usd3
    bundleRegistry.registerToken(usd3.address, {'from': registryOwner})
    staking.setStakingRate(
        usd3.address,
        web3.chain_id,
        staking_rate,
        {'from': registryOwner})

    assert staking.hasDefinedStakingRate(usd1.address, web3.chain_id) is True
    assert staking.hasDefinedStakingRate(usd3.address, web3.chain_id) is True

    # check staking rates
    usd1_staking_rate = staking.getStakingRate(usd1.address, web3.chain_id)
    usd3_staking_rate = staking.getStakingRate(usd3.address, web3.chain_id)

    assert usd1_staking_rate == staking_rate
    assert usd3_staking_rate == staking_rate

    one_dip = 10**dip.decimals()
    one_usd1 = 10**usd1.decimals()
    one_usd3 = 10**usd3.decimals()

    assert one_usd1 != one_usd3

    ## check dip staking -> supported token amount
    dip_amount = 10 * one_dip

    usd1_amount = staking.calculateCapitalSupport(usd1.address, web3.chain_id, dip_amount)
    usd3_amount = staking.calculateCapitalSupport(usd3.address, web3.chain_id, dip_amount)

    # check resulting supported amounts
    usd1_amount_expected = round(10 * staking_rate_f * 10 ** usd1.decimals())
    usd3_amount_expected = round(10 * staking_rate_f * 10 ** usd3.decimals())

    assert usd1_amount == usd1_amount_expected
    assert usd3_amount == usd3_amount_expected

    # check token amount -> dip staking
    assert staking.calculateRequiredStaking(usd1.address, web3.chain_id, usd1_amount) == dip_amount
    assert staking.calculateRequiredStaking(usd3.address, web3.chain_id, usd3_amount) == dip_amount


def test_conversion_calculation_usd1(
    registryOwner,
    bundleRegistry: BundleRegistry,
    staking: Staking,
    usd1: USD1
):
    exp = 6
    staking_rate_f = 0.123456 # 1 dip unlocks 12.3456 cents (usd1)
    staking_rate_i = staking_rate_f * 10 ** exp
    staking_rate = staking.toRate(staking_rate_i, -exp)

    # set staking rate for usd1
    bundleRegistry.registerToken(usd1.address, {'from': registryOwner})
    staking.setStakingRate(
        usd1.address,
        web3.chain_id,
        staking_rate,
        {'from': registryOwner})

    # calculate dips needed to support 25 usd1
    mult_usd1 = 10**usd1.decimals()
    target_usd1 = 25
    target_amount = target_usd1 * mult_usd1
    required_dip = staking.calculateRequiredStaking(
        usd1.address,
        web3.chain_id,
        target_amount)

    supported_usd1 = staking.calculateCapitalSupport(
        usd1.address,
        web3.chain_id,
        required_dip)

    print('staking_rate {} target_usd1 {} required_dip {} supported_usd1 {}'.format(
        staking_rate,
        target_usd1,
        required_dip,
        supported_usd1))

    assert abs(target_amount - supported_usd1) <= 1


def test_conversion_calculation_usd3(
    bundleRegistry: BundleRegistry,
    registryOwner,
    staking: Staking,
    usd3: USD1
):
    exp = 6
    staking_rate_f = 0.123456 # 1 dip unlocks 12.3456 cents (usd1)
    staking_rate_i = staking_rate_f * 10 ** exp
    staking_rate = staking.toRate(staking_rate_i, -exp)

    # set staking rate for usd1
    bundleRegistry.registerToken(usd3.address, {'from': registryOwner})
    staking.setStakingRate(
        usd3.address,
        web3.chain_id,
        staking_rate,
        {'from': registryOwner})

    # calculate dips needed to support 39 usd3
    mult_usd3 = 10 ** usd3.decimals()
    target_usd3 = 39
    target_amount = target_usd3 * mult_usd3

    required_dip = staking.calculateRequiredStaking(
        usd3.address,
        web3.chain_id,
        target_amount)

    supported_usd3 = staking.calculateCapitalSupport(
        usd3.address,
        web3.chain_id,
        required_dip)

    print('staking_rate {} target_usd3 {} rerquired_dip {} supported_usd3 {}'.format(
        staking_rate,
        target_usd3,
        required_dip,
        target_amount))

    assert abs(target_amount - supported_usd3) <= 1


def test_staking_rate_failure_modes(
    registryOwner,
    instanceOperator,
    bundleRegistry: BundleRegistry,
    staking: Staking,
    usd1: USD1
):
    # attempt to get staking rate for non-registered token
    with brownie.reverts('ERROR:STK-100:TOKEN_NOT_REGISTERED'):
        staking.getStakingRate(usd1.address, web3.chain_id)

    # attempt to set rate for non-registered token
    exp = 6
    staking_rate_f = 0.123456 # 1 dip unlocks 12.3456 cents (usd1)
    staking_rate_i = staking_rate_f * 10 ** exp
    staking_rate = staking.toRate(staking_rate_i, -exp)

    with brownie.reverts('ERROR:STK-020:TOKEN_NOT_REGISTERED'):
        staking.setStakingRate(
            usd1.address,
            web3.chain_id,
            staking_rate,
            {'from': registryOwner})

    bundleRegistry.registerToken(usd1.address, {'from': registryOwner})

    # attempt to set rate as non-owner of staking contract
    with brownie.reverts('Ownable: caller is not the owner'):
        staking.setStakingRate(
            usd1.address,
            web3.chain_id,
            staking_rate,
            {'from': instanceOperator})

    # attempt to set zero rate
    staking_rate_zero = 0

    with brownie.reverts('ERROR:STK-021:STAKING_RATE_ZERO'):
        staking.setStakingRate(
            usd1.address,
            web3.chain_id,
            staking_rate_zero,
            {'from': registryOwner})


def test_calculating_failure_modes(
    staking: Staking,
    usd1: USD1,
    dip: DIP
):
    # attempt to calculate staking for non-registered token
    one_usd1 = 10**usd1.decimals()
    one_dip = 10**dip.decimals()

    # attempt to caluclate without having set a staking rate
    with brownie.reverts("ERROR:STK-001:STAKING_RATE_NOT_DEFINED"):
        staking.calculateRequiredStaking(usd1, web3.chain_id, one_usd1)
    
    with brownie.reverts("ERROR:STK-001:STAKING_RATE_NOT_DEFINED"):
        staking.calculateCapitalSupport(usd1, web3.chain_id, one_dip)


def test_tofrom_rate(
    staking: Staking
):
    # with brownie.reverts("OverflowError: fromRate '-1' - -1 is 
    # outside allowable range for uint256"):
    with pytest.raises(OverflowError):
        staking.fromRate(-1)

    rate_min = staking.fromRate(0)
    assert rate_min == (0, 10**18)

    rate_max = staking.fromRate(2**256 - 1)
    assert rate_max == (2**256 - 1, 10**18)

    # OverflowError: fromRate '1157920892373161954235709850086879..
    # 07853269984665640564039457584007913129639936' - 11579208923..
    # 73161954235709850086879078532699846656405640394575840079131..
    # 29639936 is outside allowable range for uint256
    with pytest.raises(OverflowError):
        staking.fromRate(2**256)
