// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

import "@etherisc/gif-interface/contracts/modules/IRegistry.sol";
import "@etherisc/gif-interface/contracts/services/IInstanceService.sol";

contract GifStaking is
    Ownable
{

    struct Instance {
        bytes32 id;
        uint256 chainId;
        address registry;
        uint256 registeredAt;
    }

    ERC20 private _dip;
    uint256 private _chainId;
    
    mapping(bytes32 /* instanceId */ => Instance) private _instance;
    mapping(bytes32 /* instanceId */ => mapping(uint256 /* bundleId */ => IBundle.Bundle)) private _bundle;


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
        require(_instance[instanceId].registeredAt == 0, "ERROR:STK-020:INSTANCE_ALREADY_REGISTERED");
        require(chainId > 0, "ERROR:STK-021:CHAIN_ID_ZERO");
        require(registry != address(0), "ERROR:STK-022:REGISTRY_CONTRACT_ADDRESS_ZERO");

        Instance storage instance = _instance[instanceId];
        instance.id = instanceId;
        instance.chainId = chainId;
        instance.registry = registry;
        instance.registeredAt = block.timestamp;
    }


    function registerBundleForStaking(
        bytes32 instanceId,
        uint256 bundleId
    )
        external
        onlyOwner()
    {
        require(_instance[instanceId].registeredAt > 0, "ERROR:STK-030:INSTANCE_NOT_REGISTERED");
        require(bundleId > 0, "ERROR:STK-031:BUNDLE_ID_ZERO");
    }
} 
