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

    // staking wallet (ccount holding dips)
    uint256 private _stakeBalance;
    address private _stakingWallet;

    // staking rewards
    uint256 private _rewardReserves;
    uint256 private _rewardBalance;
    uint256 private _rewardRate;
    uint256 private _rewardRateMax;

    // dip to token staking rate
    mapping(address /* token */ => mapping(uint256 /* chainId */ => uint256 /* rate */ )) private _stakingRate;

    // target
    mapping(bytes32 /* targetId */ => Target) private _target;
    bytes32 [] private _targetIds;

    // staking
    mapping(bytes32 /* targetId */ => mapping(address /* user */ => StakeInfo)) private _stakeInfo;
    mapping(bytes32 /* targetId */ => uint256 /* amount staked */) private _targetStakeBalance;

    // external contracts
    BundleRegistry private _registry;
    IERC20Metadata private _dip;
    FixedMath private _math;


    modifier onlyDefinedStakingRate(address token, uint256 chainId) {
        require(this.hasDefinedStakingRate(token, chainId), "ERROR:STK-001:STAKING_RATE_NOT_DEFINED");
        _;
    }

    modifier onlyInfo(bytes32 targetId, address user) {
        require(this.hasInfo(targetId, user), "ERROR:STK-002:USER_WITHOUT_STAKE_INFO");
        _;
    }

    modifier onlyTarget(bytes32 targetId) {
        require(this.isTarget(targetId), "ERROR:STK-003:TARGET_NOT_REGISTERED");
        _;
    }

    constructor(
        address bundleRegistryAddress
    ) 
        Ownable()
    {
        require(bundleRegistryAddress != address(0), "ERROR:STK-005:BUNDLE_REGISTRY_ADDRESS_ZERO");

        _registry = BundleRegistry(bundleRegistryAddress);
        _dip = IERC20Metadata(DIP_CONTRACT_ADDRESS);
        _math = new FixedMath();

        _stakeBalance = 0;
        _stakingWallet = address(this);

        _rewardReserves = 0;
        _rewardBalance = 0;
        _rewardRate = 0;
        _rewardRateMax = _math.itof(REWARD_MAX_PERCENTAGE, -2);
    }


    function increaseRewardReserves(uint256 amount) 
        external override
    {
        address user = msg.sender;
        _rewardReserves += amount;

        _collectDip(user, amount);

        emit LogStakingRewardReservesIncreased(
            user,
            amount,
            _rewardReserves);
    }


    function getBundleRegistry() external override view returns(BundleRegistry bundleRegistry) {
        return _registry;
    }


    function targets() external override view returns(uint256 numberOfTargets) {
        return _targetIds.length;
    }


    function getTargetId(uint256 idx) external override view returns(bytes32 targetId) {
        require(idx < _targetIds.length, "ERROR:STK-010:TARGET_INDEX_TOO_LARGE");
        return _targetIds[idx];
    }


    function isTarget(bytes32 targetId) external override view returns(bool isATarget) {
        return _target[targetId].targetType != TargetType.Undefined;
    }

    function isTargetRegistered(Target memory target) 
        external override 
        view 
        returns(bool isRegistered)
    {
        if(target.targetType == TargetType.Instance) {
            return _registry.isRegisteredInstance(target.instanceId);
        } else if(target.targetType == TargetType.Component) {
            return _registry.isRegisteredComponent(target.instanceId, target.componentId);
        } else if(target.targetType == TargetType.Bundle) {
            return _registry.isRegisteredBundle(target.instanceId, target.bundleId);
        } else {
            return false;
        }
    }


    function getTarget(bytes32 targetId) 
        external override
        view 
        onlyTarget(targetId)
        returns(Target memory target)
    {
        return _target[targetId];
    }


    function register(
        bytes32 targetId, 
        Target memory target
    ) 
        external override
    {
        require(!this.isTarget(targetId), "ERROR:STK-010:TARGET_ALREADY_REGISTERED");
        require(targetId == _toTargetId(target), "ERROR:STK-011:TARGET_DATA_INCONSISTENT");

        // once a target is available in registry anybody may register it 
        // as a staking target
        require(this.isTargetRegistered(target), "ERROR:STK-012:TARGET_NOT_IN_REGISTRY");

        _target[targetId] = target;
        _targetIds.push(targetId);

        emit LogStakingTargetRegistered(
            targetId, 
            target.targetType, 
            target.instanceId, 
            target.componentId, 
            target.bundleId);
    }


    function toTarget(
        TargetType targetType,
        bytes32 instanceId,
        uint256 componentId,
        uint256 bundleId,
        bytes memory data
    )
        external override
        view
        returns(
            bytes32 targetId,
            Target memory target
        )
    {
        // default token data
        address token = address(0);
        uint256 chainId = 0;

        // targetId attributes
        if(targetType == TargetType.Instance) {
            componentId = 0;
            bundleId = 0;
            data = "";
        } else if(targetType == TargetType.Component) {
            bundleId = 0;
            data = "";
        } else if(targetType == TargetType.Bundle) {
            // if available use bundle riskpool id instead of provided component id
            if(_registry.isRegisteredBundle(instanceId, bundleId)) {
                IBundleDataProvider.BundleInfo memory info = _registry.getBundleInfo(instanceId, bundleId);
                componentId = info.riskpoolId;
            }

            data = "";
        } else {
            revert("ERROR:STK-019:TARGET_TYPE_UNSUPPORTED");
        }

        // set target token where available
        if(_registry.isRegisteredComponent(instanceId, componentId)) {
            IComponentDataProvider.ComponentInfo memory info = _registry.getComponentInfo(instanceId, componentId);
            token = info.token;
            chainId = info.chainId;
        }

        return (
            _toTargetId(targetType, instanceId, componentId, bundleId, data),
            Target(
                targetType,
                instanceId,
                componentId,
                bundleId,
                data,
                token,
                chainId
            ));
    }


    function toInstanceTargetId(bytes32 instanceId)
        external override
        pure 
        returns(bytes32 targetId)
    {
        return _toTargetId(
            TargetType.Instance, 
            instanceId, 
            0, 
            0, 
            "");
    }


    function toComponentTargetId(
        bytes32 instanceId, 
        uint256 componentId
    ) 
        external override 
        pure 
        returns(bytes32 targetId)
    {
        return _toTargetId(
            TargetType.Component, 
            instanceId, 
            componentId, 
            0, 
            "");
    }

    function toBundleTargetId(
        bytes32 instanceId, 
        uint256 componentId,
        uint256 bundleId
    )
        external override 
        pure 
        returns(bytes32 targetId)
    {
        return _toTargetId(
            TargetType.Bundle, 
            instanceId, 
            componentId, 
            bundleId, 
            "");
    }

    function isStakingSupported(bytes32 targetId) 
        external override
        view 
        onlyTarget(targetId)
        returns(bool isSupported)
    {
        Target memory target = this.getTarget(targetId);

        // currently only bundle staking is supported
        if(target.targetType != TargetType.Bundle) {
            return false;
        }

        IBundleDataProvider.BundleInfo memory info = _registry.getBundleInfo(target.instanceId, target.bundleId);
        isSupported = false;

        if(block.timestamp < info.expiryAt) {
            if(info.closedAt == 0) {
                isSupported = true;
            } else if(block.timestamp < info.closedAt) {
                isSupported = true;
            }
        }
    }


    function isUnstakingSupported(bytes32 targetId) 
        external override
        view 
        onlyTarget(targetId)
        returns(bool isSupported)
    {
        Target memory target = this.getTarget(targetId);

        // currently only bundle (un)staking is supported
        if(target.targetType != TargetType.Bundle) {
            return false;
        }

        IBundleDataProvider.BundleInfo memory info = _registry.getBundleInfo(target.instanceId, target.bundleId);
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


    // dip staking rate: value of 1 dip in amount of provided token 
    // (taking into account dip.decimals and token.decimals)
    function setStakingRate(
        address token, 
        uint256 chainId, 
        uint256 newStakingRate
    ) 
        external override
        onlyOwner()
    {
        require(_registry.isRegisteredToken(token, chainId), "ERROR:STK-030:TOKEN_NOT_REGISTERED");
        require(newStakingRate > 0, "ERROR:STK-031:STAKING_RATE_ZERO");

        uint256 oldStakingRate = _stakingRate[token][chainId];
        _stakingRate[token][chainId] = newStakingRate;

        emit LogStakingStakingRateSet(token, chainId, oldStakingRate, newStakingRate);
    }

    function stake(
        bytes32 targetId, 
        uint256 amount
    )
        external override
        onlyTarget(targetId)
    {
        require(this.isStakingSupported(targetId), "ERROR:STK-041:STAKING_NOT_SUPPORTED");
        require(amount > 0, "ERROR:STK-042:STAKING_AMOUNT_ZERO");

        address user = msg.sender;
        Target memory target = _target[targetId];
        StakeInfo storage info = _stakeInfo[targetId][user];

        // handling for new stakes
        if(info.createdAt == 0) {
            info.user = user;
            info.targetId = targetId;
            info.stakeBalance = 0;
            info.rewardBalance = 0;
            info.createdAt = block.timestamp;
        }

        _updateRewards(target, info);
        _increaseStakes(info, amount);
        _collectDip(user, amount);

        emit LogStakingStaked(
            info.user,
            info.targetId,
            target.instanceId,
            target.componentId,
            target.bundleId,
            amount,
            _stakeBalance
        );
    }


    function unstakeAndClaimRewards(bytes32 targetId) external override {
        _unstake(targetId, msg.sender, type(uint256).max);
    }


    function unstake(bytes32 targetId, uint256 amount) external override {
        _unstake(targetId, msg.sender, amount);
    }


    function _unstake(
        bytes32 targetId,
        address user, 
        uint256 amount
    ) 
        internal
        onlyInfo(targetId, user)        
    {
        require(this.isUnstakingSupported(targetId), "ERROR:STK-050:UNSTAKE_NOT_SUPPORTED");
        require(amount > 0, "ERROR:STK-051:UNSTAKE_AMOUNT_ZERO");

        Target memory target = _target[targetId];
        StakeInfo storage info = _stakeInfo[targetId][user];

        _updateRewards(target, info);

        bool unstakeAll = (amount == type(uint256).max);
        if(unstakeAll) {
            amount = info.stakeBalance;
        }

        _decreaseStakes(info, amount);
        _payoutDip(user, amount);

        emit LogStakingUnstaked(
            user,
            targetId,
            target.instanceId,
            target.componentId,
            target.bundleId,
            amount,
            info.stakeBalance
        );

        if(unstakeAll) {
            _claimRewards(target, info);
        }
    }


    function claimRewards(bytes32 targetId)
        external override
        onlyInfo(targetId, msg.sender)
    {
        Target memory target = _target[targetId];
        StakeInfo storage info = _stakeInfo[targetId][msg.sender];
        _claimRewards(target, info);
    }


    function stakes(bytes32 targetId, address user)
        external override 
        view 
        returns(uint256 dipAmount)
    {
        return _stakeInfo[targetId][user].stakeBalance;
    }


    function stakes(bytes32 targetId)
        external override 
        view 
        returns(uint256 dipAmount)
    {
        return _targetStakeBalance[targetId];
    }


    function _claimRewards(
        Target memory target, 
        StakeInfo storage info
    )
        internal
    {
        uint256 amount = info.rewardBalance;

        // TODO remove require, only for testing here...
        require(amount <= _rewardReserves, 'ERR:REWARD_RESERVES_INSUFFICIENT');

        // ensure reward payout is within avaliable reward reserves
        if(amount > _rewardReserves) {
            amount = _rewardReserves;
        }

        _rewardReserves -= amount;

        _decreaseRewards(info, amount);
        _payoutDip(info.user, amount);

        emit LogStakingRewardsClaimed(
            info.user,
            info.targetId,
            target.instanceId,
            target.componentId,
            target.bundleId,
            amount,
            info.rewardBalance
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


    function hasInfo(
        bytes32 targetId,
        address user
    )
        external override
        view
        returns(bool hasStakeInfo)
    {
        return _stakeInfo[targetId][user].createdAt > 0;
    }


    function getInfo(
        bytes32 targetId,
        address user
    )
        external override
        view
        onlyInfo(targetId, user)
        returns(StakeInfo memory info)
    {
        return _stakeInfo[targetId][user];
    }


    function capitalSupport(bytes32 targetId)
        external override
        view
        returns(uint256 capitalAmount)
    {
        // if target is not registered it is not possible that any dips have been staked
        // as a result capital support is 0 too
        if(!this.isTarget(targetId)) {
            return 0;
        }

        // get target token data
        Target memory target = this.getTarget(targetId);

        // without a defined token staking does not lead to capital support
        if(target.token == address(0)) {
            return 0;
        }

        return this.calculateCapitalSupport(
            target.token, 
            target.chainId, 
            _targetStakeBalance[targetId]);
    }


    function getStakingRate(
        address token, 
        uint256 chainId
    )
        external override
        view
        returns(uint256 rate)
    {
        require(_registry.isRegisteredToken(token, chainId), "ERROR:STK-100:TOKEN_NOT_REGISTERED");
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
        IInstanceDataProvider.TokenInfo memory info = _registry.getTokenInfo(token, chainId);
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
        IInstanceDataProvider.TokenInfo memory info = _registry.getTokenInfo(token, chainId);
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


    function calculateRewardsIncrement(StakeInfo memory stakeInfo)
        public override
        view
        returns(uint256 rewardsAmount)
    {
        uint256 timeSinceLastUpdate = block.timestamp - stakeInfo.updatedAt;

        // TODO potentially reduce time depending on the time when the bundle has been closed

        rewardsAmount = calculateRewards(stakeInfo.stakeBalance, timeSinceLastUpdate);
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

    function getRewardReserves() external override view returns(uint256 rewardReserves) {
        return _rewardReserves;
    }

    function getRewardBalance() external override view returns(uint256 rewardReserves) {
        return _rewardBalance;
    }

    function getStakeBalance() external override view returns(uint256 stakesBalane) {
        return _stakeBalance;
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


    function _toTargetId(Target memory target)
        internal 
        pure 
        returns(bytes32 targetId)
    {
        return _toTargetId(
            target.targetType,
            target.instanceId,
            target.componentId,
            target.bundleId,
            target.data);
    }


    function _toTargetId(
        TargetType targetType,
        bytes32 instanceId,
        uint256 componentId,
        uint256 bundleId,
        bytes memory data
    )
        internal
        pure
        returns(bytes32 targetId)
    {
        targetId = keccak256(
            abi.encodePacked(
                targetType,
                instanceId, 
                componentId,
                bundleId,
                data
            ));
    }


    function _updateRewards(Target memory target, StakeInfo storage info)
        internal
    {
        uint256 amount = calculateRewardsIncrement(info);
        _rewardBalance += amount;

        info.rewardBalance += amount;
        info.updatedAt = block.timestamp;

        emit LogStakingRewardsUpdated(
            info.user,
            info.targetId,
            target.instanceId,
            target.componentId,
            target.bundleId,
            amount,
            info.rewardBalance
        );
    }


    function _decreaseRewards(
        StakeInfo storage info,
        uint256 amount
    )
        internal
    {
        _rewardBalance -= amount;

        info.rewardBalance -= amount;
        info.updatedAt = block.timestamp;
    }


    function _increaseStakes(
        StakeInfo storage info,
        uint256 amount
    )
        internal
    {
        _targetStakeBalance[info.targetId] += amount;
        _stakeBalance += amount;

        info.stakeBalance += amount;
        info.updatedAt = block.timestamp;
    }


    function _decreaseStakes(
        StakeInfo storage info,
        uint256 amount
    )
        internal
    {
        require(amount <= info.stakeBalance, "ERROR:STK-120:UNSTAKING_AMOUNT_EXCEEDS_STAKING_BALANCE");

        _targetStakeBalance[info.targetId] -= amount;
        _stakeBalance -= amount;

        info.stakeBalance -= amount;
        info.updatedAt = block.timestamp;
    }


    function _collectDip(address user, uint256 amount)
        internal
    {
        _dip.transferFrom(user, _stakingWallet, amount);

        uint256 actualBalance = _dip.balanceOf(_stakingWallet);
        emit LogStakingDipBalanceChanged(
            _stakeBalance,
            _rewardBalance, 
            actualBalance, 
            actualBalance - _stakeBalance - _rewardBalance);
    }


    function _payoutDip(address user, uint256 amount)
        internal
    {
        if(_stakingWallet != address(this)) {
            _dip.transferFrom(_stakingWallet, user, amount);
        }
        else {
            _dip.transfer(user, amount);
        }

        uint256 actualBalance = _dip.balanceOf(_stakingWallet);
        emit LogStakingDipBalanceChanged(
            _stakeBalance,
            _rewardBalance, 
            actualBalance, 
            actualBalance - _stakeBalance - _rewardBalance);
    }
}