// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "./IStakingDataProvider.sol";
interface IStaking is
    IStakingDataProvider
{

    event LogStakingRewardRateSet(uint256 oldRewardRate, uint256 newRewardRate);
    event LogStakingStakingRateSet(address token, uint256 chainId, uint256 oldStakingRate, uint256 newStakingRate);

    event LogStakingStakedForBundle(address user, bytes32 instanceId, uint256 bundleId, uint256 amount, uint256 rewards);
    event LogStakingUnstakedFromBundle(address user, bytes32 instanceId, uint256 bundleId, uint256 amount, uint256 rewards, bool all);

    function setRewardRate(uint256 rewardRate) external;
    function setStakingRate(address token, uint256 chainId, uint256 stakingRate) external;    

    function stakeForBundle(bytes32 instanceId, uint256 bundleId, uint256 amount) external;
    function unstakeFromBundle(bytes32 instanceId, uint256 bundleId, uint256 amount) external;  
    function unstakeFromBundle(bytes32 instanceId, uint256 bundleId) external;
}
