// SPDX-License-Identifier: Apache-2.0
pragma solidity 0.8.2;

import "@openzeppelin/contracts/utils/math/Math.sol";

contract FixedMath {

    enum Rounding {
        Down, // floor(value)
        Up, // = ceil(value)
        HalfUp // = floor(value + 0.5)
    }

    int8 public constant EXP = 18;
    uint256 public constant MULTIPLIER = 10**uint256(int256(EXP));
    uint256 public constant MULTIPLIER_HALF = MULTIPLIER / 2;
    
    Rounding public constant ROUNDING_DEFAULT = Rounding.HalfUp;

    function itof(uint256 a)
        external
        pure
        returns(uint256 aUFixed)
    {
        return a * MULTIPLIER;
    }

    function itof(uint256 a, int8 exp)
        external
        pure
        returns(uint256 af)
    {
        require(EXP + exp >= 0, "ERROR:FM-010:EXPONENT_TOO_SMALL");
        require(EXP + exp <= 2 * EXP, "ERROR:FM-011:EXPONENT_TOO_LARGE");

        return a * 10 ** uint8(EXP + exp);
    }

    function ftoi(uint256 af)
        external
        pure
        returns(uint256 a)
    {
        return ftoi(af, ROUNDING_DEFAULT);
    }

    function ftoi(uint256 af, Rounding rounding)
        public
        pure
        returns(uint256 a)
    {
        if(rounding == Rounding.HalfUp) {
            return Math.mulDiv(af + MULTIPLIER_HALF, 1, MULTIPLIER, Math.Rounding.Down);
        } else if(rounding == Rounding.Down) {
            return Math.mulDiv(af, 1, MULTIPLIER, Math.Rounding.Down);
        } else {
            return Math.mulDiv(af, 1, MULTIPLIER, Math.Rounding.Up);
        }
    }

    function mul(uint256 af, uint256 bf) 
        external
        pure
        returns(uint256 abf)
    {
        return Math.mulDiv(af, bf, MULTIPLIER);
    }

    function div(uint256 af, uint256 bf) 
        external
        pure
        returns(uint256 a_bf)
    {
        require(bf > 0, "ERROR:FM-020:DIVISOR_ZERO");
        return Math.mulDiv(af, MULTIPLIER, bf);
    }

    function getMultiplier() external pure returns(uint256 multiplier) {
        return MULTIPLIER;
    }
}
