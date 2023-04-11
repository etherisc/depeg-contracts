import sched
import time

from threading import Thread

from loguru import logger

from fastapi import HTTPException
from fastapi.routing import APIRouter

from server.settings import (
    Settings,
    settings
)

from server.jobs import (
    queue,
    Job
)

from server.product import process_latest_price

# setup for router
router = APIRouter(prefix='/v1')

# scheduler
PRIORITY = 1
INTERVAL = 5 # seconds to wait for new data

# domain specific setup

# setup scheduling
schedule = sched.scheduler(time.time, time.sleep)
next_event = None
events = 0


@router.on_event('startup')
async def startup_event():
    logger.info('starting scheduler')
    thread = Thread(target = start_scheduler)
    thread.start()


@router.on_event("shutdown")
def shutdown_event():
    global schedule

    logger.info('stopping scheduler')
    if schedule and next_event:
        schedule.cancel(next_event)

    logger.info('scheduler stopped')


def start_scheduler():
    global next_event

    queue.add(Job(name='checker', method_to_run=process_latest_price, interval=settings.checker_interval))

    next_event = schedule.enter(settings.scheduler_interval, PRIORITY, schedule_event, (schedule,))
    logger.info('scheduler started')
    schedule.run()


def schedule_event(s):
    global events
    global next_event

    events += 1
    queue.execute()
    next_event = schedule.enter(settings.scheduler_interval, PRIORITY, schedule_event, (s,))
