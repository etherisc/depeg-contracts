import brownie
import pytest

from brownie.network.account import Account
from brownie import (
    interface,
    DepegProduct,
    DepegRiskpool,
)

# from scripts.util import (
#     s2h,
#     s2b32,
# )

from scripts.setup import (
    new_bundle,
)

from scripts.instance import (
    GifInstance,
)

from scripts.depeg_product import (
    GifDepegProduct,
    GifDepegRiskpool,
)

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


def test_create_bundle(
    instance: GifInstance, 
    instanceOperator: Account,
    investor: Account,
    gifDepegRiskpool: GifDepegRiskpool, 
    riskpoolKeeper: Account,
    customer: Account,
    feeOwner: Account,
    capitalOwner: Account
):
    riskpool = gifTestProduct.getRiskpool().getContract()

    initialFunding = 10000
    minSumInsured = 5000
    maxSumInsured = 10000
    minDurationDays = 30
    maxDurationDays = 90
    aprPercentage = 1.7

    bundleId = new_bundle(
        instance, 
        instanceOperator, 
        investor, 
        gifDepegRiskpool, 
        initialFunding,
        minSumInsured,
        maxSumInsured,
        minDurationDays,
        maxDurationDays,
        aprPercentage
    )

    riskpool.bundles() == 1
    bundle = riskpool.getBundle(0)

    (
        bundleIdInternal,
        riskpoolId,
        tokenId,
        state,
        filter,
        capital,
        lockedCapital,
        balance,
        createdAt,
        updatedAt
    ) = bundle

    print(bundle)
    capitalFee = initialFunding / 20 + 42
    bundleExpectedCapital = initialFunding - capitalFee

    # check bundle values with expectation
    assert bundleId == bundleIdInternal
    assert riskpoolId == riskpool.getId()
    assert tokenId == 1
    assert state == 0 # BundleState { Active, Locked, Closed }
    assert filter == '0x'
    assert capital == bundleExpectedCapital
    assert lockedCapital == 0
    assert balance == bundleExpectedCapital
    assert createdAt > 0
    assert updatedAt >= createdAt

    # check associated nft
    bundleToken = instance.getBundleToken()

    assert bundleToken.exists(tokenId) == True
    assert bundleToken.burned(tokenId) == False
    assert bundleToken.ownerOf(tokenId) == riskpoolKeeper
    assert bundleToken.getBundleId(tokenId) == bundleId

    # check riskpool and bundle are consistent
    assert riskpool.getCapital() == capital
    assert riskpool.getTotalValueLocked() == lockedCapital
    assert riskpool.getBalance() == balance
