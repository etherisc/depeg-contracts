#!/bin/bash

export GIF=/gif-contracts

if [ -d "$GIF/.git" ]; then
    exit 0
fi

# checkout gif and compile it
echo ">>>> Checking out GIF contracts..."
git clone git@github.com:etherisc/gif-contracts.git $GIF
cd $GIF
git switch release/2.0.0-rc.x

echo ">>>> Compiling GIF contracts..."
brownie compile --all
echo "" > .env

echo ">>>> GIF checkout completed. Registry address is saved in gif_instance_address.txt"
