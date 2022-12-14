// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";

import "./AggregatorDataProvider.sol";
import "./IPriceDataProvider.sol";

contract UsdcPriceDataProvider is
    AggregatorDataProvider, 
    IPriceDataProvider
{
    event LogUsdcProviderForcedDepeg (uint256 updatedTriggeredAt, uint256 forcedDepegAt);
    event LogUsdcProviderResetDepeg (uint256 resetDepegAt);

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
    PriceInfo private _latestPriceInfo;
    PriceInfo private _depegPriceInfo;

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
    }


    function processLatestPriceInfo()
        public override
        returns(PriceInfo memory priceInfo)
    {
        (
            uint80 roundId,
            int256 answer,
            uint256 startedAt,
            uint256 updatedAt,
            uint80 answeredInRound
        ) = latestRoundData();

        require(answer >= 0, "ERROR:UPDP-020:NEGATIVE_PRICE_VALUES_INVALID");
        require(roundId >= _latestPriceInfo.id, "ERROR:UPDP-021:PRICE_ID_SEQUENCE_INVALID");

        if(roundId == _latestPriceInfo.id) {
            return _latestPriceInfo;
        }

        uint256 price = uint256(answer);
        IPriceDataProvider.ComplianceState compliance = _calculateCompliance(roundId, price, updatedAt);
        IPriceDataProvider.StabilityState stability =_calculateStability(roundId, price, updatedAt);

        priceInfo = PriceInfo(
            roundId,
            price,
            compliance,
            stability,
            _latestPriceInfo.triggeredAt,
            _latestPriceInfo.depeggedAt,
            updatedAt
        );

        // record depeg price info
        // the price recorded here will be used to determine payout amounts
        if(_depegPriceInfo.depeggedAt == 0 && priceInfo.depeggedAt > 0) {
            _depegPriceInfo = priceInfo;
        }

        _latestPriceInfo = priceInfo;
    }

    function forceDepegForNextPriceInfo()
        external override
        onlyOwner()
        onlyTestnet()
    {
        require(_latestPriceInfo.triggeredAt > DEPEG_RECOVERY_WINDOW, "ERROR:UPDP-030:TRIGGERED_AT_TOO_SMALL");
        _latestPriceInfo.triggeredAt -= DEPEG_RECOVERY_WINDOW;

        emit LogUsdcProviderForcedDepeg(_latestPriceInfo.triggeredAt, block.timestamp);
    }

    function resetDepeg()
        external override
        onlyOwner()
        onlyTestnet()
    {
        // reset any info that will be copied over
        // to next latest price info
        _latestPriceInfo.compliance = IPriceDataProvider.ComplianceState.Valid;
        _latestPriceInfo.stability = IPriceDataProvider.StabilityState.Stable;
        _latestPriceInfo.triggeredAt = 0;
        _latestPriceInfo.depeggedAt = 0;

        // reset depeg price info
        _depegPriceInfo.id = 0;
        _depegPriceInfo.price = 0;
        _depegPriceInfo.compliance = IPriceDataProvider.ComplianceState.Initializing;
        _depegPriceInfo.stability = IPriceDataProvider.StabilityState.Initializing;
        _depegPriceInfo.triggeredAt = 0;
        _depegPriceInfo.depeggedAt = 0;
        _depegPriceInfo.createdAt = 0;

        emit LogUsdcProviderResetDepeg(block.timestamp);
    }

    function hasNewPriceInfo()
        external override
        view
        returns(
            bool newInfoAvailable, 
            uint256 priceId,
            uint256 timeDelta
        )
    {
        (
            uint80 roundId,
            int256 answer,
            uint256 startedAt,
            uint256 updatedAt,
            uint80 answeredInRound
        ) = latestRoundData();

        if(roundId == _latestPriceInfo.id) {
            return (
                false,
                roundId,
                0
            );
        }

        return (
            true,
            roundId,
            updatedAt - _latestPriceInfo.createdAt
        );
    }

    function _calculateCompliance(
        uint256 roundId,
        uint256 price,
        uint256 updatedAt
    )
        internal
        returns(IPriceDataProvider.ComplianceState compliance)
    {
        if(_latestPriceInfo.id == 0) {
            return IPriceDataProvider.ComplianceState.Initializing;
        }

        // check against last recored states to decide compliance state
        bool isCompliant = true;

        // check deviation
        if(isExceedingDeviation(price, _latestPriceInfo.price)) {
            emit LogPriceDataDeviationExceeded(
                roundId,
                price > _latestPriceInfo.price ? price - _latestPriceInfo.price : _latestPriceInfo.price - price,
                price,
                _latestPriceInfo.price);

            isCompliant = false;
        }

        // check heartbeat
        if(isExceedingHeartbeat(updatedAt, _latestPriceInfo.createdAt)) {
            emit LogPriceDataHeartbeatExceeded(
                roundId,
                updatedAt - _latestPriceInfo.createdAt,
                updatedAt,
                _latestPriceInfo.createdAt);

            isCompliant = false;
        }

        if(isCompliant) {
            return IPriceDataProvider.ComplianceState.Valid;
        }

        if(_latestPriceInfo.compliance == IPriceDataProvider.ComplianceState.Valid
            || _latestPriceInfo.compliance == IPriceDataProvider.ComplianceState.Initializing) 
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
        if(_latestPriceInfo.id == 0) {
            return IPriceDataProvider.StabilityState.Initializing;
        }

        // once depegged, state remains depegged
        if(_latestPriceInfo.depeggedAt > 0) {
            return IPriceDataProvider.StabilityState.Depegged;
        }

        // check triggered state:
        // triggered and not recovered within recovery window
        if(_latestPriceInfo.triggeredAt > 0) {

            // check if recovery run out of time and we have depegged
            if(updatedAt - _latestPriceInfo.triggeredAt > DEPEG_RECOVERY_WINDOW) {
                emit LogPriceDataDepegged (
                    roundId,
                    price,
                    _latestPriceInfo.triggeredAt,
                    updatedAt);

                _latestPriceInfo.depeggedAt = updatedAt;
                return IPriceDataProvider.StabilityState.Depegged;
            }

            // check for potential recovery
            if(price >= DEPEG_RECOVERY_PRICE) {
                emit LogPriceDataRecovered (
                    roundId,
                    price,
                    _latestPriceInfo.triggeredAt,
                    updatedAt);

                _latestPriceInfo.triggeredAt = 0;
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

            _latestPriceInfo.triggeredAt = updatedAt;
            return IPriceDataProvider.StabilityState.Triggered;
        }

        // everything fine 
        return IPriceDataProvider.StabilityState.Stable;
    }

    function getLatestPriceInfo()
        public override
        view
        returns(PriceInfo memory priceInfo)
    {
        return _latestPriceInfo;
    }

    function getDepegPriceInfo()
        public override
        view
        returns(PriceInfo memory priceInfo)
    {
        return _depegPriceInfo;
    }

    function getTriggeredAt() external override view returns(uint256 triggeredAt) {
        return _latestPriceInfo.triggeredAt;
    }

    function getDepeggedAt() external override view returns(uint256 depeggedAt) {
        return _latestPriceInfo.depeggedAt;
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
