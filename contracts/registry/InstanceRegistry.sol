// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";

import "@etherisc/gif-interface/contracts/modules/IRegistry.sol";
import "@etherisc/gif-interface/contracts/services/IInstanceService.sol";

import "./IInstanceDataProvider.sol";
import "./IInstanceRegistry.sol";

contract InstanceRegistry is
    IInstanceDataProvider,
    IInstanceRegistry,
    Ownable
{

    uint256 public constant TOKEN_MAX_DECIMALS = 18;

    // token 
    mapping(address /* token address */ => mapping(uint256 /* chainId */ => TokenInfo)) private _tokenInfo;

    // instance state
    mapping(bytes32 /* instanceId */ => InstanceInfo) private _instanceInfo;

    bytes32 [] private _instanceIds;
    TokenKey [] private _tokenKeys;

    modifier onlyDifferentChain(uint256 chainId) {
        require(chainId != block.chainid, "ERROR:IRG-005:CALL_INVALID_FOR_SAME_CHAIN");
        _;
    }

    constructor() 
        Ownable()
    { }

    function registerToken(address tokenAddress)
        external override
        onlyOwner()
    {
        IERC20Metadata token = IERC20Metadata(tokenAddress);
        _registerToken(
            tokenAddress,
            block.chainid,
            token.decimals(),
            token.symbol()
        );
    }

    function registerToken(
        address tokenAddress,
        uint256 chainId,
        uint8 decimals,
        string memory symbol
    )
        external override
        onlyOwner()
        onlyDifferentChain(chainId)
    {
        _registerToken(
            tokenAddress,
            chainId,
            decimals,
            symbol
        );
    }

    function updateToken(
        address token, 
        uint256 chainId, 
        TokenState newState
    ) 
        external override
    {
        require(_tokenInfo[token][chainId].createdAt > 0, "ERROR:IRG-010:TOKEN_NOT_REGISTERED");
        require(newState != TokenState.Undefined, "ERROR:IRG-010:TOKEN_STATE_INVALID");
        
        TokenState oldState =  _tokenInfo[token][chainId].state;
        _tokenInfo[token][chainId].state = newState;
        
        emit LogInstanceRegistryTokenUpdated(token, chainId, oldState, newState);
    }

    function registerInstance(
        address registry
    )
        external override
        onlyOwner()
    {
        IInstanceService instanceService = _getInstanceServiceFromRegistry(registry);

        _registerInstance(
            instanceService.getInstanceId(),
            block.chainid,
            registry
        );
    }


    function registerInstance(
        bytes32 instanceId,
        uint256 chainId,
        address registry
    )
        external override
        onlyOwner()
        onlyDifferentChain(chainId)
    {
        _registerInstance(
            instanceId,
            chainId,
            registry
        );
    }


    function updateInstance(
        bytes32 instanceId, 
        InstanceState state 
    ) 
        external override
    {

    }


    function updateInstance(
        bytes32 instanceId, 
        string memory displayName
    ) 
        external override
    {

    }

    function isRegisteredToken(address tokenAddress) 
        external override 
        view 
        returns(bool isRegistered)
    {
        return _tokenInfo[tokenAddress][block.chainid].createdAt > 0;
    }


    function isRegisteredToken(address tokenAddress, uint256 chainId) 
        external override 
        view 
        returns(bool isRegistered)
    {
        return _tokenInfo[tokenAddress][chainId].createdAt > 0;
    }

    function isRegisteredInstance(bytes32 instanceId) 
        external override
        view 
        returns(bool isRegistered)
    {
        return _instanceInfo[instanceId].createdAt > 0;
    }

    function _registerInstance(
        bytes32 instanceId,
        uint256 chainId,
        address registry
    )
        internal
    {
        require(chainId > 0, "ERROR:STK-021:CHAIN_ID_ZERO");
        require(registry != address(0), "ERROR:STK-022:REGISTRY_CONTRACT_ADDRESS_ZERO");

        bool isValid = _validateInstance(instanceId, chainId, registry);
        require(isValid, "ERROR:STK-023:INSTANCE_ID_INVALID");

        InstanceInfo storage info = _instanceInfo[instanceId];
        bool isNewInstance = info.createdAt == 0;

        InstanceInfo storage instance = _instanceInfo[instanceId];
        instance.id = instanceId;
        instance.state = IInstanceDataProvider.InstanceState.Approved;
        instance.displayName = "";
        instance.chainId = chainId;
        instance.registry = registry;
        instance.updatedAt = block.timestamp;

        if(isNewInstance) {
            info.createdAt = block.timestamp;
            _instanceIds.push(instanceId);
        }

        emit LogInstanceRegistryInstanceRegistered(
            instance.id,
            instance.state,
            isNewInstance
        );
    }


    function instances() external override view returns(uint256 numberOfInstances) {
        return _instanceIds.length;
    }

    function getInstanceId(uint256 idx) external override view returns(bytes32 instanceId) {
        require(idx < _instanceIds.length, "ERROR:STK-061:INSTANCE_INDEX_TOO_LARGE");
        return _instanceIds[idx];
    }

    function getInstanceInfo(
        bytes32 instanceId
    )
        public override
        view
        returns(InstanceInfo memory info)
    {
        require(_instanceInfo[instanceId].createdAt > 0, "ERROR:STK-062:INSTANCE_NOT_REGISTERED");
        info = _instanceInfo[instanceId];
    }

    function tokens() external override view returns(uint256 numberOfTokens) {
        return _tokenKeys.length;
    }

    function getTokenId(uint256 idx) external override view returns(address token, uint256 chainId) {
        require(idx < _tokenKeys.length, "ERROR:STK-090:TOKEN_IDX_TOO_LARGE");
        return (_tokenKeys[idx].token, _tokenKeys[idx].chainId);
    }

    function getTokenInfo(address token)
        external override
        view
        returns(TokenInfo memory tokenInfo)
    {
        return getTokenInfo(token, block.chainid);
    }


    function getTokenInfo(
        address tokenAddress,
        uint256 chainId
    )
        public override
        view
        returns(TokenInfo memory tokenInfo)
    {
        require(_tokenInfo[tokenAddress][chainId].createdAt > 0, "ERROR:STK-091:TOKEN_NOT_REGISTERED");
        return _tokenInfo[tokenAddress][chainId];
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


    function _registerToken(
        address token,
        uint256 chainId,
        uint8 decimals,
        string memory symbol
    )
        internal
    {
        require(token != address(0), "ERROR:STK-101:TOKEN_ADDRESS_ZERO");
        require(chainId > 0, "ERROR:STK-102:CHAIN_ID_ZERO");
        require(decimals > 0, "ERROR:STK-103:DECIMALS_ZERO");
        require(decimals <= TOKEN_MAX_DECIMALS, "ERROR:STK-104:DECIMALS_TOO_LARGE");

        TokenInfo storage info = _tokenInfo[token][chainId];
        bool isNewToken = info.createdAt == 0;

        info.key = TokenKey(token, chainId);
        info.state = IInstanceDataProvider.TokenState.Approved;
        info.symbol = symbol;
        info.decimals = decimals;
        info.updatedAt = block.timestamp;

        if(isNewToken) {
            info.createdAt = block.timestamp;
            _tokenKeys.push(info.key);
        }

        emit LogInstanceRegistryTokenRegistered(
            token,
            chainId,
            info.state,
            isNewToken
        );
    }
    

    function _getInstanceService(
        bytes32 instanceId
    )
        internal
        view
        returns(IInstanceService instanceService)
    {
        require(_instanceInfo[instanceId].createdAt > 0, "ERROR:STK-130:INSTANCE_NOT_REGISTERED");
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