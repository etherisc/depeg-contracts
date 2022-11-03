# Depeg Insurance Contracts

This repository holds the smart contracts for a depeg insurance for stable coins.

## Product Considerations

### What is insured?

A depeg policy covers the risk of a depeg of stable coin USD1 from the fiat currency USD.

* The insured buys a policy to insure the depeg risk of stable coin USD1.
* In a depeg event the loss amount is payed out in stable coin USD2.
* The risk that stable coin USD2 has depegged at the same time is not covered.

Policy parameters:
* Sum insured amount of X in USD1
* Maximum premium payment of amount Y in USD2 the policy holder is willing to pay
* Actual USD1 funds located at account address Z

### Account/wallet requirements

Only funds at a specific address may be insured.
Insurable accounts

* Externally owned account (EOA)
* Gnosis Safe multisig smart contract

### Depeg event

The depeg definition is based on data provided by the [Chainlink price feed](https://docs.chain.link/docs/data-feeds/price-feeds/) for stable coin USD1.
See [Contract addresses](https://docs.chain.link/docs/data-feeds/price-feeds/addresses/?network=ethereum) for available price feeds.

The following definition for a deterministic definition of a depeg event may be used.

* A depeg event candidate is created when the USD1 price data falls below a trigger threshold.

* When the USD1 price data recovers at or above a recovery threshold within 24h the depeg event candidate is considered a false alarm and no claims/payouts are created.

* When the USD1 price data does not recover at or above the recovery threshold within 24 hours the depeg event candidate becomes an actual depeg event.

* For the loss calculation the price data 24h after the initial depeg trigger is used.

An inherent risk with the above definition is its Chainlink price feed dependency. 

Chainlink price feeds come with a so called 'Heartbeat' which indicates the maximum time between consecutive price updates even when the price does not change enough to trigger a price update.

As in the case of any off-chain dependency there is a risk that systems do not behave as intended in extraordinary circumstances.

For such cases we are considering the addition of a manual trigger for depeg events.

Such a trigger might only be used when a predefined set of conditions occur.
For the usage of a manual trigger a number of restrictions will apply.
* The latest price update from the chainlink feed is long overdue
* Price data is broken, publically acknowledged by Chainlink
* Calling is restricted to accounts whitelisted by the product owner

### Loss calculation

For the loss calculation the following points are considered.

* The loss is assesed by the %-loss of the USD1 exchange rate against the fiat currency USD. 
* The sum insured might be reduced to the actual balance of the insured account at the time of the loss event
* The loss amount is calulated by the %-loss at the depeg claim event times the sum insured.

### Payout handling

Payouts are made in an alternative stable coin USD2.

* The payout amount calculation is ensured by product management
* Actual payout execution may be triggered by the policy holder
* For a payout a fixed exchange rate 
between the payout stable coin USD2 and the fiat USD of 1.0 is used. 


## Risk Capital Considerations

### Where does the risk capital come from?

The risk capital in USD2 to cover the depeg policies comes from risk investors.
Participation makes sense for risk investors with the following believe system

* Depeg risk of USD1 over the coming 3 to 6 months is neglegible
* Availability of USD2 funds
* Interest to make some income by locking USD2 funds into a riskpool

### How is the risk premium determined?

The risk investor defines the annual percentage return she/he is asking for covering the depeg risk.
This annual percentage return asked by the risk investor directly translates into policy net premium amounts.

Risk investors might want to consider the following aspects before fixing their annual percentage return for the provided risk capital.

* The more policies covered, the more return (net premiums - claim payouts)
* The higher the policy premiums, the more return
* Setting the annual percentage return very high will likely lead to very few covered policies
* Setting the annual percentage return very low will likely lead to many covered policies with a low total net premium
* Finding the sweet spot for the annual percentage return will lead to the highest return on the risk capital.

### How to invest risk capital for the depeg insurance

Investing risk captial can be achieved by providing risk captial to the depeg risk pool.

* Risk investors need to fix their risk parameters (e.g. annual percentage return) and provide risk capital to the risk pool in stable coin USD2.
* When investing in the risk pool the risk investor gets a risk bundle NFT that represents the invested USD2 capital.
* Once the risk bundle is created the risk capital needs to be unlocked by staking DIP token against the bundle.
* Only risk capital that is unlocked by DIP staking may be available to cover depeg policies and collect potential return on the risk capital.
