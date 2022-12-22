// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

interface IBundleRegistry {

    function registerBundle(bytes32 instanceId, uint256 bundleId) external;
    function updateBundle(bytes32 instanceId, uint256 bundleId) external;
}
