// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import {IERC20Metadata} from "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";

import {IChainNftFacade} from "../registry/IChainNftFacade.sol";
import {IChainRegistryFacade} from "../registry/IChainRegistryFacade.sol";
import {IStakingFacade} from "../staking/IStakingFacade.sol";

// solhint-disable-next-line max-states-count
contract MockRegistryStaking is
    IChainNftFacade,
    IChainRegistryFacade,
    IStakingFacade
{

    // nft info
    string public constant NAME = "Dezentralized Insurance Protocol Registry (MOCK)";
    string public constant SYMBOL = "DIPR";

    // some object types
    uint8 public constant UNDEFINED = uint8(0);
    uint8 public constant CHAIN = uint8(2);
    uint8 public constant REGISTRY = uint8(3);
    uint8 public constant TOKEN = uint8(4);
    uint8 public constant STAKE = uint8(10);
    uint8 public constant INSTANCE = uint8(20);
    uint8 public constant PRODUCT = uint8(21);
    uint8 public constant ORACLE = uint8(22);
    uint8 public constant RISKPOOL = uint8(23);
    uint8 public constant POLICY = uint8(30);
    uint8 public constant BUNDLE = uint8(40);

    // stuff for rate calculation
    int8 public constant EXP = 18;
    uint256 public constant MULTIPLIER = 10 ** uint256(int256(EXP));

    event LogMockBundleRegistered(uint256 id, bytes5 chain, uint8 objectType, bytes32 instanceId, uint256 riskpoolId, uint256 bundleId, address to);


    // keep track of chain and object specific minted counts, and items
    mapping(bytes5 /* chain id*/ => mapping(uint8 /* object type */ => uint256 /* count*/)) private _objects;
    mapping(bytes32 /* instance id*/  => uint96 /* nft id*/) private _instance;
    mapping(bytes32 /* instance id*/  => mapping(uint256 /* component id */ => uint96 /* nft id*/)) private _component;
    mapping(bytes32 /* instance id*/  => mapping(uint256 /* bundle id */ => uint96 /* nft id*/)) private _bundle;

    // keep track of minted nft and stakes per nft
    mapping(uint256 /* nft id*/ => bool) private _isMinted;
    mapping(uint96 /* nft id*/ => uint256 /* dip amount */) private _stakes;

    // rates
    uint256 private _rewardRate;
    mapping(bytes5 /* chain id*/ => mapping(address /* token */ => uint256 /* rate */)) private _stakingRate;

    // owner, nft token id stuff
    address private _owner;

    uint256 private _chainIdInt; 
    bytes5 private _chainId; 
    uint256 private _chainIdDigits;
    uint256 private _chainIdMultiplier;
    uint256 private _idNext;
    uint256 private _totalMinted;

    // token references
    IERC20Metadata private _dip;
    IERC20Metadata private _usdt;

    constructor(address dipAddress, address usdtAddress) {
        _owner = msg.sender;

        _dip = IERC20Metadata(dipAddress);
        _usdt = IERC20Metadata(usdtAddress);

        _chainIdInt = block.chainid;
        _chainId = toChain(_chainIdInt);
        _chainIdDigits = _countDigits(_chainIdInt);
        _chainIdMultiplier = 10 ** _chainIdDigits;
        _idNext = 2;

        _mintObject(CHAIN);
        _mintObject(REGISTRY);

        _mintObject(TOKEN);
        _mintObject(TOKEN);

        _rewardRate = toRate(125, -3);
        setStakingRate(_chainId, usdtAddress, toRate(1,-1));
    }


    function owner() external override(IChainRegistryFacade, IStakingFacade) view returns(address) {
        return _owner;
    }

    //--- staking functions ------------------------------------------------//

    function getRegistry() external override(IChainNftFacade, IStakingFacade) view returns(IChainRegistryFacade) {
        return IChainRegistryFacade(this);
    }

    function getStakingWallet() external override view returns(address stakingWallet) {
        return address(this);
    }

    function getDip() external override view returns(IERC20Metadata) {
        return _dip;
    }

    function rewardRate() external override view returns(uint256 rate) {
        return _rewardRate;
    }

    function rewardBalance() external override pure returns(uint256 dipAmount) {
        return 0;
    }

    function rewardReserves() external override pure returns(uint256 dipAmount) {
        return 0;
    }

    function setStakingRate(bytes5 chain, address token, uint256 rate) public {
        _stakingRate[chain][token] = rate;
    }

    function maxRewardRate() external override pure returns(uint256 rate) {
        return _itof(333, -3);
    }

    function stakingRate(bytes5 chain, address token) external override view returns(uint256 rate) {
        return _stakingRate[chain][token];
    }

    function setStakedDip(uint96 targetNftId, uint256 dipAmount) public {
        _stakes[targetNftId] = dipAmount;
    }


    function capitalSupport(uint96 targetNftId) external override view returns(uint256 capitalAmount) {
        uint256 dipAmount = _stakes[targetNftId];
        uint256 rate = _stakingRate[_chainId][address(_usdt)];
        int8 decimals = int8(_usdt.decimals());
        int8 dipDecimals = int8(uint8(_dip.decimals()));
        uint256 support = _itof(dipAmount, decimals - dipDecimals) * rate;

        return support / MULTIPLIER;
    }


    function implementsIStaking() external override pure returns(bool) {
        return true;
    }

    function toRate(uint256 value, int8 exp) public override pure returns(uint256 rate) {
        return _itof(value, exp);
    }

    function rateDecimals() external override pure returns(uint256 decimals) {
        return uint256(uint8(EXP));
    }

    function version() external override(IChainRegistryFacade, IStakingFacade) pure returns(uint48) {
        return 1;
    }

    function versionParts()
        external
        override(IChainRegistryFacade, IStakingFacade)
        pure
        returns(
            uint16 major,
            uint16 minor,
            uint16 patch
        )
    {
        return (0, 0, 1);
    }

    //--- registry functions ------------------------------------------------//

    function mockRegisterRiskpool(
        bytes32 instanceId,
        uint256 riskpoolId
    )
        external
    {
        _checkMintInstance(instanceId);
        _checkMintRiskpool(instanceId, riskpoolId);
    }


    /* solhint-disable no-unused-vars */
    function registerBundle(
        bytes32 instanceId,
        uint256 riskpoolId,
        uint256 bundleId,
        string memory displayName,
        uint256 expiryAt
    )
    /* solhint-enable no-unused-vars */
        external
        override
        returns(uint96 nftId)
    {
        nftId = _checkMintBundle(instanceId, riskpoolId);
        emit LogMockBundleRegistered(nftId, _chainId, BUNDLE, instanceId, riskpoolId, bundleId, msg.sender);
    }


    function objects(bytes5 chain, uint8 objectType) external override view returns(uint256 numberOfObjects) {
        return _objects[chain][objectType];
    }

    function getInstanceNftId(bytes32 instanceId) external override view returns(uint96 id) {
        return _instance[instanceId];
    }

    function getComponentNftId(bytes32 instanceId, uint256 componentId) external override view returns(uint96 nftId) {
        return _component[instanceId][componentId];
    }

    function getBundleNftId(bytes32 instanceId, uint256 bundleId) external override view returns(uint96 nftId) {
        return _bundle[instanceId][bundleId];
    }


    function getNft() external override view returns(IChainNftFacade) {
        return IChainNftFacade(this);
    }

    function toChain(uint256 chainId) public override(IChainRegistryFacade, IStakingFacade) pure returns(bytes5 chain) {
        return bytes5(uint40(chainId));
    }

    //--- nft functions ------------------------------------------------------//

    // solhint-disable-next-line no-unused-vars
    function mint(address to, string memory uri) public override returns(uint256 tokenId) {
        tokenId = _getNextTokenId();
        _isMinted[tokenId] = true;
        _totalMinted++;
    }

    function name() external override pure returns (string memory) { return NAME; }
    function symbol() external override pure returns (string memory) { return SYMBOL; }
    function totalMinted() external override view returns(uint256) { return _totalMinted; }

    function exists(uint256 tokenId) external override view returns(bool) {
        return _isMinted[uint96(tokenId)];
    }

    function exists(uint96 tokenId) external override view returns(bool) {
        return _isMinted[tokenId];
    }




    //--- internal functions ------------------------------------------------------//

    function _itof(uint256 a, int8 exp) internal pure returns(uint256) {
        return a * 10 ** uint8(EXP + exp);
    }


    function _checkMintInstance(bytes32 instanceId) internal returns(uint96 nftId) {
        nftId = _instance[instanceId];

        if(nftId == 0) {
            nftId = _mintObject(INSTANCE);
            _instance[instanceId] = nftId;
        }
    }


    function _checkMintRiskpool(bytes32 instanceId, uint256 riskpoolId) internal returns(uint96 nftId) {
        nftId = _component[instanceId][riskpoolId];

        if(nftId == 0) {
            nftId = _mintObject(RISKPOOL);
            _component[instanceId][riskpoolId] = nftId;
        }
    }


    function _checkMintBundle(bytes32 instanceId, uint256 bundleId) internal returns(uint96 nftId) {
        nftId = _bundle[instanceId][bundleId];

        if(nftId == 0) {
            nftId = _mintObject(BUNDLE);
            _bundle[instanceId][bundleId] = nftId;
        }
    }


    function _mintObject(uint8 objectType) internal returns(uint96 nftId) {
        nftId = uint96(mint(address(this), ""));
        _objects[_chainId][objectType] += 1;
    }


    function _getNextTokenId() private returns(uint256 id) {
        id = (_idNext * _chainIdMultiplier + _chainIdInt) * 100 + _chainIdDigits;
        _idNext++;
    }


    function _countDigits(uint256 num)
        private 
        pure 
        returns (uint256 count)
    {
        count = 0;
        while (num != 0) {
            count++;
            num /= 10;
        }
    }

}