// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

contract USD1 is ERC20 {

    string public constant NAME = "USD Stable Coin 1";
    string public constant SYMBOL = "USDC";

    uint256 public constant INITIAL_SUPPLY = 10**24;

    constructor()
        ERC20(NAME, SYMBOL)
    {
        _mint(
            _msgSender(),
            INITIAL_SUPPLY
        );
    }
}

contract USD2 is ERC20 {

    string public constant NAME = "USD Stable Coin 2";
    string public constant SYMBOL = "USDT";

    uint256 public constant INITIAL_SUPPLY = 10**24;

    constructor()
        ERC20(NAME, SYMBOL)
    {
        _mint(
            _msgSender(),
            INITIAL_SUPPLY
        );
    }
}


contract DIP is ERC20 {

    // https://etherscan.io/token/0xc719d010b63e5bbf2c0551872cd5316ed26acd83#readContract
    string public constant NAME = "Decentralized Insurance Protocol";
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
