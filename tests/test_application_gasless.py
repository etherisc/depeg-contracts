import brownie
import pytest

from brownie import (
    web3,
    chain,
    history,
    interface
)

from brownie.network import accounts
from brownie.network.account import Account

from scripts.util import b2s

from scripts.depeg_product import (
    GifDepegProduct,
    GifDepegRiskpool,
)

from scripts.setup import (
    create_bundle, 
    apply_for_policy_with_bundle,
)

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


def test_signature_and_signer(product):

    # TODO fix this test
    return

    # {
    #     "wallet": "0x2CeC4C063Fef1074B0CD53022C3306A6FADb4729",
    #     "protectedBalance": "2000000000",
    #     "duration": 2592000,
    #     "bundleId": 4,
    #     "signatureId": "0x6a71447a5a44676b4d76453169515a564f346336770000000000000000000000"
    # }
    # signature
    # 0xe22c77faa4a6b338f30218edfd322193f8a6f32fa32cb523592ecc874f8d14e85a798e321a81bbdc2a1ff6e4b17274a0ec3d1a86faa74124a9ef9a7b728dfb3c1c

    protectedWallet = accounts.at('0x2CeC4C063Fef1074B0CD53022C3306A6FADb4729', force=True)
    policyHolder = protectedWallet
    protectedBalance = 2000000000
    durationDays = 30
    duration = durationDays * 24 * 3600
    bundleId = 4

    signer1 = product.getSignerFromDigestAndSignature(
        protectedWallet,
        protectedBalance,
        duration,
        bundleId,
        0x6a71447a5a44676b4d76453169515a564f346336770000000000000000000000,
        0xe22c77faa4a6b338f30218edfd322193f8a6f32fa32cb523592ecc874f8d14e85a798e321a81bbdc2a1ff6e4b17274a0ec3d1a86faa74124a9ef9a7b728dfb3c1c)

    signatureId = 0x6a71447a5a44676b4d76453169515a564f346336770000000000000000000001
    signature = 0xe22c77faa4a6b338f30218edfd322193f8a6f32fa32cb523592ecc874f8d14e85a798e321a81bbdc2a1ff6e4b17274a0ec3d1a86faa74124a9ef9a7b728dfb3c1c

    signer2 = product.getSignerFromDigestAndSignature(
        protectedWallet,
        protectedBalance,
        duration,
        bundleId,
        signatureId,
        signature)

    signatureIdBytes = web3.toBytes(signatureId)
    signatureBytes = web3.toBytes(signature)

    signer3 = product.getSignerFromDigestAndSignature(
        protectedWallet,
        protectedBalance,
        duration,
        bundleId,
        signatureIdBytes,
        signatureBytes)

    # check signer against expected signer
    assert signer1 == policyHolder


def test_create_application(
    instance,
    instanceService,
    instanceOperator,
    instanceWallet,
    investor,
    customer,
    product,
    riskpool
):
    # TODO fix this test
    return

    instanceWallet = instanceService.getInstanceWallet()
    riskpoolWallet = instanceService.getRiskpoolWallet(riskpool.getId())
    tokenAddress = instanceService.getComponentToken(riskpool.getId())
    token = interface.IERC20Metadata(tokenAddress)
    tf = 10 ** token.decimals()

    bundleId = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool)

    riskpoolBalanceBefore = instanceService.getBalance(riskpool.getId())
    instanceBalanceBefore = token.balanceOf(instanceWallet)

    # {
    #     "wallet": "0x2CeC4C063Fef1074B0CD53022C3306A6FADb4729",
    #     "protectedBalance": "2000000000",
    #     "duration": 2592000,
    #     "bundleId": 4,
    #     "signatureId": "0x6a71447a5a44676b4d76453169515a564f346336770000000000000000000000"
    # }
    # signature
    # 0xe22c77faa4a6b338f30218edfd322193f8a6f32fa32cb523592ecc874f8d14e85a798e321a81bbdc2a1ff6e4b17274a0ec3d1a86faa74124a9ef9a7b728dfb3c1c

    protectedWallet = accounts.at('0x2CeC4C063Fef1074B0CD53022C3306A6FADb4729', force=True)
    policyHolder = protectedWallet
    protectedBalance = 2000000000
    sumInsured = riskpool.calculateSumInsured(protectedBalance)
    durationDays = 30
    duration = durationDays * 24 * 3600
    bundleId = 4

    signatureId = 0x6a71447a5a44676b4d76453169515a564f346336770000000000000000000000
    signature = 0xe22c77faa4a6b338f30218edfd322193f8a6f32fa32cb523592ecc874f8d14e85a798e321a81bbdc2a1ff6e4b17274a0ec3d1a86faa74124a9ef9a7b728dfb3c1c

    signatureIdBytes = web3.toBytes(signatureId)
    signatureBytes = web3.toBytes(signature)

    tx = product.applyForPolicyWithBundleAndSignature(
        policyHolder, 
        protectedWallet, 
        protectedBalance, 
        duration, 
        bundleId, 
        signatureIdBytes, 
        signatureBytes, 
        {'from': customer})

    assert False


def get_bundle_id(
    instance_service,
    riskpool,
    process_id
):
    data = instance_service.getApplication(process_id).dict()['data']
    params = riskpool.decodeApplicationParameterFromData(data).dict()
    return params['bundleId']