// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "@openzeppelin/contracts/access/Ownable.sol";

import "../registry/IInstanceDataProvider.sol";
import "../registry/IBundleDataProvider.sol";
import "../registry/BundleRegistry.sol";

import "./FixedMath.sol";
import "./IStakingDataProvider.sol";
import "./IStaking.sol";

contract Staking is
    IStakingDataProvider,
    IStaking,
    Ownable
{

    uint256 public constant MAINNET_ID = 1;

    address public constant DIP_CONTRACT_ADDRESS = 0xc719d010B63E5bbF2C0551872CD5316ED26AcD83;
    uint256 public constant DIP_DECIMALS = 18;

    uint256 public constant REWARD_MAX_PERCENTAGE = 33;
    uint256 public constant YEAR_DURATION = 365 days;

    // dip to token staking rate
    mapping(address /* token */ => mapping(uint256 /* chainId */ => uint256 /* rate */ )) private _stakingRate;

    // staking state
    mapping(bytes32 /* instanceId */ => mapping(uint256 /* bundleId */ => mapping(address /* user */ => BundleStakeInfo))) private _bundleStakeInfo;
    mapping(bytes32 /* instanceId */ => mapping(uint256 /* bundleId */ => uint256 /* amount staked */)) private _bundleStakedAmount;
    mapping(bytes32 /* instanceId */ => uint256 /* amount staked */) private _instanceStakedAmount;

    BundleRegistry private _bundleRegistry;
    IERC20Metadata private _dip;
    FixedMath private _math;

    uint256 private _rewardRate;
    uint256 private _rewardRateMax;

    uint256 private _overallStakedAmount;
    address private _stakingWallet;


    modifier onlyDefinedStakingRate(address token, uint256 chainId) {
        require(this.hasDefinedStakingRate(token, chainId), "ERROR:STK-001:STAKING_RATE_NOT_DEFINED");
        _;
    }

    modifier onlyWithBundleStakeInfo(bytes32 instanceId, uint256 bundleId, address user) {
        require(this.hasBundleStakeInfo(instanceId, bundleId, user), "ERROR:STK-002:USER_WITHOUT_BUNDLE_STAKE_INFO");
        _;
    }

    constructor(
        address bundleRegistryAddress
    ) 
        Ownable()
    {
        require(bundleRegistryAddress != address(0), "ERROR:STK-005:BUNDLE_REGISTRY_ADDRESS_ZERO");

        _bundleRegistry = BundleRegistry(bundleRegistryAddress);

        _dip = IERC20Metadata(DIP_CONTRACT_ADDRESS);
        _math = new FixedMath();
        _rewardRateMax = _math.itof(REWARD_MAX_PERCENTAGE, -2);

        _stakingWallet = address(this);
    }


    function getBundleRegistry() external override view returns(BundleRegistry bundleRegistry) {
        return _bundleRegistry;
    }


    function isBundleStakingSupported(bytes32 instanceId, uint256 bundleId) 
        external override
        view 
        returns(bool isSupported)
    {
        IBundleDataProvider.BundleInfo memory info = _bundleRegistry.getBundleInfo(instanceId, bundleId);
        isSupported = false;

        if(block.timestamp < info.expiryAt) {
            if(info.closedAt == 0) {
                isSupported = true;
            } else if(block.timestamp < info.closedAt) {
                isSupported = true;
            }
        }
    }


    function isBundleUnstakingSupported(bytes32 instanceId, uint256 bundleId) 
        external override
        view 
        returns(bool isSupported)
    {
        IBundleDataProvider.BundleInfo memory info = _bundleRegistry.getBundleInfo(instanceId, bundleId);
        isSupported = false;

        if(block.timestamp >= info.expiryAt) {
            isSupported = true;
        } else if(info.closedAt > 0 && block.timestamp >= info.closedAt) {
            isSupported = true;
        }
    }

    function setDipContract(address dipTokenAddress) 
        external
        onlyOwner()
    {
        require(block.chainid != MAINNET_ID, "ERROR:STK-010:DIP_ADDRESS_CHANGE_NOT_ALLOWED_ON_MAINNET");
        require(dipTokenAddress != address(0), "ERROR:STK-011:DIP_CONTRACT_ADDRESS_ZERO");

        _dip = IERC20Metadata(dipTokenAddress);
    }


    // dip staking rate: value of 1 dip in amount of provided token (taking into account dip.decimals and token.decimals)
    function setStakingRate(
        address token, 
        uint256 chainId, 
        uint256 newStakingRate
    ) 
        external override
        onlyOwner()
    {
        require(_bundleRegistry.isRegisteredToken(token, chainId), "ERROR:STK-030:TOKEN_NOT_REGISTERED");
        require(newStakingRate > 0, "ERROR:STK-031:STAKING_RATE_ZERO");

        uint256 oldStakingRate = _stakingRate[token][chainId];
        _stakingRate[token][chainId] = newStakingRate;

        emit LogStakingStakingRateSet(token, chainId, oldStakingRate, newStakingRate);
    }

    function stakeForBundle(
        bytes32 instanceId, 
        uint256 bundleId, 
        uint256 amount
    )
        external override
    {
        require(_bundleRegistry.isRegisteredBundle(instanceId, bundleId), "ERROR:STK-040:BUNDLE_NOT_REGISTERED");
        require(this.isBundleStakingSupported(instanceId, bundleId), "ERROR:STK-041:STAKING_TOO_LATE");
        require(amount > 0, "ERROR:STK-042:STAKING_AMOUNT_ZERO");

        address user = msg.sender;
        BundleStakeInfo storage stakeInfo = _bundleStakeInfo[instanceId][bundleId][user];

        // handling for new stakes
        if(stakeInfo.createdAt == 0) {
            stakeInfo.user = user;
            stakeInfo.key = IBundleDataProvider.BundleKey(instanceId, bundleId);
            stakeInfo.createdAt = block.timestamp;
        }

        uint256 rewards = calculateRewardsIncrement(stakeInfo);
        _increaseBundleStakes(stakeInfo, amount + rewards);
        _collectStakes(user, amount);

        emit LogStakingStakedForBundle(
            user,
            instanceId,
            bundleId,
            amount,
            rewards
        );
    }

    function unstakeFromBundle(
        bytes32 instanceId, 
        uint256 bundleId
    )
        external override
    {
        unstakeFromBundle(instanceId, bundleId, type(uint256).max);
    }

    function unstakeFromBundle(
        bytes32 instanceId, 
        uint256 bundleId, 
        uint256 amount
    ) 
        public override
        onlyWithBundleStakeInfo(instanceId, bundleId, msg.sender)        
    {
        require(this.isBundleUnstakingSupported(instanceId, bundleId), "ERROR:STK-050:UNSTAKING_TOO_EARLY");
        require(amount > 0, "ERROR:STK-051:UNSTAKING_AMOUNT_ZERO");

        address user = msg.sender;
        BundleStakeInfo storage stakeInfo = _bundleStakeInfo[instanceId][bundleId][user];

        uint256 rewards = calculateRewardsIncrement(stakeInfo);
        if(rewards > 0) {
            _increaseBundleStakes(stakeInfo, rewards);
        }

        bool unstakeAll = (amount == type(uint256).max);
        if(unstakeAll) {
            amount = stakeInfo.balance;
        }

        _decreaseBundleStakes(stakeInfo, amount);
        _payoutStakes(user, amount);

        emit LogStakingUnstakedFromBundle(
            user,
            instanceId,
            bundleId,
            amount,
            rewards,
            unstakeAll
        );
    }


    function setRewardRate(
        uint256 newRewardRate
    )
        external override
        onlyOwner
    {
        require(newRewardRate <= _rewardRateMax, "ERROR:STK-060:REWARD_EXCEEDS_MAX_VALUE");
        uint256 oldRewardRate = _rewardRate;

        _rewardRate = newRewardRate;

        emit LogStakingRewardRateSet(oldRewardRate, newRewardRate);
    }


    function hasBundleStakeInfo(
        bytes32 instanceId,
        uint256 bundleId,
        address user
    )
        external override
        view
        returns(bool hasInfo)
    {
        BundleStakeInfo memory stakeInfo = _bundleStakeInfo[instanceId][bundleId][user];
        return stakeInfo.createdAt > 0;
    }


    function getBundleStakeInfo(
        bytes32 instanceId, 
        uint256 bundleId,
        address user
    )
        external override
        view
        onlyWithBundleStakeInfo(instanceId, bundleId, user)
        returns(BundleStakeInfo memory info)
    {
        return _bundleStakeInfo[instanceId][bundleId][user];
    }


    function getBundleStakes(
        bytes32 instanceId, 
        uint256 bundleId,
        address user
    )
        external override 
        view 
        returns(uint256 dipAmount)
    {
        return _bundleStakeInfo[instanceId][bundleId][user].balance;
    }


    function getBundleStakes(
        bytes32 instanceId, 
        uint256 bundleId
    )
        external override 
        view 
        returns(uint256 dipAmount)
    {
        require(_bundleRegistry.isRegisteredBundle(instanceId, bundleId), "ERROR:STK-070:BUNDLE_NOT_REGISTERED");
        return _bundleStakedAmount[instanceId][bundleId];
    }


    function getTotalStakes(bytes32 instanceId)
        external override 
        view
        returns(uint256 dipAmount)
    {
        require(_bundleRegistry.isRegisteredInstance(instanceId), "ERROR:STK-080:INSTANCE_NOT_REGISTERED");
        return _instanceStakedAmount[instanceId];
    }


    function getTotalStakes() external override view returns(uint256 dipAmount) {
        return _overallStakedAmount;
    }


    function getBundleCapitalSupport(
        bytes32 instanceId, 
        uint256 bundleId
    )
        external override
        view
        returns(uint256 capitalAmount)
    {
        // if bundle is not registered it is not possible that any dips have been staked
        // as a result capital support is 0 too
        if(!_bundleRegistry.isRegisteredBundle(instanceId, bundleId)) {
            return 0;
        }

        IInstanceDataProvider.TokenInfo memory info = _bundleRegistry.getBundleTokenInfo(instanceId, bundleId); 
        uint256 stakedDipAmount = this.getBundleStakes(instanceId, bundleId);

        return this.calculateCapitalSupport(info.key.token, info.key.chainId, stakedDipAmount);
    }

    function getStakingRate(
        address token, 
        uint256 chainId
    )
        external override
        view
        returns(uint256 rate)
    {
        require(_bundleRegistry.isRegisteredToken(token, chainId), "ERROR:STK-100:TOKEN_NOT_REGISTERED");
        return _stakingRate[token][chainId];
    }

    function hasDefinedStakingRate(
        address token, 
        uint256 chainId
    )
        external override 
        view 
        returns(bool hasRate)
    {
        return _stakingRate[token][chainId] > 0;
    }


    function calculateRequiredStaking(
        address token, 
        uint256 chainId, 
        uint256 targetAmount
    )
        external override
        view 
        onlyDefinedStakingRate(token, chainId)        
        returns(uint dipAmount)
    {
        IInstanceDataProvider.TokenInfo memory info = _bundleRegistry.getTokenInfo(token, chainId);
        uint256 rate = _stakingRate[token][chainId];
        return _math.div(targetAmount, rate) * 10 ** (DIP_DECIMALS - info.decimals);
    }

    function calculateCapitalSupport(
        address token, 
        uint256 chainId, 
        uint256 dipAmount
    )
        external override
        view 
        onlyDefinedStakingRate(token, chainId)        
        returns(uint tokenAmount)
    {
        IInstanceDataProvider.TokenInfo memory info = _bundleRegistry.getTokenInfo(token, chainId);
        uint256 rate = _stakingRate[token][chainId];
        return (_math.mul(dipAmount, rate) * 10 ** info.decimals) / 10 ** DIP_DECIMALS;
    }

    function getRewardRate() 
        external override
        view
        returns(uint256 rate)
    {
        return _rewardRate;
    }


    function calculateRewardsIncrement(BundleStakeInfo memory stakeInfo)
        public override
        view
        returns(uint256 rewardsAmount)
    {
        uint256 timeSinceLastUpdate = block.timestamp - stakeInfo.updatedAt;

        // TODO potentially reduce time depending on the time when the bundle has been closed

        rewardsAmount = calculateRewards(stakeInfo.balance, timeSinceLastUpdate);
    }


    function calculateRewards(
        uint256 amount,
        uint256 duration
    ) 
        public override
        view
        returns(uint256 rewardAmount) 
    {
        uint256 yearFraction = _math.itof(duration) / YEAR_DURATION;
        uint256 rewardDuration = _math.mul(_rewardRate, yearFraction);
        rewardAmount = _math.ftoi(amount * rewardDuration);
    }

    function getStakingWallet()
        public override
        view
        returns(address stakingWallet)
    {
        return _stakingWallet;
    }


    function oneYear() external override pure returns(uint256 yearInSeconds) {
        return YEAR_DURATION;
    }

    function toRate(uint256 value, int8 exp) external override view returns(uint256 rate) {
        return _math.itof(value, exp);
    }

    function fromRate(uint256 rate) external override view returns(uint256 value, uint256 divisor) {
        return (
            rate,
            _math.getMultiplier()
        );
    }

    function _increaseBundleStakes(
        BundleStakeInfo storage stakeInfo,
        uint256 amount
    )
        internal
    {
        _bundleStakedAmount[stakeInfo.key.instanceId][stakeInfo.key.bundleId] += amount;
        _instanceStakedAmount[stakeInfo.key.instanceId] += amount;
        _overallStakedAmount += amount;

        stakeInfo.balance += amount;
        stakeInfo.updatedAt = block.timestamp;
    }


    function _decreaseBundleStakes(
        BundleStakeInfo storage stakeInfo,
        uint256 amount
    )
        internal
    {
        require(amount <= stakeInfo.balance, "ERROR:STK-120:UNSTAKING_AMOUNT_EXCEEDS_STAKING_BALANCE");
        _bundleStakedAmount[stakeInfo.key.instanceId][stakeInfo.key.bundleId] -= amount;
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
}