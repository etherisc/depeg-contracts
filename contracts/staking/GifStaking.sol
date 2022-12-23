// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";

import "@etherisc/gif-interface/contracts/modules/IRegistry.sol";
import "@etherisc/gif-interface/contracts/services/IInstanceService.sol";

import "../registry/IBundleDataProvider.sol";
import "./IStakingDataProvider.sol";

// TODO check/compare for function naming https://github.com/ethereum/EIPs/issues/900
contract GifStaking is
    IBundleDataProvider,
    IStakingDataProvider,
    Ownable
{

    // enum InstanceState {
    //     Undefined,
    //     Active,
    //     Suspended,
    //     Archived
    // }

    // struct InstanceInfo {
    //     bytes32 id;
    //     InstanceState state;
    //     string displayName;
    //     uint256 chainId;
    //     address registry;
    //     uint256 createdAt;
    //     uint256 updatedAt;
    // }

    // struct TokenKey {
    //     address token;
    //     uint256 chainId;
    // }

    // enum TokenState {
    //     Undefined,
    //     Approved,
    //     Suspended
    // }
    // struct TokenInfo {
    //     TokenKey key;
    //     TokenState state;
    //     string symbol;
    //     uint8 decimals;
    //     uint256 createdAt;
    // }

    // struct BundleKey {
    //     bytes32 instanceId;
    //     uint256 bundleId;
    // }

    // struct BundleInfo {
    //     BundleKey key;
    //     TokenKey tokenKey;
    //     string tokenSymbol;
    //     uint8 tokenDecimals;
    //     IBundle.BundleState state;
    //     uint256 closedSince;
    //     uint256 createdAt;
    //     uint256 updatedAt;
    // }

    struct StakeInfo {
        address staker;
        BundleKey key;
        uint256 balance;
        uint256 createdAt;
        uint256 updatedAt;
    }

    uint256 public constant MAINNET_ID = 1;

    uint256 public constant TOKEN_MAX_DECIMALS = 18;

    address public constant DIP_CONTRACT_ADDRESS = 0xc719d010B63E5bbF2C0551872CD5316ED26AcD83;
    uint256 public constant DIP_DECIMALS = 18;
    uint256 public constant DIP_TO_TOKEN_PARITY_LEVEL_DECIMALS = TOKEN_MAX_DECIMALS;
    uint256 public constant DIP_TO_TOKEN_PARITY_LEVEL = 10**DIP_TO_TOKEN_PARITY_LEVEL_DECIMALS;

    uint256 public constant REWARD_100_PERCENTAGE = 10**6;
    uint256 public constant REWARD_MAX_PERCENTAGE = REWARD_100_PERCENTAGE / 3;
    uint256 public constant ONE_YEAR_DURATION = 365 * 24 * 3600; 

    // dip to token staking rate
    mapping(uint256 /* chainId */ => mapping(address /* tokenAddress */ => uint256 /* rate */ )) private _dipStakingRate;

    // instance and bundle state
    mapping(bytes32 /* instanceId */ => InstanceInfo) private _instanceInfo;
    mapping(bytes32 /* instanceId */ => mapping(uint256 /* bundleId */ => BundleInfo)) private _bundleInfo;

    // token 
    mapping(address /* token address */ => mapping(uint256 /* chainId */ => TokenInfo)) private _tokenInfo;

    // staking state
    mapping(bytes32 /* instanceId */ => mapping(uint256 /* bundleId */ => mapping(address /* stake owner */ => StakeInfo))) private _stakeInfo;
    mapping(bytes32 /* instanceId */ => mapping(uint256 /* bundleId */ => uint256 /* amount staked */)) private _stakedAmount;
    mapping(bytes32 /* instanceId */ => uint256 /* amount staked */) private _instanceStakedAmount;

    IERC20Metadata private _dip;
    uint256 private _rewardPercentage;

    bytes32 [] private _instanceIds;
    TokenKey [] private _tokenKeys;
    BundleKey [] private _bundleKeys;

    uint256 private _overallStakedAmount;
    address private _stakingWallet;


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


    modifier differentChain(uint256 chainId) {
        require(chainId != block.chainid, "ERROR:STK-005:TOKEN_ON_THIS_CHAIN");
        _;
    }


    constructor() 
        Ownable()
    {
        _dip = IERC20Metadata(DIP_CONTRACT_ADDRESS);
        _stakingWallet = address(this);
    }

    // temporary hack until GifStaking is replaced by rewritten contract

    // instance data provider
    function getTokenId(uint256 idx) external override view returns(address tokenAddress, uint256 chainId) {}
    function isRegisteredToken(address tokenAddress) external override view returns(bool isRegistered) {}
    function isRegisteredToken(address tokenAddress, uint256 chainId) external override view returns(bool isRegistered) {}

    function isRegisteredInstance(bytes32 instanceId) external override view returns(bool isRegistered) {}

    // component data provider
    function components(bytes32 instanceId) external override view returns(uint256 numberOfComponents) {}
    function getComponentId(bytes32 instanceId, uint256 idx) external override view returns(uint256 componentId) {}

    function isRegisteredComponent(bytes32 instanceId, uint256 componentId) external override view returns(bool isRegistered) {}
    function getComponentInfo(bytes32 instanceId, uint256 componentId) external override view returns(ComponentInfo memory info) {}

    // bundle data provider
    function bundles(bytes32 instanceId, uint256 riskpoolId) external override view returns(uint256 numberOfBundles) {}
    function getBundleId(bytes32 instanceId, uint256 riskpoolId, uint256 idx) external override view returns(uint256 bundleId) {}


    function setDipContract(address dipTokenAddress) 
        external
        onlyOwner()
    {
        require(block.chainid != MAINNET_ID, "ERROR:STK-010:DIP_ADDRESS_CHANGE_NOT_ALLOWED_ON_MAINNET");
        require(dipTokenAddress != address(0), "ERROR:STK-011:DIP_CONTRACT_ADDRESS_ZERO");

        _dip = IERC20Metadata(dipTokenAddress);
    }

    // dip staking rate: value of 1 dip in amount of provided token 
    function setDipStakingRate(
        address tokenAddress, 
        uint256 chainId, 
        uint256 stakingRate
    ) 
        external
        onlyOwner()
    {
        require(_tokenInfo[tokenAddress][chainId].createdAt > 0, "ERROR:STK-012:TOKEN_NOT_REGISTERED");
        require(stakingRate > 0, "ERROR:STK-015:STAKING_RATE_ZERO");
        _dipStakingRate[chainId][tokenAddress] = stakingRate;
    }

    function setRewardPercentage(uint256 rewardPercentage)
        external
        onlyOwner
    {
        require(rewardPercentage <= REWARD_MAX_PERCENTAGE, "ERROR:STK-016:REWARD_EXEEDS_MAX_VALUE");
        _rewardPercentage = rewardPercentage;
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


    function registerToken(
        address tokenAddress
    )
        external
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
        external
        onlyOwner()
        differentChain(chainId)
    {
        _registerToken(
            tokenAddress,
            chainId,
            decimals,
            symbol
        );
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
        IERC20 token = instanceService.getComponentToken(bundle.riskpoolId);

        _updateBundleState(instanceId, bundleId, address(token), bundle.state);
    }


    function updateBundleState(
        bytes32 instanceId,
        uint256 bundleId,
        address token,
        IBundle.BundleState state        
    )
        external
        onlyOwner()
        instanceOnDifferentChain(instanceId)
    {
        require(bundleId > 0, "ERROR:STK-030:BUNDLE_ID_ZERO");
        require(token != address(0), "ERROR:STK-031:TOKEN_ADDRESS_ZERO");

        _updateBundleState(instanceId, bundleId, token, state);
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
            stakeInfo.key = BundleKey(instanceId, bundleId);
            stakeInfo.createdAt = block.timestamp;
        }

        uint256 amountIncludingRewards = amount + calculateRewardsIncrement(stakeInfo);
        _increaseBundleStakes(stakeInfo, amountIncludingRewards);
        _collectStakes(staker, amount);
    }

    // TODO rename: withdraw => unstake, (align with naming below)
    // https://github.com/ethereum/EIPs/issues/900
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

        stakeInfo.balance += calculateRewardsIncrement(stakeInfo);

        if(amount == type(uint256).max) {
            amount = stakeInfo.balance;
        }

        _decreaseBundleStakes(stakeInfo, amount);
        _payoutStakes(staker, amount);
    }


    function getOneYearDuration() public pure returns(uint256 yearDuration) { 
        return ONE_YEAR_DURATION;
    }


    function getReward100PercentLevel() public pure returns(uint256 reward100PercentLevel) { 
        return REWARD_100_PERCENTAGE;
    }


    function getDipToTokenParityLevel() external pure returns(uint256 parityLevel) {
        return DIP_TO_TOKEN_PARITY_LEVEL;
    }


    function getBundleStakes(
        bytes32 instanceId,
        uint256 bundleId
    ) 
        external override
        view 
        returns(uint256 stakedDipAmount)
    {
        return stakes(instanceId, bundleId);
    }



    function isRegisteredBundle(
        bytes32 instanceId, 
        uint256 bundleId
    ) 
        external override
        view 
        returns(bool isRegistered)
    {
        return _bundleInfo[instanceId][bundleId].createdAt > 0;
    }


    function calculateRequiredStakingAmount(
        uint256 chainId,
        address targetTokenAddress,
        uint256 targetAmount
    )
        external
        view
        returns(uint256 stakingAmount)
    {
        uint256 stakingRate = getDipStakingRate(chainId, targetTokenAddress);
        uint256 stakingAmountBase = targetAmount * DIP_TO_TOKEN_PARITY_LEVEL / stakingRate;
        stakingAmount = stakingAmountBase * 10**DIP_DECIMALS / 10**_tokenInfo[targetTokenAddress][chainId].decimals;
    }


    function getBundleCapitalSupport(
        bytes32 instanceId,
        uint256 bundleId
    )
        external override
        view
        returns(uint256 captialCap)
    {
        BundleInfo memory bundle = getBundleInfo(instanceId, bundleId);
        uint256 dipStakes = stakes(instanceId, bundleId);
        return calculateTokenAmountFromStaking(dipStakes, bundle.token.chainId, bundle.token.token);
    }

    function getBundleToken(bytes32 instanceId, uint256 bundleId) 
        external override 
        view 
        returns(address token)
    {
        BundleInfo memory bundle = getBundleInfo(instanceId, bundleId);
        return bundle.token.token;
    }

    function getDip() external view returns(IERC20Metadata dip) {
        return _dip;
    }


    function getDipStakingRate(uint256 chainId, address tokenAddress)
        public
        view
        returns(uint256 stakingRate)
    {
        stakingRate = _dipStakingRate[chainId][tokenAddress];
        require(_dipStakingRate[chainId][tokenAddress] > 0, "ERROR:STK-060:STAKING_RATE_ZERO");
    }


    function calculateTokenAmountFromStaking(
        uint256 dipAmount,
        uint256 chainId, 
        address tokenAddress 
    )
        public
        view
        returns(uint256 tokenAmount)
    {
        uint256 stakingRate = getDipStakingRate(chainId, tokenAddress);
        uint256 tokenDecimals = _tokenInfo[tokenAddress][chainId].decimals;
        uint256 numerator = 1;
        uint256 denominator = 1;

        if(DIP_DECIMALS + DIP_TO_TOKEN_PARITY_LEVEL_DECIMALS >= tokenDecimals) {
            denominator = 10**(DIP_DECIMALS + DIP_TO_TOKEN_PARITY_LEVEL_DECIMALS - tokenDecimals); 
        }
        else {
            numerator = 10**(tokenDecimals - (DIP_DECIMALS + DIP_TO_TOKEN_PARITY_LEVEL_DECIMALS));
        }

        tokenAmount = (dipAmount * stakingRate * numerator) / denominator;
    }


    function getStakingWallet()
        public
        view
        returns(address instanceWallet)
    {
        return _stakingWallet;
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


    function bundles() external view returns(uint256 numberOfBundles) {
        return _bundleKeys.length;
    }

    function getBundleKey(uint256 idx) external view returns(BundleKey memory key) {
        require(idx < _bundleKeys.length, "ERROR:STK-063:BUNDLE_INDEX_TOO_LARGE");
        return _bundleKeys[idx];
    }


    function getBundleInfo(
        bytes32 instanceId,
        uint256 bundleId
    )
        public override
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
        public
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
        public
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
        public
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
        public
        view
        returns(uint256 amount)
    {
        InstanceInfo memory info = _instanceInfo[instanceId];
        require(info.createdAt > 0, "ERROR:STK-083:INSTANCE_NOT_REGISTERED");

        amount = _instanceStakedAmount[instanceId];
    }


    function stakes() public view returns(uint256 amount) {
        return _overallStakedAmount;
    }


    function calculateRewardsIncrement(StakeInfo memory stakeInfo)
        public
        view
        returns(uint256 rewardsAmount)
    {
        uint256 timeSinceLastUpdate = block.timestamp - stakeInfo.updatedAt;

        // TODO potentially reduce time depending on the time when the bundle has been closed

        rewardsAmount = calculateRewards(stakeInfo.balance, timeSinceLastUpdate);
    }


    // TODO evaluate and use floting point library
    function calculateRewards(
        uint256 amount,
        uint256 duration
    ) 
        public view
        returns(uint256 rewardAmount) 
    {
        uint256 rewardDuration = _rewardPercentage * duration / ONE_YEAR_DURATION;
        rewardAmount = amount * rewardDuration / REWARD_100_PERCENTAGE;
    }

    function tokens() external override view returns(uint256 numberOfTokens) {
        return _tokenKeys.length;
    }

    function getTokenKey(uint256 idx) external view returns(TokenKey memory tokenKey) {
        require(idx < _tokenKeys.length, "ERROR:STK-090:TOKEN_IDX_TOO_LARGE");
        return _tokenKeys[idx];
    }

    function getTokenInfo(address tokenAddress)
        external override
        view
        returns(TokenInfo memory tokenInfo)
    {
        return getTokenInfo(tokenAddress, block.chainid);
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
        address tokenAddress,
        uint256 chainId,
        uint8 decimals,
        string memory symbol
    )
        internal
        onlyOwner()
    {
        require(_tokenInfo[tokenAddress][chainId].createdAt == 0, "ERROR:STK-100:TOKEN_ALREADY_REGISTERED");
        require(tokenAddress != address(0), "ERROR:STK-101:TOKEN_ADDRESS_ZERO");
        require(chainId > 0, "ERROR:STK-102:CHAIN_ID_ZERO");
        require(decimals > 0, "ERROR:STK-103:DECIMALS_ZERO");
        require(decimals <= TOKEN_MAX_DECIMALS, "ERROR:STK-104:DECIMALS_TOO_LARGE");

        TokenInfo storage info = _tokenInfo[tokenAddress][chainId];
        info.key = TokenKey(tokenAddress, chainId);
        info.symbol = symbol;
        info.decimals = decimals;
        info.createdAt = block.timestamp;

        _tokenKeys.push(info.key);
    }


    function _updateBundleState(
        bytes32 instanceId,
        uint256 bundleId,
        address token,
        IBundle.BundleState state        
    )
        internal
    {
        require(_instanceInfo[instanceId].createdAt > 0, "ERROR:STK-110:INSTANCE_NOT_REGISTERED");

        uint256 chainId = _instanceInfo[instanceId].chainId;
        require(_tokenInfo[token][chainId].createdAt > 0, "ERROR:STK-111:TOKEN_NOT_REGISTERED");

        BundleInfo storage info = _bundleInfo[instanceId][bundleId];
        
        // handle new bundle
        if(info.createdAt == 0) {
            info.key = BundleKey(instanceId, bundleId);
            info.token = TokenKey(token, chainId);
            info.tokenSymbol = _tokenInfo[token][chainId].symbol;
            info.tokenDecimals = _tokenInfo[token][chainId].decimals;
            info.createdAt = block.timestamp;

            _bundleKeys.push(info.key);
        }

        // handling of first state change to closed state
        if(state == IBundle.BundleState.Closed && info.closedAt == 0) {
            info.closedAt = block.timestamp;
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
        _stakedAmount[stakeInfo.key.instanceId][stakeInfo.key.bundleId] += amount;
        _instanceStakedAmount[stakeInfo.key.instanceId] += amount;
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
        require(amount <= stakeInfo.balance, "ERROR:STK-120:WITHDRAWAL_AMOUNT_EXCEEDS_STAKING_BALANCE");
        _stakedAmount[stakeInfo.key.instanceId][stakeInfo.key.bundleId] -= amount;
        _instanceStakedAmount[stakeInfo.key.instanceId] -= amount;
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