// SPDX-License-Identifier: MIT
pragma solidity ^0.8.2;

import {IUniswapV2Router} from "./IUniswapV2Router.sol";

contract UsdtBuyer {

    address public constant UNISWAP_V2_ROUTER = 0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D;
    address public constant USDT = 0xdAC17F958D2ee523a2206206994597C13D831ec7;
    address private _owner;

    modifier onlyOwner() {
        require(msg.sender == _owner, "not owner");
        _;
    }

    constructor() {
        _owner = msg.sender;
    }

    function buy(uint256 amountIn, uint256 amountOutMin)
        external
        onlyOwner()
    {
        address[] memory path = new address[](2);
        path[0] = IUniswapV2Router(UNISWAP_V2_ROUTER).WETH();
        path[1] = USDT;

        address to = msg.sender;
        uint256 deadline = block.timestamp + 10 minutes;
        IUniswapV2Router(UNISWAP_V2_ROUTER).swapExactETHForTokens{value: amountIn}(
            amountOutMin, 
            path, 
            to, 
            deadline);
    }

    // default function to transfer ethers to this contract
    fallback() external payable {}

    // withdraw ethers from this contract
    function withdraw(uint256 amount) external onlyOwner() {
        payable(msg.sender).transfer(amount);
    }
}        