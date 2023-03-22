// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.2;

import "./IChainNftFacade.sol";

interface IChainRegistryFacade {

    function registerBundle(
        bytes32 instanceId,
        uint256 riskpoolId,
        uint256 bundleId,
        string memory displayName,
        uint256 expiryAt
    )
        external
        returns(uint256 nftId);


    function owner() external view returns(address);
    function getNft() external view returns(IChainNftFacade);
    function toChain(uint256 chainId) external pure returns(bytes5 chain);

    function objects(bytes5 chain, uint8 objectType) external view returns(uint256 numberOfObjects);
    function exists(uint256 nftId) external view returns(bool);

    function getInstanceNftId(bytes32 instanceId) external view returns(uint256 id);
    function getComponentNftId(bytes32 instanceId, uint256 componentId) external view returns(uint256 nftId);
    function getBundleNftId(bytes32 instanceId, uint256 bundleId) external view returns(uint256 nftId);

}