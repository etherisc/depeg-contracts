// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "@etherisc/gif-interface/contracts/components/IComponent.sol";
import "./IInstanceDataProvider.sol";

interface IComponentDataProvider is 
    IInstanceDataProvider
{

    struct ComponentKey {
        bytes32 instanceId;
        uint256 componentId;
    }

    struct ComponentInfo {
        ComponentKey key;
        IComponent.ComponentType componentType;
        IComponent.ComponentState state;
        uint256 createdAt;
        uint256 updatedAt;
    }

    function components(bytes32 instanceId) external view returns(uint256 numberOfComponents);
    function getComponentId(bytes32 instanceId, uint256 idx) external view returns(uint256 componentId);

    function isRegisteredComponent(bytes32 instanceId, uint256 componentId) external  view returns(bool isRegistered);
    function getComponentInfo(bytes32 instanceId, uint256 componentId) external view returns(ComponentInfo memory info);
}
