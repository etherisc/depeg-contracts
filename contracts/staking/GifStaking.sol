// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";

import "@etherisc/gif-interface/contracts/modules/IRegistry.sol";
import "@etherisc/gif-interface/contracts/services/IInstanceService.sol";

contract GifStaking is
    Ownable
{

    struct InstanceInfo {
        bytes32 id;
        uint256 chainId;
        address registry;
        uint256 createdAt;
    }

    struct BundleInfo {
        uint256 id;
        IBundle.BundleState state;
        uint256 closedSince;
        uint256 createdAt;
        uint256 updatedAt;
    }

    struct StakeInfo {
        address staker;
        bytes32 instanceId;
        uint256 bundleId;
        uint256 balance;
        uint256 createdAt;
        uint256 updatedAt;
    }

    address public constant DIP_CONTRACT_ADDRESS = 0xc719d010B63E5bbF2C0551872CD5316ED26AcD83;
    uint256 public constant DIP_DECIMALS = 18;
    uint256 public constant DIP_TO_TOKEN_PARITY_LEVEL_DECIMALS = 18;
    uint256 public constant DIP_TO_TOKEN_PARITY_LEVEL = 10**DIP_TO_TOKEN_PARITY_LEVEL_DECIMALS;

    uint256 public constant YIELD_100_PERCENTAGE = 10**6;
    uint256 public constant YIELD_MAX_PERCENTAGE = YIELD_100_PERCENTAGE / 3;
    uint256 public constant ONE_YEAR_DURATION = 365 * 24 * 3600; 

    IERC20Metadata private _dip;
    uint256 private _yield;
    bytes32 [] private _instanceIds;
    address private _stakingWallet;
    
    // dip to token conversion rate
    mapping(uint256 /* chainId */ => mapping(address /* tokenAddress */ => uint256 /* rate */ )) private _dipConversionRate;
    mapping(uint256 /* chainId */ => mapping(address /* tokenAddress */ => uint256 /* decimals */ )) private _tokenDecimals;
    
    // instance and bundle state
    mapping(bytes32 /* instanceId */ => InstanceInfo) private _instanceInfo;
    mapping(bytes32 /* instanceId */ => mapping(uint256 /* bundleId */ => BundleInfo)) private _bundleInfo;

    // staking state
    mapping(bytes32 /* instanceId */ => mapping(uint256 /* bundleId */ => mapping(address /* stake owner */ => StakeInfo))) private _stakeInfo;
    mapping(bytes32 /* instanceId */ => mapping(uint256 /* bundleId */ => uint256 /* amount staked */)) private _stakedAmount;
    mapping(bytes32 /* instanceId */ => uint256 /* amount staked */) private _instanceStakedAmount;
    uint256 private _overallStakedAmount;


    modifier instanceOnSameChain(bytes32 instanceId) {
        require(_instanceInfo[instanceId].createdAt > 0, "ERROR:STK-001:INSTANCE_NOT_REGISTERED");
        require(_instanceInfo[instanceId].chainId == block.chainid, "ERROR:STK-002:INSTANCE_NOT_ON_THIS_CHAIN");
        _;
    }


    modifier instanceOnDifferentChain(bytes32 instanceId) {
        require(_instanceInfo[instanceId].createdAt > 0, "ERROR:STK-003:INSTANCE_NOT_REGISTERED");
        require(_instanceInfo[instanceId].chainId != block.chainid, "ERROR:STK-004:INSTANCE_ON_THIS_CHAIN");
        _;
    }


    constructor() 
        Ownable()
    {
        _dip = IERC20Metadata(DIP_CONTRACT_ADDRESS);
        _stakingWallet = address(this);
    }


    function setDipContract(address dipTokenAddress) 
        external
        onlyOwner()
    {
        require(block.chainid != 1, "ERROR:STK-010:DIP_ADDRESS_CHANGE_NOT_ALLOWED_ON_MAINNET");
        require(dipTokenAddress != address(0), "ERROR:STK-011:DIP_CONTRACT_ADDRESS_ZERO");

        _dip = IERC20Metadata(dipTokenAddress);
    }

    // dip conversion rate: value of 1 dip in amount of provided token 
    function setDipConversionRate(uint256 chainId, address tokenAddress, uint256 tokenDecimals, uint256 conversionRate) 
        external
        onlyOwner()
    {
        require(chainId > 0, "ERROR:STK-012:CHAIN_ID_ZERO");
        require(tokenAddress != address(0), "ERROR:STK-013:TOKEN_ADDRESS_ZERO");
        require(tokenDecimals > 0, "ERROR:STK-014:TOKEN_DECIMALS_ZERO");
        require(conversionRate > 0, "ERROR:STK-015:CONVERSION_RATE_ZERO");

        _dipConversionRate[chainId][tokenAddress] = conversionRate;
        _tokenDecimals[chainId][tokenAddress] = conversionRate;

        // special case for on chain token
        if(chainId == block.chainid) {
            IERC20Metadata token = IERC20Metadata(tokenAddress);
            _tokenDecimals[chainId][tokenAddress] = token.decimals();
        }
    }


    function setYield(uint256 yield)
        external
        onlyOwner
    {
        require(yield <= YIELD_MAX_PERCENTAGE, "ERROR:STK-016:YIELD_EXEEDS_MAX_VALUE");
        _yield = yield;
    }


    function registerGifInstance(
        bytes32 instanceId,
        uint256 chainId,
        address registry
    )
        external
        onlyOwner()
    {
        require(_instanceInfo[instanceId].createdAt == 0, "ERROR:STK-020:INSTANCE_ALREADY_REGISTERED");
        require(chainId > 0, "ERROR:STK-021:CHAIN_ID_ZERO");
        require(registry != address(0), "ERROR:STK-022:REGISTRY_CONTRACT_ADDRESS_ZERO");

        bool isValid = _validateInstance(instanceId, chainId, registry);
        require(isValid, "ERROR:STK-023:INSTANCE_INVALID");

        InstanceInfo storage instance = _instanceInfo[instanceId];
        instance.id = instanceId;
        instance.chainId = chainId;
        instance.registry = registry;
        instance.createdAt = block.timestamp;

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


    function stake(
        bytes32 instanceId, 
        uint256 bundleId, 
        uint256 amount
    )
        external
    {
        require(amount > 0, "ERROR:STK-040:STAKING_AMOUNT_ZERO");

        BundleInfo memory info = getBundleInfo(instanceId, bundleId);
        require(
            info.state == IBundle.BundleState.Active
            || info.state == IBundle.BundleState.Locked, 
            "ERROR:STK-041:BUNDLE_CLOSED_OR_BURNED"
        );

        address staker = msg.sender;
        StakeInfo storage stakeInfo = _stakeInfo[instanceId][bundleId][staker];

        // handling for new stakes
        if(stakeInfo.createdAt == 0) {
            stakeInfo.staker = staker;
            stakeInfo.instanceId = instanceId;
            stakeInfo.bundleId = bundleId;
            stakeInfo.createdAt = block.timestamp;
        }

        uint256 amountIncludingYields = amount + calculateYieldIncrement(stakeInfo);
        _increaseBundleStakes(stakeInfo, amountIncludingYields);
        _collectStakes(staker, amount);
    }


    function withdraw(
        bytes32 instanceId, 
        uint256 bundleId
    )
        external
    {
        withdraw(instanceId, bundleId, type(uint256).max);
    }


    function withdraw(
        bytes32 instanceId, 
        uint256 bundleId, 
        uint256 amount
    )
        public
    {
        require(amount > 0, "ERROR:STK-050:WITHDRAWAL_AMOUNT_ZERO");

        address staker = msg.sender;
        StakeInfo storage stakeInfo = _stakeInfo[instanceId][bundleId][staker];
        require(stakeInfo.updatedAt > 0, "ERROR:STK-051:ACCOUNT_WITHOUT_STAKING_RECORD");

        stakeInfo.balance += calculateYieldIncrement(stakeInfo);

        if(amount == type(uint256).max) {
            amount = stakeInfo.balance;
        }

        _decreaseBundleStakes(stakeInfo, amount);
        _payoutStakes(staker, amount);
    }


    function getOneYearDuration() public pure returns(uint256 yearDuration) { 
        return ONE_YEAR_DURATION;
    }


    function getYield100PercentLevel() public pure returns(uint256 yield100PercentLevel) { 
        return YIELD_100_PERCENTAGE;
    }


    function getDipToTokenParityLevel() external pure returns(uint256 parityLevel) {
        return DIP_TO_TOKEN_PARITY_LEVEL;
    }


    function getDip() external view returns(IERC20Metadata dip) {
        return _dip;
    }


    function getDipConversionRate(uint256 chainId, address tokenAddress)
        public
        view
        returns(uint256 conversionRate)
    {
        conversionRate = _dipConversionRate[chainId][tokenAddress];
        require(_dipConversionRate[chainId][tokenAddress] > 0, "ERROR:STK-060:CONVERSION_RATE_ZERO");
    }


    function convertToTokenAmount(
        uint256 dipAmount,
        uint256 chainId, 
        address tokenAddress 
    )
        external
        view
        returns(uint256 tokenAmount)
    {
        uint256 conversionRate = getDipConversionRate(chainId, tokenAddress);
        uint256 tokenDecimals = _tokenDecimals[chainId][tokenAddress];
        uint256 numerator = 1;
        uint256 denominator = 1;

        if(DIP_DECIMALS + DIP_TO_TOKEN_PARITY_LEVEL_DECIMALS >= tokenDecimals) {
            denominator = 10**(DIP_DECIMALS + DIP_TO_TOKEN_PARITY_LEVEL_DECIMALS - tokenDecimals); 
        }
        else {
            numerator = 10**(tokenDecimals - (DIP_DECIMALS + DIP_TO_TOKEN_PARITY_LEVEL_DECIMALS));
        }

        tokenAmount = (dipAmount * conversionRate * numerator) / denominator;
    }


    function getStakingWallet()
        public
        view
        returns(address instanceWallet)
    {
        return _stakingWallet;
    }


    function instances() external view returns(uint256 numberOfInstances) {
        return _instanceIds.length;
    }

    function getInstanceId(uint256 idx) external view returns(bytes32 instanceId) {
        require(idx < _instanceIds.length, "ERROR:STK-061:INSTANCE_INDEX_TOO_LARGE");
        return _instanceIds[idx];
    }

    function getInstanceInfo(
        bytes32 instanceId
    )
        external
        view
        returns(InstanceInfo memory info)
    {
        require(_instanceInfo[instanceId].createdAt > 0, "ERROR:STK-062:INSTANCE_NOT_REGISTERED");
        info = _instanceInfo[instanceId];
    }


    function getBundleInfo(
        bytes32 instanceId,
        uint256 bundleId
    )
        public
        view
        returns(BundleInfo memory info)
    {
        require(_instanceInfo[instanceId].createdAt > 0, "ERROR:STK-070:INSTANCE_NOT_REGISTERED");

        info = _bundleInfo[instanceId][bundleId];
        require(info.createdAt > 0, "ERROR:STK-071:BUNDLE_NOT_REGISTERED");
    }


    function getStakeInfo(
        bytes32 instanceId, 
        uint256 bundleId, 
        address staker
    )
        external
        view
        returns(StakeInfo memory stakeInfo)
    {
        stakeInfo = _stakeInfo[instanceId][bundleId][staker];
        require(stakeInfo.updatedAt > 0, "ERROR:STK-080:ACCOUNT_WITHOUT_STAKING_RECORD");

        return stakeInfo;
    }


    // maybe rename to staked()?
    function stakes(
        bytes32 instanceId, 
        uint256 bundleId, 
        address staker
    )
        external
        view
        returns(uint256 amount)
    {
        BundleInfo memory info = getBundleInfo(instanceId, bundleId);
        require(info.createdAt > 0, "ERROR:STK-081:BUNDLE_NOT_REGISTERED");
        
        amount = _stakeInfo[instanceId][bundleId][staker].balance;
    }


    function stakes(
        bytes32 instanceId, 
        uint256 bundleId
    )
        external
        view
        returns(uint256 amount)
    {
        BundleInfo memory info = getBundleInfo(instanceId, bundleId);
        require(info.createdAt > 0, "ERROR:STK-082:BUNDLE_NOT_REGISTERED");

        amount = _stakedAmount[instanceId][bundleId];
    }


    function stakes(
        bytes32 instanceId
    )
        external
        view
        returns(uint256 amount)
    {
        InstanceInfo memory info = _instanceInfo[instanceId];
        require(info.createdAt > 0, "ERROR:STK-083:INSTANCE_NOT_REGISTERED");

        amount = _instanceStakedAmount[instanceId];
    }


    function stakes() external view returns(uint256 amount) {
        return _overallStakedAmount;
    }


    function calculateYieldIncrement(StakeInfo memory stakeInfo)
        public
        view
        returns(uint256 yieldAmount)
    {
        uint256 timeSinceLastUpdate = block.timestamp - stakeInfo.updatedAt;

        // TODO potentially reduce time depending on the time when the bundle has been closed

        yieldAmount = calculateYield(stakeInfo.balance, timeSinceLastUpdate);
    }


    function calculateYield(
        uint256 amount,
        uint256 duration
    ) 
        public view
        returns(uint256 yieldAmount) 
    {
        uint256 durationYield = _yield * duration / ONE_YEAR_DURATION;
        yieldAmount = amount * durationYield / YIELD_100_PERCENTAGE;
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


    function _updateBundleState(
        bytes32 instanceId,
        uint256 bundleId,
        IBundle.BundleState state        
    )
        internal
    {
        BundleInfo storage info = _bundleInfo[instanceId][bundleId];
        
        // handling for new bundles
        if(info.createdAt == 0) {
            info.id = bundleId;
            info.createdAt = block.timestamp;
        }

        // handling of first state change to closed state
        if(state == IBundle.BundleState.Closed && info.closedSince == 0) {
            info.closedSince = block.timestamp;
        }

        info.state = state;
        info.updatedAt = block.timestamp;
    }


    function _increaseBundleStakes(
        StakeInfo storage stakeInfo,
        uint256 amount
    )
        internal
    {
        _stakedAmount[stakeInfo.instanceId][stakeInfo.bundleId] += amount;
        _instanceStakedAmount[stakeInfo.instanceId] += amount;
        _overallStakedAmount += amount;

        stakeInfo.balance += amount;
        stakeInfo.updatedAt = block.timestamp;
    }


    function _decreaseBundleStakes(
        StakeInfo storage stakeInfo,
        uint256 amount
    )
        internal
    {
        require(amount <= stakeInfo.balance, "ERROR:STK-090:WITHDRAWAL_AMOUNT_EXCEEDS_STAKING_BALANCE");
        _stakedAmount[stakeInfo.instanceId][stakeInfo.bundleId] -= amount;
        _instanceStakedAmount[stakeInfo.instanceId] -= amount;
        _overallStakedAmount -= amount;

        stakeInfo.balance -= amount;
        stakeInfo.updatedAt = block.timestamp;
    }
    


    function _collectStakes(address staker, uint256 amount)
        internal
    {
        _dip.transferFrom(staker, _stakingWallet, amount);
    }


    function _payoutStakes(address staker, uint256 amount)
        internal
    {
        if(_stakingWallet != address(this)) {
            _dip.transferFrom(_stakingWallet, staker, amount);
        }
        else {
            _dip.transfer(staker, amount);
        }
    }
    

    function _getInstanceService(
        bytes32 instanceId
    )
        internal
        view
        returns(IInstanceService instanceService)
    {
        require(_instanceInfo[instanceId].createdAt > 0, "ERROR:STK-100:INSTANCE_NOT_REGISTERED");
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
