// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

contract USD1 is ERC20 {

    // https://etherscan.io/address/0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48#readProxyContract
    string public constant NAME = "USD Coin - DUMMY";
    string public constant SYMBOL = "USDC";
    uint8 public constant DECIMALS = 6;

    uint256 public constant INITIAL_SUPPLY = 10**24;

    event LogUsd1Transfer(address from, address to, uint256 amount, uint256 time, uint256 blockNumber);
    event LogUsd1TransferFrom(address from, address to, uint256 amount, uint256 time, uint256 blockNumber);
    constructor()
        ERC20(NAME, SYMBOL)
    {
        _mint(
            _msgSender(),
            INITIAL_SUPPLY
        );
    }

    function decimals() public pure override returns(uint8) {
        return DECIMALS;
    }

    function transfer(address to, uint256 amount) public virtual override returns (bool) {
        address from = _msgSender();
        emit LogUsd1TransferFrom(from, to, amount, block.timestamp, block.number);
        return super.transfer(to, amount);
    }
    
    function transferFrom(address from, address to, uint256 amount) 
        public virtual override returns (bool) 
    {
        emit LogUsd1TransferFrom(from, to, amount, block.timestamp, block.number);
        return super.transferFrom(from, to, amount);
    }    
}


contract USD2 is ERC20 {

    // https://etherscan.io/address/0xdac17f958d2ee523a2206206994597c13d831ec7
    string public constant NAME = "Tether USD - DUMMY";
    string public constant SYMBOL = "USDT";
    uint8 public constant DECIMALS = 6;

    uint256 public constant INITIAL_SUPPLY = 10**24;

    constructor()
        ERC20(NAME, SYMBOL)
    {
        _mint(
            _msgSender(),
            INITIAL_SUPPLY
        );
    }

    function decimals() public pure override returns(uint8) {
        return DECIMALS;
    }
}


contract USD3 is ERC20 {

    // https://etherscan.io/address/0xdac17f958d2ee523a2206206994597c13d831ec7
    string public constant NAME = "Dummy USD - DUMMY";
    string public constant SYMBOL = "DUSD";
    uint8 public constant DECIMALS = 13;

    uint256 public constant INITIAL_SUPPLY = 10**24;

    constructor()
        ERC20(NAME, SYMBOL)
    {
        _mint(
            _msgSender(),
            INITIAL_SUPPLY
        );
    }

    function decimals() public pure override returns(uint8) {
        return DECIMALS;
    }
}


contract DIP is ERC20 {

    // https://etherscan.io/token/0xc719d010b63e5bbf2c0551872cd5316ed26acd83#readContract
    string public constant NAME = "Decentralized Insurance Protocol - DUMMY";
    string public constant SYMBOL = "DIP";
    uint8 public constant DECIMALS = 18;
    uint256 public constant INITIAL_SUPPLY = 10**9 * 10**DECIMALS; // 1 Billion 1'000'000'000
    // decimals == 18 (openzeppelin erc20 default)
    constructor()
        ERC20(NAME, SYMBOL)
    {
        _mint(
            _msgSender(),
            INITIAL_SUPPLY
        );   
    }

    function decimals() public pure override returns(uint8) {
        return DECIMALS;
    }
}
