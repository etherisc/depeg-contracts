// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "@openzeppelin/contracts/access/Ownable.sol";

// V2V3 combines AggregatorInterface and AggregatorV3Interface
import "@chainlink/contracts/src/v0.8/interfaces/AggregatorV2V3Interface.sol";

contract AggregatorDataProvider is 
    Ownable,
    AggregatorV2V3Interface
{
    // matches return data for latestRoundData
    struct ChainlinkRoundData {
        uint80 roundId;
        int256 answer;
        uint256 startedAt;
        uint256 updatedAt;
        uint80 answeredInRound;
    }

    uint256 public constant MAINNET = 1;
    uint256 public constant GANACHE = 1337;
    uint256 public constant GANACHE2 = 1234;
    uint256 public constant MUMBAI = 80001;
    
    AggregatorV2V3Interface private _aggregator;

    uint256 private _deviation;
    uint256 private _heartbeat;
    uint256 private _heartbeatMargin;

    string private _description;
    uint8 private _decimals;
    uint256 private _version;

    mapping(uint80 /* round id */ => ChainlinkRoundData) private _aggregatorData;
    uint80 [] private _roundIds;
    uint80 private _maxRoundId;

    modifier onlyTestnet() {
        require(isTestnet(), "ERROR:ADP-001:NOT_TEST_CHAIN");
        _;
    }

    constructor(
        address aggregatorAddress,
        uint256 deviationLevel, // 10**decimals() corresponding to 100%
        uint256 heartbeatSeconds,
        uint256 heartbeatMarginSeconds,
        string memory testDescription,
        uint8 testDecimals,
        uint256 testVersion
    ) 
        Ownable()
    {
        if(isMainnet()) {
            _aggregator = AggregatorV2V3Interface(aggregatorAddress);
        } else if(isTestnet()) {
            _aggregator = AggregatorV2V3Interface(address(this));
        } else {
            revert("ERROR:ADP-010:CHAIN_NOT_SUPPORTET");
        }

        _description = testDescription;
        _decimals = testDecimals;
        _version = testVersion;

        _deviation = deviationLevel;
        _heartbeat = heartbeatSeconds;
        _heartbeatMargin = heartbeatMarginSeconds;

        _maxRoundId = 0;
    }

    function addRoundData(
        int256 answer,
        uint256 startedAt
    )
        external
    {
        _maxRoundId++;
        setRoundData(
            _maxRoundId,
            answer,
            startedAt,
            startedAt, // set updatedAt == startedAt
            _maxRoundId
        );
    }


    function setRoundData (
        uint80 roundId,
        int256 answer,
        uint256 startedAt,
        uint256 updatedAt,
        uint80 answeredInRound
    )
        public
        onlyOwner()
        onlyTestnet()
    {
        // update max roundId if necessary
        if(roundId > _maxRoundId) {
            _maxRoundId = roundId;
        }

        _roundIds.push(roundId);
        _aggregatorData[roundId] = ChainlinkRoundData(
            roundId,
            answer,
            startedAt,
            updatedAt,
            answeredInRound
        );
    }

    function getRoundData(uint80 _roundId)
        public override
        view
        returns (
            uint80 roundId,
            int256 answer,
            uint256 startedAt,
            uint256 updatedAt,
            uint80 answeredInRound
        )
    {
        if(isMainnet()) {
            return _aggregator.getRoundData(_roundId);
        }

        if(_roundId == type(uint80).max && _roundIds.length > 0) {
            _roundId = _roundIds[_roundIds.length - 1];
        }

        ChainlinkRoundData memory data = _aggregatorData[_roundId];

        return (
            data.roundId,
            data.answer,
            data.startedAt,
            data.updatedAt,
            data.answeredInRound
        );
    }

    function getChainlinkAggregatorAddress() public view returns(address) {
        return address(_aggregator);
    }

    function isExceedingDeviation(uint256 price1, uint256 price2) 
        public 
        view 
        returns(bool isExceeding)
    {
        if(price1 >= price2) {
            if(price1 - price2 > _deviation) {
                return true;
            }
        }
        else if(price2 - price1 > _deviation) {
            return true;
        }

        return false;
    }

    function isExceedingHeartbeat(uint256 time1, uint256 time2) 
        public 
        view 
        returns(bool isExceeding)
    {
        if(time1 >= time2) {
            if(time1 - time2 > _heartbeat + _heartbeatMargin) {
                return true;
            }
        }
        else if(time2 - time1 > _heartbeat + _heartbeatMargin) {
            return true;
        }

        return false;
    }

    function deviation() public view returns (uint256) {
        return _deviation;
    }

    function heartbeat() public view returns (uint256) {
        return _heartbeat;
    }

    function heartbeatMargin() public view returns (uint256) {
        return _heartbeatMargin;
    }

    function latestAnswer() external override view returns (int256) {
        if(isMainnet()) {
            return _aggregator.latestAnswer();
        }

        return _aggregatorData[_maxRoundId].answer;
    }

    function latestTimestamp() external override view returns (uint256) {
        if(isMainnet()) {
            return _aggregator.latestTimestamp();
        }

        return _aggregatorData[_maxRoundId].updatedAt;
    }

    function latestRound() external override view returns (uint256) {
        if(isMainnet()) {
            return _aggregator.latestRound();
        }

        return _maxRoundId;
    }

    function getAnswer(uint256 roundId) external override view returns (int256) {
        if(isMainnet()) {
            return _aggregator.getAnswer(roundId);
        }

        return _aggregatorData[uint80(roundId)].answer;
    }

    function getTimestamp(uint256 roundId) external override view returns (uint256) {
        if(isMainnet()) {
            return _aggregator.getTimestamp(roundId);
        }

        return _aggregatorData[uint80(roundId)].updatedAt;
    }

    function description() public override view returns (string memory) {
        if(isMainnet()) {
            return _aggregator.description();
        }

        return _description;
    }

    function decimals() public override view returns(uint8) {
        if(isMainnet()) {
            return _aggregator.decimals();
        }

        return _decimals;
    }

    function version() public override view returns (uint256) {
        if(isMainnet()) {
            return _aggregator.version();
        }

        return _version;
    }

    function latestRoundData()
        public override
        view
        returns (
            uint80 roundId,
            int256 answer,
            uint256 startedAt,
            uint256 updatedAt,
            uint80 answeredInRound
        )
    {
        if(isMainnet()) {
            return _aggregator.latestRoundData();
        }

        return getRoundData(type(uint80).max);
    }

    function isMainnet()
        public
        view
        returns(bool)
    {
        return block.chainid == MAINNET;
    }    

    function isTestnet()
        public
        view
        returns(bool)
    {
        return (block.chainid == GANACHE)
            || (block.chainid == GANACHE2)
            || (block.chainid == MUMBAI);
    }    
}
