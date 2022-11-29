// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

interface IStakingDataProvider {


    function getBundleStakes(
        bytes32 instanceId,
        uint256 bundleId
    ) 
        external 
        view 
        returns(uint256 stakedDipAmount);


    function getSupportedCapitalAmount(
        bytes32 instanceId,
        uint256 bundleId,
        address token
    ) 
        external 
        view 
        returns(uint256 supportedCapitalAmount);
}
