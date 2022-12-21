// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "./IInstanceDataProvider.sol";

interface IInstanceRegistry is 
    IInstanceDataProvider 
{
    event LogInstanceRegistryTokenRegistered(address token, uint256 chainId, TokenState state, bool isNewToken);
    event LogInstanceRegistryTokenUpdated(address token, uint256 chainId, TokenState oldState, TokenState newState);

    event LogInstanceRegistryInstanceRegistered(bytes32 instanceId, InstanceState state, bool isNewInstance);
    event LogInstanceRegistryInstanceUpdated(bytes32 instanceId, InstanceState oldState, InstanceState newState);
    event LogInstanceRegistryInstanceUpdated(bytes32 instanceId, string oldDisplayName, string newDisplayName);

    function registerToken(address token) external;
    function registerToken(address token, uint256 chainId, uint8 decimals, string memory symbol) external;
    function updateToken(address token, uint256 chainId, TokenState state) external;

    function registerInstance(address registry) external;
    function registerInstance(bytes32 instanceId, uint256 chainId, address registry) external;
    function updateInstance(bytes32 instanceId, InstanceState state) external;
    function updateInstance(bytes32 instanceId, string memory displayName) external;
}
