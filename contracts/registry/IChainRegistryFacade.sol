// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.2;


interface IChainRegistryFacade {

    function getComponentNftId(
        bytes32 instanceId, 
        uint256 componentId
    )
        external
        view
        returns(uint256 nftId);

    function exists(uint256 nftId) external view returns(bool);

    // get nft id for specified bundle coordinates
    function getBundleNftId(
        bytes32 instanceId, 
        uint256 bundleId
    )
        external
        view
        returns(uint256 nftId);

    function registerBundle(
        bytes32 instanceId,
        uint256 riskpoolId,
        uint256 bundleId,
        string memory displayName,
        uint256 expiryAt
    )
        external
        returns(uint256 nftId);

}