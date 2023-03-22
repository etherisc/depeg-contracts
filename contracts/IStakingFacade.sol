// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.2;

import "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";

import "./IChainRegistryFacade.sol";

interface IStakingFacade {

    function owner() external view returns(address);
    function getRegistry() external view returns(IChainRegistryFacade);

    function getStakingWallet() external view returns(address stakingWallet);
    function getDip() external view returns(IERC20Metadata);

    function rewardRate() external view returns(uint256 rate);
    function rewardBalance() external view returns(uint256 dipAmount);
    function rewardReserves() external view returns(uint256 dipAmount);

    function setStakingRate(bytes5 chain, address token, uint256 rate) external;    
    function stakingRate(bytes5 chain, address token) external view returns(uint256 rate);

    function capitalSupport(uint256 targetNftId) external view returns(uint256 capitalAmount);
    function implementsIStaking() external pure returns(bool);

    function toChain(uint256 chainId) external pure returns(bytes5);

    function toRate(uint256 value, int8 exp) external pure returns(uint256 rate);
    function rateDecimals() external pure returns(uint256 decimals);

}