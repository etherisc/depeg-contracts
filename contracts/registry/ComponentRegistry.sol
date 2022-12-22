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

    modifier onlyRegisteredInstance(bytes32 instanceId) {
        require(this.isRegisteredInstance(instanceId), "ERROR:CRG-001:INSTANCE_NOT_REGISTERED");
        _;
    }

    modifier onlySameChain(bytes32 instanceId) {
        InstanceInfo memory info = getInstanceInfo(instanceId);
        require(block.chainid == info.chainId, "ERROR:CRG-002:INSTANCE_ON_DIFFERENT_CHAIN");
        _;
    }

    function registerComponent(bytes32 instanceId, uint256 riskpoolId) 
        external override
        onlyRegisteredInstance(instanceId)
        onlySameChain(instanceId)
        onlyOwner()
    {
        // TODO implement
    }


    function updateComponent(bytes32 instanceId, uint256 riskpoolId)
        external override
        onlyRegisteredInstance(instanceId)
        onlySameChain(instanceId)
        onlyOwner()
    {
        // TODO implement
    }

    function components(bytes32 instanceId) 
        external override
        view 
        returns(uint256 numberOfComponents)
    {
        // TODO implement
    }

    function getComponentId(bytes32 instanceId, uint256 idx) 
        external override 
        view 
        returns(uint256 componentId)
    {
        // TODO implement
    }

    function isRegisteredComponent(bytes32 instanceId, uint256 componentId) 
        external override 
        view 
        returns(bool isRegistered)
    {
        // TODO implement
    }

    function getComponentInfo(bytes32 instanceId, uint256 componentId) 
        external override 
        view 
        returns(ComponentInfo memory info)
    {
        // TODO implement
    }

}