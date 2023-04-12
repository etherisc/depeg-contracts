// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";

contract EIP712 {

    bytes32 public constant EIP712_TYPE_HASH =
        keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)");

    bytes32 private immutable _cachedDomainSeparator;
    uint256 private immutable _cachedChainId;
    address private immutable _cachedThis;

    string private _name;
    string private _version;

    bytes32 private _hashedName;
    bytes32 private _hashedVersion;


    constructor(string memory name, string memory version) {
        _name = name;
        _version = version;
        _hashedName = keccak256(bytes(name));
        _hashedVersion = keccak256(bytes(version));

        _cachedChainId = block.chainid;
        _cachedDomainSeparator = _buildDomainSeparator();
        _cachedThis = address(this);
    }


    function getSigner(
        bytes32 digest,
        bytes calldata signature
    )
        public
        pure
        returns(address signer)
    {
        return ECDSA.recover(digest, signature);
    }


    // same as EIP712._hashTypedDataV4(), see
    // https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/cryptography/EIP712.sol
    function getTypedDataV4Hash(bytes32 structHash) public view returns (bytes32) {
        return ECDSA.toTypedDataHash(_domainSeparatorV4(), structHash);
    }


    function _domainSeparatorV4() internal view returns (bytes32) {
        if (address(this) == _cachedThis && block.chainid == _cachedChainId) {
            return _cachedDomainSeparator;
        } else {
            return _buildDomainSeparator();
        }
    }


    function _buildDomainSeparator() private view returns (bytes32) {
        return keccak256(
            abi.encode(
                EIP712_TYPE_HASH, 
                _hashedName, 
                _hashedVersion, 
                block.chainid, 
                address(this)));
    }

}