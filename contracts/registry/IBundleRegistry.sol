// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "@etherisc/gif-interface/contracts/modules/IBundle.sol";

interface IBundleRegistry {

    event LogInstanceRegistryBundleRegistered(bytes32 instanceId, uint256 riskpoolId, uint256 bundleId, IBundle.BundleState state);
    event LogInstanceRegistryBundleUpdated(bytes32 instanceId, uint256 bundleId, IBundle.BundleState oldState, IBundle.BundleState newState);

    function registerBundle(bytes32 instanceId, uint256 riskpoolId, uint256 bundleId, string memory name, uint256 expiryAt) external;
    function updateBundle(bytes32 instanceId, uint256 bundleId) external;
}
