// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";

import "./AggregatorDataProvider.sol";
import "./IPriceDataProvider.sol";

contract UsdcPriceDataProvider is
    AggregatorDataProvider, 
    IPriceDataProvider
{
    address public constant USDC_CONTACT_ADDRESS = 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48;
    address public constant CHAINLINK_USDC_USD_FEED_MAINNET = 0x8fFfFfd4AfB6115b954Bd326cbe7B4BA576818f6;
    uint8 public constant CHAINLINK_USDC_DECIMALS = 8;

    uint256 public constant DEPEG_TRIGGER_PRICE = 995 * 10**CHAINLINK_USDC_DECIMALS / 1000; // USDC below 0.995 USD triggers depeg alert
    uint256 public constant DEPEG_RECOVERY_PRICE = 999 * 10**CHAINLINK_USDC_DECIMALS / 1000; // USDC at/above 0.999 USD is find and/or is considered a recovery from a depeg alert
    uint256 public constant DEPEG_RECOVERY_WINDOW = 24 * 3600;

    uint256 public constant PRICE_INFO_HISTORY_DURATION = 7 * 24 * 3600; // keep price info for 1 week

    string public constant CHAINLINK_TEST_DESCRIPTION = "USDC / USD (Ganache)";
    uint256 public constant CHAINLINK_TEST_VERSION = 4;

    // see https://docs.chain.link/data-feeds/price-feeds/addresses
    // deviation: 0.25%
    // heartbeat: 86400 (=24 * 60 * 60)
    uint256 public constant CHAINLINK_USDC_USD_DEVIATION = 25 * 10**CHAINLINK_USDC_DECIMALS / 10000;

    // TODO evaluate margin over full chainlink price feed history
    uint256 public constant CHAINLINK_HEARTBEAT_MARGIN = 100;
    uint256 public constant CHAINLINK_USDC_USD_HEARTBEAT = 24 * 3600;

    uint8 public constant PRICE_HISTORY_SIZE = 20;

    IERC20Metadata private _token;

    PriceInfo private _depegPriceInfo;
    uint256 private _triggeredAt;
    uint256 private _depeggedAt;

    constructor(address tokenAddress) 
        AggregatorDataProvider(
            CHAINLINK_USDC_USD_FEED_MAINNET, 
            CHAINLINK_USDC_USD_DEVIATION,
            CHAINLINK_USDC_USD_HEARTBEAT,
            CHAINLINK_HEARTBEAT_MARGIN,
            CHAINLINK_TEST_DESCRIPTION,
            CHAINLINK_USDC_DECIMALS,
            CHAINLINK_TEST_VERSION
        )
    {
        if(isMainnet()) {
            _token = IERC20Metadata(USDC_CONTACT_ADDRESS);
        } else if(isTestnet()) {
            _token = IERC20Metadata(tokenAddress);
        } else {
            revert("ERROR:UPDP-010:CHAIN_NOT_SUPPORTET");
        }

        _triggeredAt = 0;
        _depeggedAt = 0;
    }


    function getLatestPriceInfo()
        public override
        view
        returns(PriceInfo memory priceInfo)
    {
        (
            uint80 roundId,
            int256 answer,
            , // startedAt unused
            uint256 updatedAt,
             // answeredInRound unused
        ) = latestRoundData();

        require(answer >= 0, "ERROR:UPDP-020:NEGATIVE_PRICE_VALUES_INVALID");

        uint256 price = uint256(answer);

        IPriceDataProvider.ComplianceState compliance = getComplianceState(roundId, price, updatedAt);
        IPriceDataProvider.StabilityState stability = getStability(roundId, price, updatedAt);

        // calculate event type, triggered at and depegged at
        IPriceDataProvider.EventType eventType = IPriceDataProvider.EventType.Update;
        uint256 triggeredAt = _triggeredAt;
        uint256 depeggedAt = _depeggedAt;
        
        // check all possible state changing transitions
        // enter depegged state
        if(stability == IPriceDataProvider.StabilityState.Depegged && _depeggedAt == 0) {
            eventType = IPriceDataProvider.EventType.DepegEvent;
            depeggedAt = updatedAt;
        // enter triggered state
        } else if(stability == IPriceDataProvider.StabilityState.Triggered && _triggeredAt == 0) {
            eventType = IPriceDataProvider.EventType.TriggerEvent;
            triggeredAt = updatedAt;
        // recover from triggered state
        } else if(stability == IPriceDataProvider.StabilityState.Stable && _triggeredAt > 0) {
            eventType = IPriceDataProvider.EventType.RecoveryEvent;
        }

        return PriceInfo(
            roundId,
            price,
            compliance,
            stability,
            eventType,
            triggeredAt,
            depeggedAt,
            updatedAt
        );
    }


    function processLatestPriceInfo()
        public override
        returns(PriceInfo memory priceInfo)
    {
        priceInfo = getLatestPriceInfo();

        if(priceInfo.eventType == IPriceDataProvider.EventType.DepegEvent) {
            _depegPriceInfo = priceInfo;
            _depeggedAt = priceInfo.depeggedAt;

            emit LogPriceDataDepegged(
                priceInfo.id,
                priceInfo.price,
                priceInfo.triggeredAt,
                priceInfo.depeggedAt);

        } else if(priceInfo.eventType == IPriceDataProvider.EventType.TriggerEvent) {
            _triggeredAt = priceInfo.triggeredAt;

            emit LogPriceDataTriggered(
                priceInfo.id,
                priceInfo.price,
                priceInfo.triggeredAt);

        } else if(priceInfo.eventType == IPriceDataProvider.EventType.RecoveryEvent) {
            _triggeredAt = 0;

            emit LogPriceDataRecovered(
                priceInfo.id,
                priceInfo.price,
                priceInfo.triggeredAt,
                priceInfo.createdAt);
        } else {
            emit LogPriceDataProcessed(
                priceInfo.id,
                priceInfo.price,
                priceInfo.createdAt);
        }

    }


    function forceDepegForNextPriceInfo()
        external override
        onlyOwner()
        onlyTestnet()
    {
        require(_triggeredAt > DEPEG_RECOVERY_WINDOW, "ERROR:UPDP-030:TRIGGERED_AT_TOO_SMALL");

        _triggeredAt -= DEPEG_RECOVERY_WINDOW;

        emit LogUsdcProviderForcedDepeg(_triggeredAt, block.timestamp);
    }

    function resetDepeg()
        external override
        onlyOwner()
        onlyTestnet()
    {
        _depegPriceInfo.id = 0;
        _depegPriceInfo.price = 0;
        _depegPriceInfo.compliance = IPriceDataProvider.ComplianceState.Undefined;
        _depegPriceInfo.stability = IPriceDataProvider.StabilityState.Undefined;
        _depegPriceInfo.triggeredAt = 0;
        _depegPriceInfo.depeggedAt = 0;
        _depegPriceInfo.createdAt = 0;

        _triggeredAt = 0;
        _depeggedAt = 0;

        emit LogUsdcProviderResetDepeg(block.timestamp);
    }


    function isNewPriceInfoEventAvailable()
        external override
        view
        returns(
            bool newEvent, 
            PriceInfo memory priceInfo,
            uint256 timeSinceEvent
        )
    {
        priceInfo = getLatestPriceInfo();
        newEvent = !(priceInfo.eventType == IPriceDataProvider.EventType.Undefined 
            || priceInfo.eventType == IPriceDataProvider.EventType.Update);
        timeSinceEvent = priceInfo.createdAt == 0 ? 0 : block.timestamp - priceInfo.createdAt;
    }


    function getCompliance(
        uint80 roundId,
        uint256 price,
        uint256 updatedAt
    )
        public view
        returns(
            bool priceDeviationIsValid,
            bool heartbeetIsValid,
            uint256 previousPrice,
            uint256 previousUpdatedAt
        )
    {
        if(roundId == 0) {
            return (
                true,
                true,
                0,
                0);
        }

        (
            , // roundId unused
            int256 previousPriceInt,
            , // startedAt unused
            uint256 previousUpdatedAtUint,
             // answeredInRound unused
        ) = getRoundData(roundId - 1);

        if(previousUpdatedAtUint == 0) {
            return (
                true,
                true,
                previousPrice,
                previousUpdatedAtUint);
        }

        previousPrice = uint256(previousPriceInt);

        return (
            !isExceedingDeviation(price, previousPrice),
            !isExceedingHeartbeat(updatedAt, previousUpdatedAtUint),
            previousPrice,
            previousUpdatedAtUint);
    }


    function getStability(
        uint256 roundId,
        uint256 price,
        uint256 updatedAt
    )
        public
        view
        returns(IPriceDataProvider.StabilityState stability)
    {
        // no price data available (yet)
        // only expected with test setup
        if(updatedAt == 0) {
            return IPriceDataProvider.StabilityState.Initializing;
        }

        // once depegged, state remains depegged
        if(_depeggedAt > 0) {
            return IPriceDataProvider.StabilityState.Depegged;
        }

        // check triggered state:
        // triggered and not recovered within recovery window
        if(_triggeredAt > 0) {

            // check if recovery run out of time and we have depegged
            if(updatedAt - _triggeredAt > DEPEG_RECOVERY_WINDOW) {
                return IPriceDataProvider.StabilityState.Depegged;
            }

            // check for recovery
            if(price >= DEPEG_RECOVERY_PRICE) {
                return IPriceDataProvider.StabilityState.Stable;
            }

            // remaining in triggered state
            return IPriceDataProvider.StabilityState.Triggered;
        } 

        // check potential change into triggerd state
        if(price <= DEPEG_TRIGGER_PRICE) {
            return IPriceDataProvider.StabilityState.Triggered;
        }

        // everything fine 
        return IPriceDataProvider.StabilityState.Stable;
    }


    function getComplianceState(
        uint256 roundId,
        uint256 price,
        uint256 updatedAt
    )
        public
        view
        returns(IPriceDataProvider.ComplianceState compliance)
    {
        (
            bool priceDeviationIsValid,
            bool heartbeetIsValid,
            uint256 previousPrice,
            uint256 previousUpdatedAt
        ) = getCompliance(uint80(roundId), price, updatedAt);

        if(previousUpdatedAt == 0) {
            return IPriceDataProvider.ComplianceState.Initializing;
        }

        if(priceDeviationIsValid && heartbeetIsValid) {
            return IPriceDataProvider.ComplianceState.Valid;
        }

        (
            bool previousPriceDeviationIsValid,
            bool previousHeartbeetIsValid,
            , // previousPrice not usedc
            uint256 prePreviousUpdatedAt
        ) = getCompliance(uint80(roundId-1), previousPrice, previousUpdatedAt);

        if((previousPriceDeviationIsValid && previousHeartbeetIsValid)
            || prePreviousUpdatedAt == 0)
        {
            return IPriceDataProvider.ComplianceState.FailedOnce;
        }

        return IPriceDataProvider.ComplianceState.FailedMultipleTimes;
    }

    function getDepegPriceInfo()
        public override
        view
        returns(PriceInfo memory priceInfo)
    {
        return _depegPriceInfo;
    }

    function getTriggeredAt() external override view returns(uint256 triggeredAt) {
        return _triggeredAt;
    }

    function getDepeggedAt() external override view returns(uint256 depeggedAt) {
        return _depeggedAt;
    }

    function getAggregatorAddress() external override view returns(address priceInfoSourceAddress) {
        return getChainlinkAggregatorAddress();
    }

    function getHeartbeat() external override view returns(uint256 heartbeatSeconds) {
        return heartbeat();
    }

    function getDeviation() external override view returns(uint256 deviationLevel) {
        return deviation();
    }

    function getDecimals() external override view returns(uint8 priceInfoDecimals) {
        return decimals();
    }

    function getToken() external override view returns(address) {
        return address(_token);
    }

    function getOwner() external override view returns(address) {
        return owner();
    }

    function isMainnetProvider()
        public override
        view
        returns(bool)
    {
        return isMainnet();
    }

    function isTestnetProvider()
        public override
        view
        returns(bool)
    {
        return isTestnet();
    }

}
