// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "../registry/IBundleDataProvider.sol";
import "../registry/BundleRegistry.sol";
interface IStakingDataProvider {

    // TODO add NFT for staking

    enum TargetType {
        Undefined,
        Protocol,
        Instance,
        Component,
        Bundle,
        TypeA,
        TypeB,
        TypeC,
        TypeD,
        TypeE
    }

    struct Target {
        TargetType targetType;
        bytes32 instanceId;
        uint256 componentId;
        uint256 bundleId;
        bytes data;
        address token;
        uint256 chainId;
    }

    struct StakeInfo {
        address user;
        bytes32 targetId;
        uint256 stakeBalance;
        uint256 rewardBalance;
        uint256 createdAt;
        uint256 updatedAt;
    }

    function getStakingWallet() external view returns(address stakingWallet);

    function getRewardRate() external view returns(uint256 rate);
    function getRewardBalance() external view returns(uint256 rewardReserves);
    function getRewardReserves() external view returns(uint256 rewardReserves);

    function calculateRewards(uint256 amount, uint256 duration) external view returns(uint256 rewardAmount);
    function calculateRewardsIncrement(StakeInfo memory info) external view returns(uint256 incrementAmount);
    function oneYear() external pure returns(uint256 yearInSeconds);

    function hasDefinedStakingRate(address token, uint256 chainId) external view returns(bool hasRate);
    function getStakingRate(address token, uint256 chainId) external view returns(uint256 rate);    
    function calculateRequiredStaking(address token, uint256 chainId, uint256 tokenAmount) external view returns(uint dipAmount);
    function calculateCapitalSupport(address token, uint256 chainId, uint256 dipAmount) external view returns(uint tokenAmount);

    // check/get staking targets
    function targets() external view returns(uint256 numberOfTargets);
    function getTargetId(uint256 idx) external view returns(bytes32 targetId);

    function isTarget(bytes32 targetId) external view returns(bool isATarget);
    function isTargetRegistered(Target memory target) external view returns(bool isRegistered);
    function getTarget(bytes32 targetId) external view returns(Target memory target);

    function toInstanceTargetId(bytes32 instanceId) external pure returns(bytes32 targetId);
    function toComponentTargetId(bytes32 instanceId, uint256 componentId) external pure returns(bytes32 targetId);
    function toBundleTargetId(bytes32 instanceId, uint256 componentId, uint256 bundleId) external pure returns(bytes32 targetId);

    function toTarget(
        TargetType targetType,
        bytes32 instanceId,
        uint256 componentId,
        uint256 bundleId,
        bytes memory data
    )
        external
        view
        returns(
            bytes32 targetId,
            Target memory target);

    // check/get staking info
    function hasInfo(bytes32 targetId, address user) external view returns(bool hasInfos);
    function getInfo(bytes32 targetId, address user) external view returns(StakeInfo memory info);

    function isStakingSupported(bytes32 targetId) external view returns(bool isSupported);
    function isUnstakingSupported(bytes32 targetId) external view returns(bool isSupported);

    // get staked dips
    function stakes(bytes32 targetId, address user) external view returns(uint256 dipAmount);
    function stakes(bytes32 targetId) external view returns(uint256 dipAmount);
    function capitalSupport(bytes32 targetId) external view returns(uint256 capitalAmount);

    function getStakeBalance() external view returns(uint256 stakeBalance);

    // getters for bundle staking
    function getBundleRegistry() external view returns(BundleRegistry bundleRegistry);

    function toRate(uint256 value, int8 exp) external view returns(uint256 rate);
    function fromRate(uint256 rate) external view returns(uint256 value, uint256 divisor); 
}
