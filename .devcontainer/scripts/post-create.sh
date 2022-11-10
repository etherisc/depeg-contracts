#!/bin/bash

.devcontainer/scripts/checkout-gif.sh 

echo '>>>> Compiling depeg contracts ...'
echo "" > .env 
rm -rf build/
#brownie compile --all 
