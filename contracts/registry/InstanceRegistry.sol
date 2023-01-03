// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";

import "@etherisc/gif-interface/contracts/modules/IRegistry.sol";
import "@etherisc/gif-interface/contracts/services/IInstanceService.sol";

import "./IInstanceDataProvider.sol";
import "./IInstanceRegistry.sol";

// TODO discuss upgradability for instance registry
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


    modifier onlyRegisteredToken(address token, uint256 chainId) {
        require(this.isRegisteredToken(token, chainId), "ERROR:IRG-001:TOKEN_NOT_REGISTERED");
        _;
    }


    modifier onlyRegisteredInstance(bytes32 instanceId) {
        require(this.isRegisteredInstance(instanceId), "ERROR:IRG-002:INSTANCE_NOT_REGISTERED");
        _;
    }


    modifier onlySameChain(bytes32 instanceId) {
        InstanceInfo memory info = getInstanceInfo(instanceId);
        require(block.chainid == info.chainId, "ERROR:CRG-003:DIFFERENT_CHAIN_NOT_SUPPORTET");
        _;
    }


    modifier onlyDifferentChain(uint256 chainId) {
        require(chainId != block.chainid, "ERROR:IRG-004:CALL_INVALID_FOR_SAME_CHAIN");
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
        onlyRegisteredToken(token, chainId)
        onlyOwner()
    {
        require(newState != TokenState.Undefined, "ERROR:IRG-011:TOKEN_STATE_INVALID");
        
        TokenState oldState =  _tokenInfo[token][chainId].state;
        _tokenInfo[token][chainId].state = newState;
        _tokenInfo[token][chainId].updatedAt = block.timestamp;
        
        emit LogInstanceRegistryTokenStateUpdated(token, chainId, oldState, newState);
    }

    function registerInstance(
        address registry
    )
        external override
        onlyOwner()
    {
        IInstanceService instanceService = _getInstanceService(registry);

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
        onlyDifferentChain(chainId)
        onlyOwner()
    {
        _registerInstance(
            instanceId,
            chainId,
            registry
        );
    }


    function updateInstance(
        bytes32 instanceId, 
        InstanceState newState 
    ) 
        external override
        onlyRegisteredInstance(instanceId)
        onlyOwner()
    {
        require(newState != InstanceState.Undefined, "ERROR:IRG-021:INSTANCE_STATE_INVALID");
        
        InstanceState oldState =  _instanceInfo[instanceId].state;
        _instanceInfo[instanceId].state = newState;
        _instanceInfo[instanceId].updatedAt = block.timestamp;

        emit LogInstanceRegistryInstanceStateUpdated(instanceId, oldState, newState);
    }


    function updateInstance(
        bytes32 instanceId, 
        string memory newDisplayName
    ) 
        external override
        onlyRegisteredInstance(instanceId)
        onlyOwner()
    {        
        string memory oldDisplayName =  _instanceInfo[instanceId].displayName;
        _instanceInfo[instanceId].displayName = newDisplayName;
        _instanceInfo[instanceId].updatedAt = block.timestamp;
        
        emit LogInstanceRegistryInstanceDisplayNameUpdated(instanceId, oldDisplayName, newDisplayName);

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
        require(chainId > 0, "ERROR:IRG-030:CHAIN_ID_ZERO");
        require(registry != address(0), "ERROR:IRG-031:REGISTRY_ADDRESS_ZERO");

        bool isValid = _validateInstance(instanceId, chainId, registry);
        require(isValid, "ERROR:IRG-032:INSTANCE_ID_INVALID");

        InstanceInfo storage instance = _instanceInfo[instanceId];
        bool isNewInstance = instance.createdAt == 0;

        if(isNewInstance) {
            instance.id = instanceId;
            instance.createdAt = block.timestamp;
            _instanceIds.push(instanceId);
        }

        instance.state = IInstanceDataProvider.InstanceState.Approved;
        instance.displayName = "";
        instance.chainId = chainId;
        instance.registry = registry;
        instance.updatedAt = block.timestamp;

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
        require(idx < _instanceIds.length, "ERROR:IRG-040:INSTANCE_INDEX_TOO_LARGE");
        return _instanceIds[idx];
    }

    function getInstanceInfo(
        bytes32 instanceId
    )
        public override
        view
        onlyRegisteredInstance(instanceId)
        returns(InstanceInfo memory info)
    {
        info = _instanceInfo[instanceId];
    }


    function probeInstance(
        address registryAddress
    )
        external override
        view 
        returns(
            bool isContract, 
            uint256 contractSize, 
            bool isValidId,
            bytes32 instanceId,
            IInstanceService instanceService
        )
    {
        contractSize = _getContractSize(registryAddress);
        isContract = (contractSize > 0);

        isValidId = false;
        instanceId = bytes32(0);
        instanceService = IInstanceService(address(0));

        if(isContract) {
            IRegistry registry = IRegistry(registryAddress);

            try registry.getContract("InstanceService") returns(address instanceServiceAddress) {
                instanceService = IInstanceService(instanceServiceAddress);
                instanceId = instanceService.getInstanceId();
                isValidId = (instanceId == keccak256(abi.encodePacked(block.chainid, registry)));
            }
            catch { } // no-empty-blocks is ok here (see default return values above)
        } 
    }


    function tokens() external override view returns(uint256 numberOfTokens) {
        return _tokenKeys.length;
    }

    function getTokenId(uint256 idx) external override view returns(address token, uint256 chainId) {
        require(idx < _tokenKeys.length, "ERROR:IRG-050:TOKEN_IDX_TOO_LARGE");
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
        onlyRegisteredToken(tokenAddress, chainId)
        public override
        view
        returns(TokenInfo memory tokenInfo)
    {
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
            (
                bool isContract,
                , // don't care about contract size
                bool hasValidId,
                bytes32 actualInstanceId,
                // don't care about instanceservice
            ) = this.probeInstance(registry);

            if(!isContract || !hasValidId) { 
                return false; 
            }
            
            if(actualInstanceId != instanceId) {
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
        require(token != address(0), "ERROR:IRG-100:TOKEN_ADDRESS_ZERO");
        require(chainId > 0, "ERROR:IRG-101:CHAIN_ID_ZERO");
        require(decimals > 0, "ERROR:IRG-102:DECIMALS_ZERO");
        require(decimals <= TOKEN_MAX_DECIMALS, "ERROR:IRG-103:DECIMALS_TOO_LARGE");

        TokenInfo storage info = _tokenInfo[token][chainId];
        bool isNewToken = info.createdAt == 0;

        if(isNewToken) {
            info.key = TokenKey(token, chainId);
            info.createdAt = block.timestamp;

            _tokenKeys.push(info.key);
        }

        info.state = IInstanceDataProvider.TokenState.Approved;
        info.symbol = symbol;
        info.decimals = decimals;
        info.updatedAt = block.timestamp;

        emit LogInstanceRegistryTokenRegistered(
            token,
            chainId,
            info.state,
            isNewToken
        );
    }
        
    
    // TODO remove and replace with probeInstance
    function _getInstanceService(
        address registryAddress
    )
        internal
        view
        returns(IInstanceService instanceService)
    {
        require(_getContractSize(registryAddress) > 0, "ERROR:IRG-120:REGISTRY_NOT_CONTRACT");

        IRegistry registry = IRegistry(registryAddress);
        
        try registry.getContract("InstanceService") returns(address instanceServiceAddress) {
            instanceService = IInstanceService(instanceServiceAddress);
        } catch {
            revert("ERROR:IRG-121:NOT_REGISTRY_CONTRACT");
        }
    }

    function _getContractSize(address contractAddress)
        internal
        view
        returns(uint256 size)
    {
        assembly {
            size := extcodesize(contractAddress)
        }
    }
}