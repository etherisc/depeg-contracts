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


def test_yield_calculation(
    gifStaking: GifStaking,
):
    yield100Percent = gifStaking.getYield100PercentLevel()
    yield20Percent = yield100Percent / 5
    gifStaking.setYield(yield20Percent)

    amount = 10**6
    oneYear = gifStaking.getOneYearDuration()
    oneYearYieldAmount = gifStaking.calculateYield(amount, oneYear)

    print('oneYearYieldAmount {} fraction {}'.format(oneYearYieldAmount, oneYearYieldAmount/amount))

    assert yield20Percent/yield100Percent == oneYearYieldAmount/amount

    # half amount
    halfAmount = amount / 2
    yearYieldHalfAmount = gifStaking.calculateYield(halfAmount, oneYear)

    print('yearYieldHalfAmount {} fraction {}'.format(yearYieldHalfAmount, yearYieldHalfAmount/amount))

    assert yearYieldHalfAmount == oneYearYieldAmount / 2

    # half year
    halfYear = oneYear / 2
    halfYearYieldAmount = gifStaking.calculateYield(amount, halfYear)

    print('halfYear {} fraction {}'.format(halfYear, halfYear/oneYear))
    print('halfYearYieldAmount {} fraction {}'.format(halfYearYieldAmount, halfYearYieldAmount/amount))

    assert halfYearYieldAmount == oneYearYieldAmount / 2

    # 14 days
    twoWeeks = 14 * 24 * 3600
    twoWeeksYieldAmount = gifStaking.calculateYield(amount, twoWeeks)

    print('twoWeeks {} twoWeeksFraction {}'.format(twoWeeks, twoWeeks/oneYear))
    print('twoWeeksYieldAmount {} fraction {}'.format(twoWeeksYieldAmount, twoWeeksYieldAmount/amount))

    expectedTwoWeeksYieldAmount = 2 * oneYearYieldAmount / 52
    assert twoWeeksYieldAmount - expectedTwoWeeksYieldAmount < 1.0
