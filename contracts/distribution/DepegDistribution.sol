// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import {IERC20Metadata} from "@openzeppelin/contracts/token/ERC20/extensions/IERC20Metadata.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {DepegProduct} from "../DepegProduct.sol";
import {DepegRiskpool} from "../DepegRiskpool.sol";

contract DepegDistribution is
    Ownable
{
    struct DistributorInfo {
        uint256 commissionRate;
        uint256 commissionBalance;
        uint256 policiesSold;
        uint256 createdAt;
        uint256 updatedAt;
    }

    event LogDepegPolicySold(address distributor, bytes32 processId, uint256 premiumTotalAmount, address protectedWallet, uint256 protectedBalance);
    event LogDistributionInfoUpdated(address distributor, uint256 commissionAmount, uint256 commissionBalance, uint256 totalPoliciesSold);

    uint8 public constant DECIMALS = 18;
    uint256 public constant COMMISSION_RATE_DEFAULT = 5 * 10 ** (DECIMALS - 2);

    DepegProduct private _depegProduct;
    DepegRiskpool private _depegRiskpool;
    IERC20Metadata private _token;
    mapping(address => DistributorInfo) private _distributor;
    address [] private _distributors;


    modifier onlyDistributor() {
        require(
            isDistributor(msg.sender), 
            "ERROR:DST-001:NOT_DISTRIBUTOR"
        );
        _;
    }

    constructor(
        address depegProduct,
        address depegRiskpool,
        uint256 productId
    )
        Ownable()
    {
        _depegProduct = DepegProduct(depegProduct);
        require(_depegProduct.getId() == productId, "ERROR:DST-010:PRODUCT_ID_MISMATCH");

        _depegRiskpool = DepegRiskpool(depegRiskpool);
        require(_depegProduct.getRiskpoolId() == _depegRiskpool.getId(), "ERROR:DST-011:RISKPOOL_ID_MISMATCH");

        _token = IERC20Metadata(_depegProduct.getToken());
    }

    function createDistributor(address distributor)
        external
        onlyOwner()
        returns (DistributorInfo memory)
    {
        require(!isDistributor(distributor), "ERROR:DST-020:DISTRIBUTOR_ALREADY_EXISTS");
        
        _distributor[distributor] = DistributorInfo(
            COMMISSION_RATE_DEFAULT,
            0, // commissionAmount,
            0, // policiesSold
            block.timestamp, // createdAt
            block.timestamp // updatedAt
        );

        _distributors.push(distributor);

        return _distributor[distributor];

    }

    /// @dev lets a distributor create a policy for the specified wallet address
    // the policy holder is this contract, the beneficiary is the specified wallet address
    function createPolicy(
        address buyer,
        address protectedWallet,
        uint256 protectedBalance,
        uint256 duration,
        uint256 bundleId
    ) 
        external
        onlyDistributor()
        returns(bytes32 processId)
    {
        // collect premium and commission from buyer to this contract
        (uint256 premiumTotalAmount,) = _collectTokenAndUpdateCommission(
            buyer, 
            protectedBalance, 
            duration, 
            bundleId);

        // create policy
        // this will transfer premium amount from this contract to depeg (and keep the commission in this contract)
        processId = _depegProduct.applyForPolicyWithBundle(
            protectedWallet,
            protectedBalance,
            duration,
            bundleId);

        emit LogDepegPolicySold(msg.sender, processId, premiumTotalAmount, protectedWallet, protectedBalance);
    }

    function _collectTokenAndUpdateCommission(
        address buyer,
        uint256 protectedBalance,
        uint256 duration,
        uint256 bundleId
    )
        internal
        returns (
            uint256 premiumTotalAmount,
            uint256 commissionAmount
        )
    {
        address distributor = msg.sender;

        // calculate premium and commission amount
        (
            premiumTotalAmount,
            commissionAmount
        ) = calculatePrice(distributor, protectedBalance, duration, bundleId);

        // update distributor book keeping record
        DistributorInfo storage info = _distributor[distributor];
        info.commissionBalance += commissionAmount;
        info.policiesSold += 1;
        info.updatedAt = block.timestamp;

        // collect total premium amount
        _token.transferFrom(buyer, address(this), premiumTotalAmount);

        emit LogDistributionInfoUpdated(distributor, commissionAmount, info.commissionBalance, info.policiesSold);
    }


    function calculatePrice(
        address distributor, 
        uint256 protectedBalance, 
        uint256 duration, 
        uint256 bundleId
    )
        public
        view
        returns (
            uint256 premiumTotalAmount,
            uint256 commissionAmount
        )
    {
        // TODO fetch policy price
        uint256 sumInsured = _depegRiskpool.calculateSumInsured(protectedBalance);
        uint256 netPremium = _depegProduct.calculateNetPremium(
            sumInsured,
            duration,
            bundleId);

        uint256 depegPremium = _depegProduct.calculatePremium(netPremium);

        // TODO calculate commission and total premium
        commissionAmount = calculateCommission(distributor, depegPremium);
        premiumTotalAmount = depegPremium + commissionAmount;
    } 

    function calculateCommission(address distributor, uint256 netPremiumAmount)
        public
        view
        returns(uint256 commissionAmount)
    {
        uint256 rate = _distributor[distributor].commissionRate;
        if(rate == 0) {
            return 0;
        }
        
        return (netPremiumAmount * rate) / (10**DECIMALS - rate);
    }

    function withdraw(uint256 amount)
        external
        onlyOwner()
    {
        require(_token.balanceOf(address(this)) >= amount, "ERROR:DST-010:COMMISION_BALANCE_TOO_LARGE");
    }

    function withdrawCommission(uint256 amount)
        external
        onlyDistributor()
    {
        require(getCommissionBalance(msg.sender) >= amount, "ERROR:DST-021:COMMISION_AMOUNT_TOO_LARGE");
        require(_token.balanceOf(address(this)) >= amount, "ERROR:DST-022:COMMISION_BALANCE_INSUFFICIENT");
    }

    function getToken() external view returns (address token) {
        return address(_token);
    }

    function distributors() external view returns(uint256) {
        return _distributors.length;
    }

    function getDistributor(uint256 idx) external view returns(address) {
        return _distributors[idx];
    }

    function isDistributor(address distributor) public view returns (bool) {
        return _distributor[distributor].createdAt > 0;
    }

    function getPoliciesSold(address distributor) external view returns (uint256 policies) {
        return _distributor[distributor].policiesSold;
    }

    function getCommissionBalance(address distributor) public view returns (uint256 commissionAmount) {
        return _distributor[distributor].commissionBalance;
    }

    function getCommissionRate(address distributor) external view returns (uint256 commissionRate) {
        return _distributor[distributor].commissionRate;
    }
}