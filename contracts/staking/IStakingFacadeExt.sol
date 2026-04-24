// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

/**
 * @dev this facade is intended for user contracts with limited 
 * interactions with the actual contract and that need to work 
 * with older solidity versions that do not support user defined 
 * types.
 * 
 * usage: 
 * (1) copy this interface into your repository
 * (2) adapt the pragma to your needsd
 * (3) use it in your contracts, ie. cast actual contract 
 * address to this interface, then  usd the resulting facade 
 * to interact with the actual contract
 */

import {IStakingFacade} from "./IStakingFacade.sol";

interface IStakingFacadeExt is IStakingFacade {

    struct StakeInfo {
        uint96 id;
        uint96 target;
        uint256 stakeBalance;
        uint256 rewardBalance;
        uint40 createdAt;
        uint40 updatedAt;
        uint48 version;
        uint40 lockedUntil; // introduced with V03
    }

    function setTargetRewardRate(uint96 targetNftId, uint256 newRewardRate) external;
    function getTargetRewardRate(uint96 targetNftId) external view returns(uint256 rewardRate);

    function getInfo(uint96 stakeNftId) external view returns(StakeInfo memory info);
    function calculateRewardsIncrement(StakeInfo memory stakeInfo) external view returns(uint256 rewardsAmount);
}