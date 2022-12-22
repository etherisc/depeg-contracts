// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "@etherisc/gif-interface/contracts/modules/IBundle.sol";

import "./IComponentDataProvider.sol";

interface IBundleDataProvider is 
    IComponentDataProvider
{

    struct BundleKey {
        bytes32 instanceId;
        uint256 bundleId;
    }

    struct BundleInfo {
        BundleKey key;
        ComponentKey riskpool;
        string name;
        IBundle.BundleState state;
        TokenKey token;
        string tokenSymbol;
        uint8 tokenDecimals;
        uint256 expiryAt;
        uint256 closedAt;
        uint256 createdAt;
        uint256 updatedAt;
    }

    function bundles(bytes32 instanceId) external view returns(uint256 numberOfBundles);
    function bundles(bytes32 instanceId, uint256 riskpoolId) external view returns(uint256 numberOfBundles);
    function getBundleId(bytes32 instanceId, uint256 idx) external view returns(uint256 bundleId);
    function getBundleId(bytes32 instanceId, uint256 riskpoolId, uint256 idx) external view returns(uint256 bundleId);

    function isRegisteredBundle(bytes32 instanceId, uint256 bundleId) external view returns(bool isRegistered);
    function getBundleInfo(bytes32 instanceId, uint256 bundleId) external view returns(BundleInfo memory info);
}
