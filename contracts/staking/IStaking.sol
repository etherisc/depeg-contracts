// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "./IStakingDataProvider.sol";
interface IStaking is
    IStakingDataProvider
{

    event LogStakingRewardReservesIncreased(address user, uint256 amount, uint256 newBalance);

    event LogStakingRewardRateSet(uint256 oldRewardRate, uint256 newRewardRate);
    event LogStakingStakingRateSet(address token, uint256 chainId, uint256 oldStakingRate, uint256 newStakingRate);

    event LogStakingTargetRegistered(bytes32 targetId, TargetType targetType, bytes32 instanceId, uint256 componentId, uint256 bundleId);

    event LogStakingStaked(address user, bytes32 targetId, bytes32 instanceId, uint256 componentId, uint256 bundleId, uint256 amount, uint256 newBalance);
    event LogStakingUnstaked(address user, bytes32 targetId, bytes32 instanceId, uint256 componentId, uint256 bundleId, uint256 amount, uint256 newBalance);

    event LogStakingRewardsUpdated(address user, bytes32 targetId, bytes32 instanceId, uint256 componentId, uint256 bundleId, uint256 amount, uint256 newBalance);
    event LogStakingRewardsClaimed(address user, bytes32 targetId, bytes32 instanceId, uint256 componentId, uint256 bundleId, uint256 amount, uint256 newBalance);

    event LogStakingDipBalanceChanged(uint256 stakeBalance, uint256 rewardBalance, uint256 actualBalance, uint reserves);

    function increaseRewardReserves(uint256 amount) external;

    function setRewardRate(uint256 rewardRate) external;
    function setStakingRate(address token, uint256 chainId, uint256 stakingRate) external;    

    function register(bytes32 targetId, Target memory target) external;

    function stake(bytes32 targetId, uint256 amount) external;
    function unstake(bytes32 targetId, uint256 amount) external;  
    function unstakeAndClaimRewards(bytes32 targetId) external;

    function claimRewards(bytes32 targetId) external;
}
