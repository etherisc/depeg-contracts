// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

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

    IERC20Metadata private _token;

    mapping(uint256 /* price-id */=> PriceInfo) private _priceData;
    uint256 [] private _priceIds;

    uint256 private _lastPriceId;
    uint256 private _triggeredAt;
    uint256 private _depeggedAt;

    constructor(address testTokenAddress) 
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
        if(block.chainid == MAINNET) {
            _token = IERC20Metadata(USDC_CONTACT_ADDRESS);
        }
        else if(block.chainid == GANACHE) {
            _token = IERC20Metadata(testTokenAddress);
        }
    }


    function getLatestPriceInfo()
        public override
        returns(PriceInfo memory priceInfo)
    {
        return getPriceInfo(type(uint256).max);
    }


    function getPriceInfo(
        uint256 priceId
    ) 
        public override
        returns(PriceInfo memory priceInfo)
    {
        require(priceId > 0, "PRICE_ID_ZERO");
        require(
            priceId == type(uint256).max
            || (priceId < type(uint80).max && _lastPriceId == 0)
            || priceId == _lastPriceId + 1,
            "PRICE_ID_INVALID");

        uint80 roundId;
        int256 answer;
        uint256 startedAt;
        uint256 updatedAt;
        uint80 answeredInRound;

        if(priceId == type(uint256).max) {
            (
                roundId,
                answer,
                startedAt,
                updatedAt,
                answeredInRound
            ) = latestRoundData();
        }
        else {
            (
                roundId,
                answer,
                startedAt,
                updatedAt,
                answeredInRound
            ) = getRoundData(uint80(priceId));
        }

        require(answer >= 0, "NEGATIVE_PRICE_VALUES_INVALID");

        uint256 price = uint256(answer);
        IPriceDataProvider.ComplianceState compliance = _calculateCompliance(roundId, price, updatedAt);
        IPriceDataProvider.StabilityState stability =_calculateStability(roundId, price, updatedAt);

        priceInfo = PriceInfo(
            roundId,
            price,
            compliance,
            stability,
            _triggeredAt,
            _depeggedAt,
            updatedAt
        );

        _lastPriceId = roundId;

        // TODO verify if this is really needed ...
        _updatePriceData(priceInfo);
    }


    function _calculateCompliance(
        uint256 roundId,
        uint256 price,
        uint256 updatedAt
    )
        internal
        returns(IPriceDataProvider.ComplianceState compliance)
    {
        if(_priceIds.length < 1) {
            return IPriceDataProvider.ComplianceState.Initializing;
        }

        // check against last recored states to decide compliance state
        bool isCompliant = true;
        uint256 lastIdx = _priceIds.length - 1;
        uint256 lastPriceId = _priceIds[lastIdx];
        PriceInfo memory lastInfo = _priceData[lastPriceId];

        // check deviation
        if(isExceedingDeviation(price, lastInfo.price)) {
            emit LogPriceDataDeviationExceeded(
                roundId,
                price > lastInfo.price ? price - lastInfo.price : lastInfo.price - price,
                price,
                lastInfo.price);

            isCompliant = false;
        }

        // check heartbeat
        if(isExceedingHeartbeat(updatedAt, lastInfo.createdAt)) {
            emit LogPriceDataHeartbeatExceeded(
                roundId,
                updatedAt - lastInfo.createdAt,
                updatedAt,
                lastInfo.createdAt);

            isCompliant = false;
        }

        if(isCompliant) {
            return IPriceDataProvider.ComplianceState.Valid;
        }

        if(lastInfo.compliance == IPriceDataProvider.ComplianceState.Valid
            || lastInfo.compliance == IPriceDataProvider.ComplianceState.Initializing) 
        {
            return IPriceDataProvider.ComplianceState.FailedOnce;
        }
        
        return IPriceDataProvider.ComplianceState.FailedMultipleTimes;
    }


    function _calculateStability(
        uint256 roundId,
        uint256 price,
        uint256 updatedAt
    )
        internal
        returns(IPriceDataProvider.StabilityState stability)
    {
        if(_lastPriceId == 0) {
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
                emit LogPriceDataDepegged (
                    roundId,
                    price,
                    _triggeredAt,
                    updatedAt);

                _depeggedAt = updatedAt;
                return IPriceDataProvider.StabilityState.Depegged;
            }

            // check for potential recovery
            if(price >= DEPEG_RECOVERY_PRICE) {
                emit LogPriceDataRecovered (
                    roundId,
                    price,
                    _triggeredAt,
                    updatedAt);

                _triggeredAt = 0;
                return IPriceDataProvider.StabilityState.Stable;
            }

            // remaining in triggered state
            return IPriceDataProvider.StabilityState.Triggered;
        } 

        // check potential change into triggerd state
        if(price <= DEPEG_TRIGGER_PRICE) {
            emit LogPriceDataTriggered (
                roundId,
                price,
                updatedAt);

            _triggeredAt = updatedAt;
            return IPriceDataProvider.StabilityState.Triggered;
        }

        // everything fine 
        return IPriceDataProvider.StabilityState.Stable;
    }

    function _updatePriceData(PriceInfo memory priceInfo) 
        internal
    {
        uint256 latestPriceId = 0;
        uint256 newPriceId = priceInfo.id;

        if(_priceIds.length > 0) {
            latestPriceId = _priceIds[_priceIds.length - 1];
        }

        if(_priceData[newPriceId].createdAt == 0 && newPriceId > latestPriceId) {
            _priceData[newPriceId] = priceInfo;
            _priceIds.push(newPriceId);
        }
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

    function getToken() external override view returns(IERC20Metadata tokenAddress) {
        return _token;
    }
}
