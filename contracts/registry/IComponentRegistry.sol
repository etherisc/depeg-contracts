// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

interface IComponentRegistry {

    function registerComponent(bytes32 instanceId, uint256 riskpoolId) external;
    function updateComponent(bytes32 instanceId, uint256 riskpoolId) external;
}
