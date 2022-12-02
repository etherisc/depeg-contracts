import brownie
import pytest
import time

from brownie.network.account import Account
from brownie import (
    GifStaking,
    DIP,
)

from scripts.setup import create_bundle

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


def test_rewards_calculation(
    gifStaking: GifStaking,
):
    reward100Percent = gifStaking.getReward100PercentLevel()
    reward20Percent = reward100Percent / 5
    gifStaking.setRewardPercentage(reward20Percent)

    amount = 10**6
    oneYear = gifStaking.getOneYearDuration()
    oneYearRewardsAmount = gifStaking.calculateRewards(amount, oneYear)

    print('oneYearRewardsAmount {} fraction {}'.format(oneYearRewardsAmount, oneYearRewardsAmount/amount))

    assert reward20Percent/reward100Percent == oneYearRewardsAmount/amount

    # half amount
    halfAmount = amount / 2
    yearRewardsHalfAmount = gifStaking.calculateRewards(halfAmount, oneYear)

    print('yearRewardsHalfAmount {} fraction {}'.format(yearRewardsHalfAmount, yearRewardsHalfAmount/amount))

    assert yearRewardsHalfAmount == oneYearRewardsAmount / 2

    # half year
    halfYear = oneYear / 2
    halfYearRewardsAmount = gifStaking.calculateRewards(amount, halfYear)

    print('halfYear {} fraction {}'.format(halfYear, halfYear/oneYear))
    print('halfYearRewardsAmount {} fraction {}'.format(halfYearRewardsAmount, halfYearRewardsAmount/amount))

    assert halfYearRewardsAmount == oneYearRewardsAmount / 2

    # 14 days
    twoWeeks = 14 * 24 * 3600
    twoWeeksRewardsAmount = gifStaking.calculateRewards(amount, twoWeeks)

    print('twoWeeks {} twoWeeksFraction {}'.format(twoWeeks, twoWeeks/oneYear))
    print('twoWeeksRewardsAmount {} fraction {}'.format(twoWeeksRewardsAmount, twoWeeksRewardsAmount/amount))

    expectedTwoWeeksAmount = oneYearRewardsAmount * (2 / 52)
    assert abs(twoWeeksRewardsAmount - expectedTwoWeeksAmount)/expectedTwoWeeksAmount < 0.003
