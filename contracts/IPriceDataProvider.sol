// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";

interface IPriceDataProvider {

    enum ComplianceState {
        Initializing,
        Valid,
        FailedOnce,
        FailedMultipleTimes
    }

    enum StabilityState {
        Initializing,
        Stable,
        Triggered,
        Depegged
    }

    event LogPriceDataDeviationExceeded (
        uint256 priceId,
        uint256 priceDeviation,
        uint256 currentPrice,
        uint256 lastPrice);

    event LogPriceDataHeartbeatExceeded (
        uint256 priceId,
        uint256 timeDifference,
        uint256 currentCreatedAt,
        uint256 lastCreatedAt);

    struct PriceInfo {
        uint256 id;
        uint256 price;
        ComplianceState compliance;
        StabilityState stability;
        uint256 createdAt;
    }

    function getLatestPriceInfo()
        external 
        returns(PriceInfo memory priceInfo);
    
    function getPriceInfo(
        uint256 priceId
    ) 
        external 
        returns(PriceInfo memory priceInfo);

    function getAggregatorAddress() external view returns(address aggregatorAddress);
    function getHeartbeat() external view returns(uint256 heartbeatSeconds);
    function getDeviation() external view returns(uint256 deviationLevel);
    function getDecimals() external view returns(uint8 aggregatorDecimals);

    function getToken() external view returns(IERC20Metadata token);
}
