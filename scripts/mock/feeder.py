import logging
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

# price feed states
STABLE = 'stable'
TRIGGERED = 'triggered'
DEPEGGED = 'depegged'
STATES = [STABLE, TRIGGERED, DEPEGGED]

# scheduler
PRIORITY = 1
INTERVAL = 5 # seconds to wait for new data

# the api server
app = FastAPI()

# pricefeed stuff
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

    if new_state not in STATES:
        raise HTTPException(
            status_code=404, 
            detail="state {} invalid. valid states: {}".format(
                new_state, ','.join(STATES)
            ))

    old_state = state
    state = new_state;

    return {
        'old_state': old_state,
        'new_state': new_state
        }


def execute_event():
    logging.info('rounds <<{}>>'.format(rounds))


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
