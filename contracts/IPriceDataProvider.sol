// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

interface IPriceDataProvider {

    struct PriceInfo {
        uint256 id;
        uint256 price;
        uint256 createdAt;
    }

    function getLatestPriceInfo()
        external 
        view 
        returns(PriceInfo memory priceInfo);
    
    function getPriceInfo(
        uint256 priceId
    ) 
        external 
        view 
        returns(PriceInfo memory priceInfo);

    function getAggregatorAddress() external view returns(address priceInfoSourceAddress);
    function getAggregatorDecimals() external view returns(uint8 priceInfoDecimals);
    function getTokenAddress() external view returns(address tokenAddress);
}
