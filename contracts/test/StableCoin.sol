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
