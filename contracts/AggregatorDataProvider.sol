// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "@chainlink/contracts/src/v0.8/interfaces/AggregatorV3Interface.sol";

contract AggregatorDataProvider is 
    AggregatorV3Interface 
{
    // matches return data for getRoundData/latestRoundData
    struct ChainlinkRoundData {
        uint80 roundId;
        int256 answer;
        uint256 startedAt;
        uint256 updatedAt;
        uint80 answeredInRound;
    }

    uint256 public constant MAINNET = 1;
    uint256 public constant GANACHE = 1337;
    
    AggregatorV3Interface private _aggregator;

    string private _description;
    uint8 private _decimals;
    uint256 private _version;

    mapping(uint80 /* round id */ => ChainlinkRoundData) private _aggregatorData;
    uint80 [] private _roundIds;


    constructor(
        address aggregatorAddress,
        string memory testDescription,
        uint8 testDecimals,
        uint256 testVersion
    ) 
    {
        if(block.chainid == MAINNET) {
            _aggregator = AggregatorV3Interface(aggregatorAddress);
        }
        else if(block.chainid == GANACHE) {
            _aggregator = AggregatorV3Interface(address(this));
            _description = testDescription;
            _decimals = testDecimals;
            _version = testVersion;
        }
    }

    function setRoundData (
        uint80 roundId,
        int256 answer,
        uint256 startedAt,
        uint256 updatedAt,
        uint80 answeredInRound
    )
        external
    {
        require(block.chainid == GANACHE, "CHAIN_NOT_GANACHE");

        _roundIds.push(roundId);
        _aggregatorData[roundId] = ChainlinkRoundData(
            roundId,
            answer,
            startedAt,
            updatedAt,
            answeredInRound
        );
    }

    function getChainlinkAggregatorAddress() public view returns(address) {
        return address(_aggregator);
    }

    function description() public override view returns (string memory) {
        if(block.chainid == MAINNET) {
            return _aggregator.description();
        }

        return _description;
    }

    function decimals() public override view returns(uint8) {
        if(block.chainid == MAINNET) {
            return _aggregator.decimals();
        }

        return _decimals;
    }

    function version() public override view returns (uint256) {
        if(block.chainid == MAINNET) {
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
        if(block.chainid == MAINNET) {
            return _aggregator.latestRoundData();
        }

        return getRoundData(type(uint80).max);
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
        if(block.chainid == MAINNET) {
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
}
