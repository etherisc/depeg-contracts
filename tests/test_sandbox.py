import brownie
import pytest
import os

from brownie.network.account import Account
from brownie import (
    chain,
    history,
    interface,
    UsdcPriceDataProvider,
    DepegProduct,
    DepegRiskpool,
    MockRegistryStaking,
    USD1,
    USD2,
    DIP
)

from scripts.util import (
    b2s,
    contract_from_address
)

from scripts.depeg_product import GifDepegProduct
from scripts.deploy_depeg import get_setup

from scripts.setup import (
    create_bundle, 
    apply_for_policy_with_bundle,
)

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


# command to use sandboxr (wihout 'STOP=Y' at the beginning: just a normal test that should pass)
# STOP=Y brownie test tests/test_sandbox.py --interactive
def test_product_sandbox(
    instance,
    instanceOperator: Account,
    gifDepegProduct20: GifDepegProduct,
    productOwner: Account,
    riskpoolKeeper: Account,
    riskpoolWallet: Account,
    investor: Account,
    customer: Account,
    registryOwner: Account,
):
    product20 = gifDepegProduct20.getContract()

    # just needed to get riskpool and product
    (
        setup_before,
        product,
        feeder,
        riskpool,
        registry,
        staking,
        dip,
        usdt,
        instance_service
    ) = get_setup(product20)

    max_protected_balance = 10000
    bundle_funding = (max_protected_balance * 2) / 5

    bundle_id = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool,
        bundleName = 'bundle-1',
        maxProtectedBalance = max_protected_balance,
        funding = bundle_funding)
    
    bundle = instance_service.getBundle(bundle_id).dict()
    bundle_filter = riskpool.decodeBundleParamsFromFilter(bundle['filter']).dict()

    # buy policy for wallet to be protected
    protected_wallet = customer
    protected_balance = 5000
    duration_days = 60
    max_premium = 100

    process_id = apply_for_policy_with_bundle(
        instance,
        instanceOperator,
        product,
        customer,
        bundle_id,
        protected_wallet,
        protected_balance,
        duration_days,
        max_premium)

    metadata = instance_service.getMetadata(process_id).dict()
    application = instance_service.getApplication(process_id).dict()
    application_data = riskpool.decodeApplicationParameterFromData(application['data']).dict()
    policy = instance_service.getPolicy(process_id).dict()      

    (
        setup,
        product,
        feeder,
        riskpool,
        registry,
        staking,
        dip,
        usdt,
        instance_service
    ) = get_setup(product20)

    if os.getenv('STOP','N') == 'Y':
        assert False
