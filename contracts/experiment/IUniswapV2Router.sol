// SPDX-License-Identifier: MIT
pragma solidity ^0.8.2;

// Interface for Uniswap V2 Router
interface IUniswapV2Router {
    function swapExactETHForTokens(
        uint256 amountOutMin,
        address[] calldata path,
        address to,
        uint256 deadline
    ) external payable returns (uint256[] memory amounts);
    
    function WETH() external pure returns (address);
}