// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

import "@etherisc/gif-interface/contracts/modules/IRegistry.sol";
import "@etherisc/gif-interface/contracts/services/IInstanceService.sol";

contract GifStaking is
    Ownable
{

    struct InstanceInfo {
        bytes32 id;
        uint256 chainId;
        address registry;
        uint256 registeredAt;
    }

    struct BundleInfo {
        uint256 bundleId;
        IBundle.BundleState state;
        uint256 createdAt;
        uint256 updatedAt;
    }


    ERC20 private _dip;
    bytes32 [] private _instanceIds;
    
    mapping(bytes32 /* instanceId */ => InstanceInfo) private _instanceInfo;
    mapping(bytes32 /* instanceId */ => mapping(uint256 /* bundleId */ => BundleInfo)) private _bundleInfo;


    modifier instanceOnSameChain(bytes32 instanceId) {
        require(_instanceInfo[instanceId].registeredAt > 0, "ERROR:STK-001:INSTANCE_NOT_REGISTERED");
        require(_instanceInfo[instanceId].chainId == block.chainid, "ERROR:STK-002:INSTANCE_NOT_ON_THIS_CHAIN");
        _;
    }


    modifier instanceOnDifferentChain(bytes32 instanceId) {
        require(_instanceInfo[instanceId].registeredAt > 0, "ERROR:STK-001:INSTANCE_NOT_REGISTERED");
        require(_instanceInfo[instanceId].chainId != block.chainid, "ERROR:STK-002:INSTANCE_ON_THIS_CHAIN");
        _;
    }


    constructor(address dipTokenAddress) 
        Ownable()
    {
        require(dipTokenAddress != address(0), "ERROR:STK-010:DIP_CONTRACT_ADDRESS_ZERO");

        _dip = ERC20(dipTokenAddress);
    }


    function registerGifInstance(
        bytes32 instanceId,
        uint256 chainId,
        address registry
    )
        external
        onlyOwner()
    {
        require(_instanceInfo[instanceId].registeredAt == 0, "ERROR:STK-020:INSTANCE_ALREADY_REGISTERED");
        require(chainId > 0, "ERROR:STK-021:CHAIN_ID_ZERO");
        require(registry != address(0), "ERROR:STK-022:REGISTRY_CONTRACT_ADDRESS_ZERO");

        bool isValid = _validateInstance(instanceId, chainId, registry);
        require(isValid, "ERROR:STK-023:INSTANCE_INVALID");

        InstanceInfo storage instance = _instanceInfo[instanceId];
        instance.id = instanceId;
        instance.chainId = chainId;
        instance.registry = registry;
        instance.registeredAt = block.timestamp;

        _instanceIds.push(instanceId);
    }


    function updateBundleState(
        bytes32 instanceId,
        uint256 bundleId
    )
        external
        onlyOwner()
        instanceOnSameChain(instanceId)
    {
        IInstanceService instanceService = _getInstanceService(instanceId);
        IBundle.Bundle memory bundle = instanceService.getBundle(bundleId);

        _updateBundleState(instanceId, bundleId, bundle.state);
    }


    function updateBundleState(
        bytes32 instanceId,
        uint256 bundleId,
        IBundle.BundleState state        
    )
        external
        onlyOwner()
        instanceOnDifferentChain(instanceId)
    {
        require(bundleId > 0, "ERROR:STK-030:BUNDLE_ID_ZERO");

        _updateBundleState(instanceId, bundleId, state);
    }


    function getBundleInfo(
        bytes32 instanceId,
        uint256 bundleId
    )
        external
        view
        returns(BundleInfo memory info)
    {
        require(_instanceInfo[instanceId].registeredAt > 0, "ERROR:STK-040:INSTANCE_NOT_REGISTERED");

        info = _bundleInfo[instanceId][bundleId];
        require(info.createdAt > 0, "ERROR:STK-041:BUNDLE_NOT_REGISTERED");
    }


    function instances() external view returns(uint256 numberOfInstances) {
        return _instanceIds.length;
    }

    function getInstanceId(uint256 idx) external view returns(bytes32 instanceId) {
        require(idx < _instanceIds.length, "ERROR:STK-090:INSTANCE_INDEX_TOO_LARGE");
        return _instanceIds[idx];
    }

    function getInstanceInfo(
        bytes32 instanceId
    )
        external
        view
        returns(InstanceInfo memory info)
    {
        require(_instanceInfo[instanceId].registeredAt > 0, "ERROR:STK-091:INSTANCE_NOT_REGISTERED");
        info = _instanceInfo[instanceId];
    }


    function getDip() external view returns(ERC20 dip) {
        return _dip;
    }

    function _updateBundleState(
        bytes32 instanceId,
        uint256 bundleId,
        IBundle.BundleState state        
    )
        internal
    {
        BundleInfo storage info = _bundleInfo[instanceId][bundleId];
        
        if(info.createdAt == 0) {
            info.bundleId = bundleId;
            info.createdAt = block.timestamp;
        }

        info.state = state;
        info.updatedAt = block.timestamp;
    }


    function _validateInstance(
        bytes32 instanceId,
        uint256 chainId,
        address registry
    )
        internal
        view
        returns(bool isValid)
    {
        // validate via call if on same chain
        if(chainId == block.chainid) {
            IInstanceService instanceService = _getInstanceServiceFromRegistry(registry);
            if(instanceService.getInstanceId() != instanceId) {
                return false;
            }
        }
        // validation for instances on different chain
        else if(instanceId != keccak256(abi.encodePacked(chainId, registry))) {
            return false;
        }

        return true;
    }
    
    
    function _getInstanceService(
        bytes32 instanceId
    )
        internal
        view
        returns(IInstanceService instanceService)
    {
        require(_instanceInfo[instanceId].registeredAt > 0, "ERROR:STK-030:INSTANCE_NOT_REGISTERED");
        return _getInstanceServiceFromRegistry(_instanceInfo[instanceId].registry);
    }
    
    
    function _getInstanceServiceFromRegistry(
        address registryAddress
    )
        internal
        view
        returns(IInstanceService instanceService)
    {
        IRegistry registry = IRegistry(registryAddress);
        instanceService = IInstanceService(registry.getContract("InstanceService"));
    }
} 
