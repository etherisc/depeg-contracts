// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";
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
        uint256 riskpoolId;
        address token;
        IBundle.BundleState state;
        string name;
        uint256 expiryAt;
        uint256 closedAt;
        uint256 createdAt;
        uint256 updatedAt;
    }

    function bundles(bytes32 instanceId, uint256 riskpoolId) external view returns(uint256 numberOfBundles);
    function getBundleId(bytes32 instanceId, uint256 riskpoolId, uint256 idx) external view returns(uint256 bundleId);
    function getBundleInfo(bytes32 instanceId, uint256 bundleId) external view returns(BundleInfo memory info);
    function isRegisteredBundle(bytes32 instanceId, uint256 bundleId) external view returns(bool isRegistered);

    function getBundleTokenInfo(bytes32 instanceId, uint256 bundleId) external view returns(TokenInfo memory token);
    function getBundleToken(bytes32 instanceId, uint256 bundleId) external view returns(IERC20Metadata token);
}
