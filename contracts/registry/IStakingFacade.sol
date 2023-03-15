// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.2;

import "./IChainRegistryFacade.sol";

interface IStakingFacade {

    function getRegistry() external view returns(IChainRegistryFacade);
    function capitalSupport(uint256 targetNftId) external view returns(uint256 capitalAmount);
    function implementsIStaking() external pure returns(bool);

}