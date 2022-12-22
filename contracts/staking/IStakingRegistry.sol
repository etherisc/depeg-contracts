// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "./IStakingDataProvider.sol";
interface IStakingRegistry is
    IStakingDataProvider
{

    function registerRiskpool(bytes32 instanceId, uint256 riskpoolId) external;
    function updateRiskpool(bytes32 instanceId, uint256 riskpoolId) external;

    function registerBundle(bytes32 instanceId, uint256 bundleId) external;
    function updateBundle(bytes32 instanceId, uint256 bundleId) external;
}
