# command to use sandboxr (wihout 'STOP=Y' at the beginning: just a normal test that should pass)
# STOP=Y brownie test tests/test_sandbox.py::test_product_sandbox --interactive

import brownie
import pytest
import os

from brownie.network.account import Account
from brownie import (
    web3,
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
    contract_from_address,
    get_package
)

from scripts.depeg_product import GifDepegProduct

from scripts.deploy_depeg import (
    get_setup,
    get_bundle,
    get_policy,
)

from scripts.setup import (
    create_bundle, 
    apply_for_policy_with_bundle,
)

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


def test_product_sandbox(
    instance,
    instanceOperator: Account,
    gifDepegProduct20: GifDepegProduct,
    usd1,
    usd2,
    productOwner: Account,
    riskpoolKeeper: Account,
    riskpoolWallet: Account,
    investor: Account,
    customer: Account,
    registryOwner: Account,
):
    product20 = gifDepegProduct20.getContract()
    instance_service = instance.getInstanceService()

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
        usdc,
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

    # "stake" some dips
    mock = contract_from_address(MockRegistryStaking, riskpool.getStaking())
    bundle_nft = mock.getBundleNftId(instance_service.getInstanceId(), bundle_id)
    bundle_stake = 10000 * 10**dip.decimals()

    mock.setStakedDip(bundle_nft, bundle_stake, {'from': instanceOperator})
    dip.transfer(mock.getStakingWallet(), bundle_stake, {'from': instanceOperator})

    # "reset" customer, set balance and allowance
    usd2.transfer(instanceOperator, usd2.balanceOf(customer), {'from': customer})

    tf = 10**usd2.decimals()
    balance = 100 * tf
    allowance = 100 * tf

    usd2.transfer(customer, balance, {'from': instanceOperator})
    usd2.approve(instance_service.getTreasuryAddress(), allowance, {'from': customer})

    assert usd2.balanceOf(customer) == balance
    assert usd2.allowance(customer, instance_service.getTreasuryAddress()) == allowance

    # specify policy buying parameters and customer setup
    protected_wallet = customer
    protected_balance = 5000 * 10**usd1.decimals()
    duration_days = 60
    duration = duration_days * 24 * 3600

    # buy policy
    tx = product.applyForPolicyWithBundle(
        protected_wallet, 
        protected_balance, 
        duration, 
        bundle_id, 
        {'from': customer})
    
    process_id = tx.events['LogApplicationCreated']['processId']

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
        usdc,
        instance_service
    ) = get_setup(product20)

    bundle_details = get_bundle(bundle_id, product)
    policy_details = get_policy(process_id, product)

    if os.getenv('STOP','N') == 'Y':
        assert False
