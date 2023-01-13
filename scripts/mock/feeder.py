import logging
import sched
import time

from threading import Thread
from fastapi import FastAPI

# usage
# 1. open new terminal
# 2. start uvicorn server
# 3. switch back to original terminal
# 4. test api servier with curl
# reg 2: uvicorn scripts.mock.feeder:app --reload
# reg 4: curl localhost:8000/

PRIORITY = 1
INTERVAL = 5 # seconds to wait for new data

# the api server
app = FastAPI()

# scheduling stuff
schedule = sched.scheduler(time.time, time.sleep)
next_event = None
events = 0


@app.get('/')
async def root():
    return {
        'message': 'hello world!'
        }


def execute_event():
    logging.info('events <<{}>>'.format(events))


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
    if schedule and next_event:
        schedule.cancel(next_event)

    logging.info('scheduler stopped')


def start_scheduler():
    global next_event

    next_event = schedule.enter(INTERVAL, PRIORITY, schedule_event, (schedule,))
    logging.info('scheduler started')
    schedule.run()


def schedule_event(s):
    global events
    global next_event

    events += 1
    execute_event()
    next_event = schedule.enter(INTERVAL, PRIORITY, schedule_event, (s,))
