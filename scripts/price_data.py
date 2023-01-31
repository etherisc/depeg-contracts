import random

from datetime import datetime

from brownie import chain

# product state
STATE_PRODUCT = {
    'Undefined': 0,
    'Active': 1,
    'Paused': 2,
    'Depegged': 3,
}

# price feeder event type and states
EVENT_TYPE = {
    'Undefined':0,
    'Update': 1,
    'TriggerEvent': 2,
    'RecoveryEvent': 3,
    'DepegEvent': 4,
}

STATE_COMPLIANCE = {
    'Undefined': 0,
    'Initializing': 1,
    'Valid': 2,
    'FailedOnce': 3,
    'FailedMultipleTimes': 4,
}

STATE_STABILITY = {
    'Undefined': 0,
    'Initializing': 1,
    'Stable': 2,
    'Triggered': 3,
    'Depegged': 4,
}

# actual chainlink aggregator data, may be validated against
# https://etherscan.io/address/0x8fFfFfd4AfB6115b954Bd326cbe7B4BA576818f6#readContract
USDC_CHAINLINK_DATA = [
    # roundId             qnswer    startedAt  updatedAt  answeredInRound
    '36893488147419103822 100000017 1660297306 1660297306 36893488147419103822',
    '36893488147419103823 100008784 1660383738 1660383738 36893488147419103823',
    '36893488147419103824 100000000 1660383820 1660383820 36893488147419103824',
    '36893488147419103825 99985387 1660470242 1660470242 36893488147419103825',
    '36893488147419103826 99989424 1660556656 1660556656 36893488147419103826',
    '36893488147419103827 100017933 1660643065 1660643065 36893488147419103827',
    '36893488147419103828 100007204 1660729494 1660729494 36893488147419103828',
    '36893488147419103829 100000000 1660815929 1660815929 36893488147419103829',
    '36893488147419103830 100002388 1660902349 1660902349 36893488147419103830',
    '36893488147419103831 100000554 1660988749 1660988749 36893488147419103831',
    '36893488147419103832 99990785 1661075158 1661075158 36893488147419103832',
]

# get same price feed response as before
USDC_CHAINLINK_DATA_PRICE_SEQUENCE_REPEAT = [
    # roundId             qnswer    startedAt  updatedAt  answeredInRound
    '36893488147419103822 100000017 1660297306 1660297306 36893488147419103822',
    '36893488147419103822 100000017 1660297306 1660297306 36893488147419103822',
]

# miss/skip element in sequence of price feed responses
USDC_CHAINLINK_DATA_PRICE_SEQUENCE_SKIP = [
    # roundId             qnswer    startedAt  updatedAt  answeredInRound
    '36893488147419103822 100000017 1660297306 1660297306 36893488147419103822',
    '36893488147419103824 100008784 1660383738 1660383738 36893488147419103824',
]

# decrease element in sequence of price feed responses
USDC_CHAINLINK_DATA_PRICE_DECREASE = [
    # roundId             qnswer    startedAt  updatedAt  answeredInRound
    '36893488147419103822 100000017 1660297306 1660297306 36893488147419103822',
    '36893488147419103821 100008784 1660383738 1660383738 36893488147419103821',
]

# for usdc/usd quality promise by chainlink see https://docs.chain.link/data-feeds/price-feeds/addresses
# 'hacked' price feed to force heatbeat violation
# ie duration between consecuteve createdAt/updatedAt timestamps > 24h + margin
USDC_CHAINLINK_DATA_HEARTBEAT_VIOLATED = [
    '36893488147419103822 100000017 1660297306 1660297306 36893488147419103822',
    '36893488147419103823 100008784 1660383807 1660383807 36893488147419103823',
    '36893488147419103824 100000000 1660470308 1660470308 36893488147419103824',
    '36893488147419103825 99985387 1660506308 1660506308 36893488147419103825',
]

# 'hacked' price feed to force deviation violation
# ie price difference between two rounds larger than 0.25%
USDC_CHAINLINK_DATA_DEVIATION_VIOLATED = [
    '36893488147419103822 100000017 1660297306 1660297306 36893488147419103822',
    '36893488147419103823 100260000 1660383738 1660383738 36893488147419103823',
    '36893488147419103824 100000000 1660383820 1660383820 36893488147419103824',
    '36893488147419103825 99985387 1660470242 1660470242 36893488147419103825',
]

# i createdAt  answer    comment
# 0 1660070000 100000017 normal
# 1 1660080000  99700000 below recovery but above trigger
# 2 1660090000  99500001 1 above trigger
# 3 1660100000  99500000 at trigger
# 4 1660120000  99800000 above trigger but below recovery
# 5 1660140000  98000000 really below trigger
# 6 1660160000  99899999 1 below recovery
# 7 1660186401  99900000 at recovery
# 8 1660200000  99700000 below recovery and above trigger
USDC_CHAINLINK_DATA_TRIGGER_AND_RECOVER = [
    # roundId             qnswer    startedAt  updatedAt  answeredInRound
    '36893488147419103822 100000017 1660070000 1660070000 36893488147419103822',
    '36893488147419103823 99700000 1660080000 1660080000 36893488147419103823',
    '36893488147419103824 99500001 1660090000 1660090000 36893488147419103824',
    '36893488147419103825 99500000 1660100000 1660100000 36893488147419103825',
    '36893488147419103826 99800000 1660120000 1660120000 36893488147419103826',
    '36893488147419103827 98000000 1660140000 1660140000 36893488147419103827',
    '36893488147419103828 99899999 1660160000 1660160000 36893488147419103828',
    '36893488147419103829 99900000 1660186400 1660186400 36893488147419103829',
    '36893488147419103830 99700000 1660200000 1660200000 36893488147419103830',
]

# same as USDC_CHAINLINK_DATA_TRIGGER_AND_RECOVER just with streched timeline
# to ensure recovery takes longer than 24h
USDC_CHAINLINK_DATA_TRIGGER_AND_DEPEG = [
    # roundId             qnswer    startedAt  updatedAt  answeredInRound
    '36893488147419103822 100000017 1660070000 1660070000 36893488147419103822',
    '36893488147419103823 99700000 1660080000 1660080000 36893488147419103823',
    '36893488147419103824 99500001 1660090000 1660090000 36893488147419103824',
    '36893488147419103825 99500000 1660100000 1660100000 36893488147419103825',
    '36893488147419103826 99800000 1660120000 1660120000 36893488147419103826',
    '36893488147419103827 98000000 1660140000 1660140000 36893488147419103827',
    '36893488147419103828 99899999 1660160000 1660160000 36893488147419103828',
    '36893488147419103829 99900000 1660186401 1660186401 36893488147419103829',
    '36893488147419103830 99700000 1660200000 1660200000 36893488147419103830',
    '36893488147419103831 99990000 1660210000 1660210000 36893488147419103831',
]

ROUND_ID_INITIAL = 36893488147419103822

PERFECT_PRICE = 10 ** 8 # == 10 ** chainlink_usdc_pricefeed.decimals()
TRIGGER_PRICE = int(0.995 * PERFECT_PRICE)
RECOVERY_PRICE = int(0.999 * PERFECT_PRICE)


def generate_next_data(
    i,
    price=None,
    last_update=None,
    delta_time=None
):
    round_id = ROUND_ID_INITIAL + i
    now = datetime.now()
    timestamp = int(datetime.timestamp(now))

    if price is None:
        price = PERFECT_PRICE + random.randint(-10, 10)

    if last_update is None:
        last_update = timestamp if i == 0 else timestamp + (i - 1) * 24 * 3600
    
    if delta_time is None:
        delta_time = 24 * 3600 + random.randint(-120, 120)

    startedAt = last_update if i == 0 else last_update + delta_time
    
    data = '{} {} {} {} {}'.format(
            round_id, # roundId
            price, # answer
            startedAt, # startedAt
            startedAt, # updatedAt
            round_id # answeredInRound
    )

    print('next_data[{}] {} - {}'.format(i, data, datetime.fromtimestamp(startedAt)))

    return data


def inject_data(
    usdc_feeder,
    data,
    owner=None,
    sleep=False
):
    (
        round_id,
        answer,
        started_at,
        updated_at,
        answered_in_round
    ) = data_to_round_data(data)

    if sleep:
        sleep_time = updated_at - chain.time()
        assert sleep_time >= 0

        chain.sleep(sleep_time)
        chain.mine(1)

    if owner:
        usdc_feeder.setRoundData(
            round_id,
            answer,
            started_at,
            updated_at,
            answered_in_round,
            {'from': owner}
        )
    else:
        usdc_feeder.setRoundData(
            round_id,
            answer,
            started_at,
            updated_at,
            answered_in_round
        )


def data_to_round_data(data):
    round_data = data.split()
    round_id = int(round_data[0])
    answer = int(round_data[1])
    started_at = int(round_data[2])
    updated_at = int(round_data[3])
    answered_in_round = int(round_data[4])

    return (
        round_id,
        answer,
        started_at,
        updated_at,
        answered_in_round
    )
