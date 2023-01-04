import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    Staking,
    DIP,
)

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


def test_rewards_calculation(
    staking: Staking,
    registryOwner: Account,
    dip: DIP
):
    exp = 3
    reward_rate_i = 217  # 21.7% apr for dip staking
    reward_rate_f = reward_rate_i * 10 ** -exp # 5% apr

    # check rate conversion
    reward_rate = staking.toRate(reward_rate_i, -exp)
    reward = staking.fromRate(reward_rate).dict()

    assert reward['value'] / reward['divisor'] == reward_rate_f

    # check reward rate setter and getter
    staking.setRewardRate(reward_rate, {'from': registryOwner})
    rate = staking.getRewardRate()

    assert rate == reward_rate

    dip_amount = 10000 * 10**dip.decimals()
    one_year = staking.oneYear()
    one_year_rewards_amount = staking.calculateRewards(dip_amount, one_year)

    print('one_year_rewards_amount {} fraction {}'.format(one_year_rewards_amount, one_year_rewards_amount/dip_amount))

    assert one_year_rewards_amount/dip_amount == reward_rate_f

    # half amount
    dip_half_amount = dip_amount / 2
    year_rewards_half_amount = staking.calculateRewards(dip_half_amount, one_year)

    print('year_rewards_half_amount {} fraction {}'.format(year_rewards_half_amount, year_rewards_half_amount/dip_amount))

    assert year_rewards_half_amount == one_year_rewards_amount / 2

    # half year
    half_year = one_year / 2
    half_year_rewards_amount = staking.calculateRewards(dip_amount, half_year)

    print('half_year {} fraction {}'.format(half_year, half_year/one_year))
    print('half_year_rewards_amount {} fraction {}'.format(half_year_rewards_amount, half_year_rewards_amount/dip_amount))

    assert half_year_rewards_amount == one_year_rewards_amount / 2

    # 14 days
    two_weeks = 14 * 24 * 3600
    two_weeks_rewards_amount = staking.calculateRewards(dip_amount, two_weeks)

    print('two_weeks {} fraction {}'.format(two_weeks, two_weeks/one_year))
    print('two_weeks_rewards_amount {} fraction {}'.format(two_weeks_rewards_amount, two_weeks_rewards_amount/dip_amount))

    expected_two_weeks_rewards_amount = (one_year_rewards_amount * 14) / 365
    assert abs(two_weeks_rewards_amount - expected_two_weeks_rewards_amount)/expected_two_weeks_rewards_amount <= 10**-10
