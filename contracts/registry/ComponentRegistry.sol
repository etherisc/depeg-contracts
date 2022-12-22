// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "./IComponentDataProvider.sol";
import "./IComponentRegistry.sol";

import "./InstanceRegistry.sol";

contract ComponentRegistry is
    IComponentDataProvider,
    IComponentRegistry,
    InstanceRegistry
{
    // components 
    mapping(bytes32 /* instanceId */ => mapping(uint256 /* componentId */ => ComponentInfo)) private _componentInfo;

    mapping(bytes32 /* instanceId */ => ComponentKey []) private _componentKeys;
    // ComponentKey [] private _componentKeys;

    modifier onlyRegisteredInstance(bytes32 instanceId) {
        require(this.isRegisteredInstance(instanceId), "ERROR:CRG-001:INSTANCE_NOT_REGISTERED");
        _;
    }

    modifier onlyRegisteredComponent(bytes32 instanceId, uint256 componentId) {
        require(this.isRegisteredComponent(instanceId, componentId), "ERROR:CRG-002:COMPONENT_NOT_REGISTERED");
        _;
    }

    modifier onlySameChain(bytes32 instanceId) {
        InstanceInfo memory info = getInstanceInfo(instanceId);
        require(block.chainid == info.chainId, "ERROR:CRG-003:DIFFERENT_CHAIN_NOT_SUPPORTET");
        _;
    }

    function registerComponent(bytes32 instanceId, uint256 componentId) 
        external override
        onlyRegisteredInstance(instanceId)
        onlySameChain(instanceId)
        onlyOwner()
    {
        InstanceInfo memory instance = getInstanceInfo(instanceId);
        IInstanceService instanceService = _getInstanceServiceFromRegistry(instance.registry);

        _registerComponent(
            instanceId,
            componentId,
            instanceService.getComponentType(componentId),
            instanceService.getComponentState(componentId)
        );
    }


    function updateComponent(bytes32 instanceId, uint256 componentId)
        external override
        onlySameChain(instanceId)
        // no restriction who can call this: function obtains new state via instnance service
    {
        InstanceInfo memory instance = getInstanceInfo(instanceId);
        IInstanceService instanceService = _getInstanceServiceFromRegistry(instance.registry);

        _updateComponent(
            instanceId,
            componentId,
            instanceService.getComponentState(componentId)
        );
    }

    function components(bytes32 instanceId) 
        external override
        view 
        returns(uint256 numberOfComponents)
    {
        return _componentKeys[instanceId].length;
    }

    function getComponentId(bytes32 instanceId, uint256 idx) 
        external override 
        view 
        returns(uint256 componentId)
    {
        require(idx < _componentKeys[instanceId].length, "ERROR:CRG-040:COMPONENT_INDEX_TOO_LARGE");
        return _componentKeys[instanceId][idx].componentId;
    }

    function isRegisteredComponent(bytes32 instanceId, uint256 componentId) 
        external override 
        view 
        returns(bool isRegistered)
    {
        return _componentInfo[instanceId][componentId].createdAt > 0;
    }

    function getComponentInfo(bytes32 instanceId, uint256 componentId) 
        external override 
        view 
        returns(ComponentInfo memory info)
    {
        return _componentInfo[instanceId][componentId];
    }

    function _registerComponent(
        bytes32 instanceId,
        uint256 componentId,
        IComponent.ComponentType componentType,
        IComponent.ComponentState state
    )
        internal
    {
        ComponentInfo storage component = _componentInfo[instanceId][componentId];
        bool isNewComponent = component.createdAt == 0;

        if(isNewComponent) {
            component.key = ComponentKey(instanceId, componentId);
            component.createdAt = block.timestamp;

            _componentKeys[instanceId].push(component.key);
        }

        component.componentType = componentType;
        component.state = state;
        component.updatedAt = block.timestamp;

        emit LogInstanceRegistryComponentRegistered(
            instanceId,
            componentId,
            component.componentType,
            component.state,
            isNewComponent
        );
    }


    function _updateComponent(
        bytes32 instanceId,
        uint256 componentId,
        IComponent.ComponentState newState
    )
        internal
        onlyRegisteredComponent(instanceId, componentId)
    {
        ComponentInfo storage component = _componentInfo[instanceId][componentId];
        IComponent.ComponentState oldState = component.state;

        component.state = newState;
        component.updatedAt = block.timestamp;

        emit LogInstanceRegistryComponentUpdated(
            instanceId, 
            componentId, 
            oldState, 
            newState);
    }

}