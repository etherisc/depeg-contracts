// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "../registry/IBundleDataProvider.sol";
import "../registry/BundleRegistry.sol";
interface IStakingDataProvider {

    // TODO NFT for staking
    // unify staking for instances, compnents and bundles
    // key needs to be able to match an instance, a component or a bundle
    struct BundleStakeInfo {
        address user;
        IBundleDataProvider.BundleKey key;
        uint256 balance;
        uint256 createdAt;
        uint256 updatedAt;
    }

    function getBundleRegistry() external view returns(BundleRegistry bundleRegistry);
    function isBundleStakingSupported(bytes32 instanceId, uint256 bundleId) external view returns(bool isSupported);
    function isBundleUnstakingSupported(bytes32 instanceId, uint256 bundleId) external view returns(bool isSupported);

    function getBundleStakeInfo(bytes32 instanceId, uint256 bundleId, address user) external view returns(BundleStakeInfo memory info);
    function hasBundleStakeInfo(bytes32 instanceId, uint256 bundleId, address user) external view returns(bool hasInfo);

    function getBundleStakes(bytes32 instanceId, uint256 bundleId, address user) external view returns(uint256 dipAmount);
    function getBundleStakes(bytes32 instanceId, uint256 bundleId) external view returns(uint256 dipAmount);

    function getTotalStakes(bytes32 instanceId) external view returns(uint256 dipAmount);
    function getTotalStakes() external view returns(uint256 dipAmount);

    function getBundleCapitalSupport(bytes32 instanceId, uint256 bundleId) external view returns(uint256 capitalAmount);

    function getStakingRate(address token, uint256 chainId) external view returns(uint256 rate);    
    function hasDefinedStakingRate(address token, uint256 chainId) external view returns(bool hasRate);
    function calculateRequiredStaking(address token, uint256 chainId, uint256 tokenAmount) external view returns(uint dipAmount);
    function calculateCapitalSupport(address token, uint256 chainId, uint256 dipAmount) external view returns(uint tokenAmount);

    function getRewardRate() external view returns(uint256 rate);
    function calculateRewards(uint256 amount, uint256 duration) external view returns(uint256 rewardAmount);
    function calculateRewardsIncrement(BundleStakeInfo memory stakeInfo) external view returns(uint256 incrementAmount);

    function getStakingWallet() external view returns(address stakingWallet);
    function oneYear() external pure returns(uint256 yearInSeconds);

    function toRate(uint256 value, int8 exp) external view returns(uint256 rate);
    function fromRate(uint256 rate) external view returns(uint256 value, uint256 divisor); 
}
