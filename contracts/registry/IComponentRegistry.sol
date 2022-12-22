// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "@etherisc/gif-interface/contracts/components/IComponent.sol";

interface IComponentRegistry {

    event LogInstanceRegistryComponentRegistered(bytes32 instanceId, uint256 componentId, IComponent.ComponentType componentType, IComponent.ComponentState state, bool isNewComponent);
    event LogInstanceRegistryComponentUpdated(bytes32 instanceId, uint256 componentId, IComponent.ComponentState oldState, IComponent.ComponentState newState);

    function registerComponent(bytes32 instanceId, uint256 riskpoolId) external;
    function updateComponent(bytes32 instanceId, uint256 riskpoolId) external;
}
