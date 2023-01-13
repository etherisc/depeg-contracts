import logging
import random
import sched
import time

from threading import Thread

from fastapi import (
    FastAPI,
    HTTPException,
)

# usage
# 1. open new terminal
# 2. start uvicorn server
# 3. switch back to original terminal
# 4. test api servier with curl
# reg 2: uvicorn scripts.mock.feeder:app --reload
# reg 4: curl localhost:8000/

# getting/setting price feed state
# curl localhost:8000/state
# curl -X PUT localhost:8000/state/stable

# price feed stuff
STABLE = 'stable'
TRIGGERED = 'triggered'
DEPEGGED = 'depegged'
STATES = [STABLE, TRIGGERED, DEPEGGED]

PRICE_MAX = 1.02
PRICE_TRIGGER = 0.995
PRICE_RECOVER = 0.998
PRICE_DEPEG = 0.93
PRICE_MIN = 0.82

TRANSITIONS = {}
TRANSITIONS['stable->triggered'] = [0.999,0.998,0.997,0.996,0.995]
TRANSITIONS['triggered->stable'] = [0.996,0.997,0.998]
TRANSITIONS['triggered->depegged'] = [0.99,0.98,0.95,0.91]
TRANSITIONS['depegged->stable'] = [0.9,0.95,0.99,1.0]

# scheduler
PRIORITY = 1
INTERVAL = 5 # seconds to wait for new data

# the api server
app = FastAPI()

# pricefeed stuff
price_buffer = []
current_price = 1.0
state = STABLE

# scheduling stuff
schedule = sched.scheduler(time.time, time.sleep)
next_round = None
rounds = 0


@app.get('/')
async def root():
    return { 
        'info': 'price feed api server',
        'openapi': 'localhost:8000/docs',
        'state': state,
        }

@app.get('/state')
async def get_state():
    return {
        'state': state
        }

@app.put('/state/{new_state}')
async def set_state(new_state:str):
    global state
    global price_buffer

    if new_state not in STATES:
        raise HTTPException(
            status_code=400,
            detail="state {} invalid. valid states: {}".format(
                new_state, ','.join(STATES)
            ))

    old_state = state

    transition = '{}->{}'.format(old_state, new_state)
    if transition in TRANSITIONS:
        price_buffer += TRANSITIONS[transition]
    else:
        raise HTTPException(
            status_code=400,
            detail="state transition {}->{} invalid".format(
                old_state, new_state))

    # set new state
    state = new_state;

    return {
        'old_state': old_state,
        'new_state': new_state
        }


def next_price() -> float:
    global price_buffer

    if len(price_buffer) > 0:
        price = price_buffer[0]
        del price_buffer[0]
        return price

    if state == STABLE:
        return random.uniform(PRICE_TRIGGER, PRICE_MAX)
    elif state == TRIGGERED:
        return random.uniform(PRICE_DEPEG, PRICE_RECOVER)
    else:
        return random.uniform(PRICE_MIN, PRICE_DEPEG)


def execute_event():
    global current_price

    current_price = next_price()

    logging.info('state {} price {} rounds {}'.format(
        state,
        current_price,
        rounds))


@app.on_event('startup')
async def startup_event():
    logging.basicConfig(
        # filename='example.log',
        format='%(asctime)s %(levelname)s:%(message)s',
        encoding='utf-8', 
        level=logging.INFO)

    logging.info('starting scheduler')
    thread = Thread(target = start_scheduler)
    thread.start()


@app.on_event("shutdown")
def shutdown_event():
    global schedule

    logging.info('stopping scheduler')
    if schedule and next_round:
        schedule.cancel(next_round)

    logging.info('scheduler stopped')


def start_scheduler():
    global next_round

    next_round = schedule.enter(INTERVAL, PRIORITY, schedule_round, (schedule,))
    logging.info('scheduler started')
    schedule.run()


def schedule_round(s):
    global rounds
    global next_round

    rounds += 1
    execute_event()
    next_round = schedule.enter(INTERVAL, PRIORITY, schedule_round, (s,))
