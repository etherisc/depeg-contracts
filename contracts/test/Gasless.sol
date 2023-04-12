// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import {EIP712} from "./EIP712.sol";

contract Gasless is
    EIP712
{

    // EIP-712 Depeg specidfics
    string public constant EIP712_DOMAIN_NAME = "EtheriscDepeg";
    string public constant EIP712_DOMAIN_VERSION = "1";

    string public constant EIP712_POLICY_TYPE = "Policy(address wallet,uint256 protectedBalance,uint256 duration,uint256 bundleId)";
    bytes32 private constant EIP712_POLICY_TYPE_HASH = keccak256(abi.encodePacked(EIP712_POLICY_TYPE));

    constructor() 
        EIP712(EIP712_DOMAIN_NAME, EIP712_DOMAIN_VERSION)
    { }


    function applyForPolicy(
        address policyHolder,
        address protectedWallet,
        uint256 protectedBalance,
        uint256 duration,
        uint256 bundleId, 
        bytes calldata signature
    )
        external
        view
    {
        
        address signer = getSignerFromDigestAndSignature(
            protectedWallet,
            protectedBalance,
            duration,
            bundleId,
            signature);

        require(policyHolder == signer, "ERROR: Signature invalid");
    }


    function getSignerFromDigestAndSignature(
        address protectedWallet,
        uint256 protectedBalance,
        uint256 duration,
        uint256 bundleId,
        bytes calldata signature
    )
        public
        view
        returns(address)
    {
        bytes32 digest = getDigest(
                protectedWallet,
                protectedBalance,
                duration,
                bundleId
            );

        return getSigner(digest, signature);
    }


    function getDigest(
        address protectedWallet,
        uint256 protectedBalance,
        uint256 duration,
        uint256 bundleId
    )
        public
        view
        returns(bytes32)
    {
        bytes32 structHash = getStructHash(
            protectedWallet,
            protectedBalance,
            duration,
            bundleId
        );

        return getTypedDataV4Hash(structHash);
    }


    function getStructHash(
        address protectedWallet,
        uint256 protectedBalance,
        uint256 duration,
        uint256 bundleId
    )
        public
        pure
        returns(bytes32)
    {
        return keccak256(
            abi.encode(
                EIP712_POLICY_TYPE_HASH,
                protectedWallet,
                protectedBalance,
                duration,
                bundleId
            )
        );
    }

}