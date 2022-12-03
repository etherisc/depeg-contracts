// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "./AggregatorDataProvider.sol";
import "./IPriceDataProvider.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";

contract UsdcPriceDataProvider is 
    AggregatorDataProvider, 
    IPriceDataProvider
{

    address public constant USDC_CONTACT_ADDRESS = 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48;
    address public constant CHAINLINK_USDC_USD_FEED_MAINNET = 0x8fFfFfd4AfB6115b954Bd326cbe7B4BA576818f6;

    string public constant CHAINLINK_TEST_DESCRIPTION = "USDC / USD (Ganache)";
    uint8 public constant CHAINLINK_TEST_DECIMALS = 8;
    uint256 public constant CHAINLINK_TEST_VERSION = 4;

    IERC20Metadata private _token;    

    constructor(address testTokenAddress) 
        AggregatorDataProvider(
            CHAINLINK_USDC_USD_FEED_MAINNET, 
            CHAINLINK_TEST_DESCRIPTION,
            CHAINLINK_TEST_DECIMALS,
            CHAINLINK_TEST_VERSION
        )
    {
        if(block.chainid == MAINNET) {
            _token = IERC20Metadata(USDC_CONTACT_ADDRESS);
        }
        else if(block.chainid == GANACHE) {
            _token = IERC20Metadata(testTokenAddress);
        }
    }


    function getLatestPriceInfo()
        external override
        view 
        returns(PriceInfo memory priceInfo)
    {
        return getPriceInfo(type(uint256).max);
    }


    function getPriceInfo(
        uint256 priceId
    ) 
        public override
        view 
        returns(PriceInfo memory priceInfo)
    {
        require(priceId > 0, "PRICE_ID_ZERO");
        require(priceId < type(uint80).max, "PRICE_ID_EXEEDING_UINT80");

        (
            uint80 roundId,
            int256 answer,
            uint256 startedAt,
            uint256 updatedAt,
            uint80 answeredInRound
        ) = getRoundData(uint80(priceId));

        require(answer >= 0, "NEGATIVE_PRICE_VALUES_INVALID");

        return PriceInfo(
            roundId,
            uint256(answer),
            updatedAt
        );
    }


    function getAggregatorAddress() external override view returns(address priceInfoSourceAddress) {
        return getChainlinkAggregatorAddress();
    }


    function getAggregatorDecimals() external override view returns(uint8 priceInfoDecimals) {
        return decimals();
    }


    function getTokenAddress() external override view returns(address tokenAddress) {
        return address(_token);
    }
}
