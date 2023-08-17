import brownie
import pytest

from eip712_structs import EIP712Struct, Address, Bytes, String, Uint
from eip712_structs import make_domain
from eth_utils import big_endian_to_int
from coincurve import PrivateKey, PublicKey

from brownie import (
    web3,
    chain,
    history,
    interface,
    Gasless
)

from web3 import Web3

from brownie.network import accounts
from brownie.network.account import Account

from scripts.util import b2s, s2b

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

keccak_hash = lambda x : Web3.keccak(x)

# https://medium.com/treum_io/introducing-eip-712-structs-in-python-27eac7f38281
# https://gist.github.com/alexisrobert/9facb3d21d4f04946f3a41b5a3c0a9a1
# "Policy(address wallet,uint256 protectedBalance,uint256 duration,uint256 bundleId)"
class Policy(EIP712Struct):
    wallet = Address()
    protectedBalance = Uint(256)
    duration = Uint(256)
    bundleId = Uint(256)
    signatureId = Bytes(32)


def create_policy_signature(wallet, protectedBalance, duration, bundleId, signatureId, contractAddress, policy_holder):
    # prepare messsage
    message = Policy()
    message['wallet'] = wallet.address
    message['protectedBalance'] = protectedBalance
    message['duration'] = duration
    message['bundleId'] = bundleId
    message['signatureId'] = signatureId

    depeg_domain = make_domain(
        name='EtheriscDepeg',
        version='1',
        chainId=web3.chain_id,
        verifyingContract=contractAddress)

    signable_bytes = message.signable_bytes(depeg_domain)

    pk = PrivateKey.from_int(int(policy_holder.private_key, 16))
    sig = pk.sign_recoverable(signable_bytes, hasher=keccak_hash)
    v = sig[64] + 27
    r = big_endian_to_int(sig[0:32])
    s = big_endian_to_int(sig[32:64])    

    signature_raw = r.to_bytes(32, 'big') + s.to_bytes(32, 'big') + v.to_bytes(1, 'big')
    signature = '0x{}'.format(signature_raw.hex())

    return signature


def test_signature_and_signer(messageHelper, customer, customer2, protectedWallet):

    # prepare application parameters
    protectedBalance = 20000 * 10**6
    duration = 30 * 24 * 3600
    bundleId = 4
    signatureId = s2b('some-unique-signature')

    signature = create_policy_signature(protectedWallet, protectedBalance, duration, bundleId, signatureId, messageHelper.address, customer)

    signer_from_signature = messageHelper.getSignerFromDigestAndSignature(
        protectedWallet,
        protectedBalance,
        duration,
        bundleId,
        signatureId,
        signature)

    assert signer_from_signature == customer

    # same assertion rerwitten
    assert customer == messageHelper.getSignerFromDigestAndSignature(protectedWallet, protectedBalance, duration, bundleId, signatureId, signature)

    # failure cases
    assert customer != messageHelper.getSignerFromDigestAndSignature(customer, protectedBalance, duration, bundleId, signatureId, signature)
    assert customer != messageHelper.getSignerFromDigestAndSignature(protectedWallet, protectedBalance+1, duration, bundleId, signatureId, signature)
    assert customer != messageHelper.getSignerFromDigestAndSignature(protectedWallet, protectedBalance, duration+1, bundleId, signatureId, signature)
    assert customer != messageHelper.getSignerFromDigestAndSignature(protectedWallet, protectedBalance, duration, bundleId+1, signatureId, signature)

    signatureId_wrong = s2b('some-other-signature')
    assert customer != messageHelper.getSignerFromDigestAndSignature(protectedWallet, protectedBalance, duration, bundleId, signatureId_wrong, signature)


def test_apply_for_policy(product, customer, customer2, protectedWallet):

    # prepare application parameters
    protectedBalance = 20000 * 10**6
    duration = 30 * 24 * 3600
    bundleId = 4
    signatureId = s2b('some-unique-signature')
    signature = create_policy_signature(protectedWallet, protectedBalance, duration, bundleId, signatureId, product.getMessageHelperAddress(), customer)

    # "happy" case (reverts in bundle controller well past signature checks)
    with brownie.reverts('ERROR:BUC-060:BUNDLE_DOES_NOT_EXIST'):
        product.applyForPolicyWithBundleAndSignature(customer, protectedWallet, protectedBalance, duration, bundleId, signatureId, signature, {'from': customer})

    # attempt to use different policy holder (customer2 instead of customer)
    with brownie.reverts("ERROR:DMH-002:SIGNATURE_INVALID"):
        product.applyForPolicyWithBundleAndSignature(customer2, protectedWallet, protectedBalance, duration, bundleId, signatureId, signature, {'from': customer})

    # attempt to use different wallet address (customer2 instead of wallet)
    with brownie.reverts("ERROR:DMH-002:SIGNATURE_INVALID"):
        product.applyForPolicyWithBundleAndSignature(customer, customer2, protectedBalance, duration, bundleId, signatureId, signature, {'from': customer})

    # attempt to use different protected balance
    with brownie.reverts("ERROR:DMH-002:SIGNATURE_INVALID"):
        product.applyForPolicyWithBundleAndSignature(customer, protectedWallet, 2 * protectedBalance, duration, bundleId, signatureId, signature, {'from': customer})

    # attempt to use different duration
    with brownie.reverts("ERROR:DMH-002:SIGNATURE_INVALID"):
        product.applyForPolicyWithBundleAndSignature(customer, protectedWallet, protectedBalance, 2 * duration, bundleId, signatureId, signature, {'from': customer})

    # attempt to use different bundle id
    with brownie.reverts("ERROR:DMH-002:SIGNATURE_INVALID"):
        product.applyForPolicyWithBundleAndSignature(customer, protectedWallet, protectedBalance, duration, bundleId - 1, signatureId, signature, {'from': customer})

    # attempt to use different bundle id
    with brownie.reverts("ERROR:DMH-002:SIGNATURE_INVALID"):
        product.applyForPolicyWithBundleAndSignature(customer, protectedWallet, protectedBalance, duration, bundleId, s2b('bad'), signature, {'from': customer})

    # attempt to use changed signature
    with brownie.reverts("ECDSA: invalid signature 'v' value"):
        product.applyForPolicyWithBundleAndSignature(customer, protectedWallet, protectedBalance, duration, bundleId, signatureId, signature[:-4] + '0000', {'from': customer})

    # attempt to use shortened signature
    with brownie.reverts("ECDSA: invalid signature length"):
        product.applyForPolicyWithBundleAndSignature(customer, protectedWallet, protectedBalance, duration, bundleId, signatureId, signature[:-2], {'from': customer})


def test_create_policy(
    instance,
    instanceService,
    instanceOperator,
    instanceWallet,
    investor,
    customer,
    protectedWallet,
    product,
    riskpool
):
    # instanceWallet = instanceService.getInstanceWallet()
    # riskpoolWallet = instanceService.getRiskpoolWallet(riskpool.getId())
    tokenAddress = instanceService.getComponentToken(riskpool.getId())
    token = interface.IERC20Metadata(tokenAddress)
    # tf = 10 ** token.decimals()

    bundleId = create_bundle(
        instance, 
        instanceOperator, 
        investor, 
        riskpool)

    # prepare application parameters
    protectedBalance = 2000 * 10**6
    duration = 30 * 24 * 3600
    signatureId = s2b('some-unique-signature')
    # signature = create_policy_signature(protectedWallet, protectedBalance, duration, bundleId, signatureId, product, customer)
    signature = create_policy_signature(protectedWallet, protectedBalance, duration, bundleId, signatureId, product.getMessageHelperAddress(), customer)

    # transfer some tokens to pay for premium
    premiumFunds = protectedBalance / 10
    token.transfer(customer, premiumFunds, {'from': instanceOperator})
    token.approve(instanceService.getTreasuryAddress(), premiumFunds, {'from': customer})

    # create application/policy for customer
    customerBalanceBefore = customer.balance()

    tx = product.applyForPolicyWithBundleAndSignature(
        customer, # = policy holder
        protectedWallet, 
        protectedBalance, 
        duration, 
        bundleId, 
        signatureId, 
        signature, 
        {'from': instanceOperator})

    process_id = tx.events['LogDepegPolicyCreated']['processId']

    # verify customer didn't have to pay gas fees
    customerBalanceAfter = customer.balance()
    assert customerBalanceBefore == customerBalanceAfter

    # verify customer is policy holder
    metadata = instanceService.getMetadata(process_id).dict()
    assert metadata['owner'] == customer
