from typing import (
    Callable,
    Optional
)

from loguru import logger
from pydantic import BaseModel

from server.util import get_unix_time

# default time between executions: 1h
JOB_INTERVAL_DEFAULT = 3600
JOB_FIRST_ID = 1000

job_id = JOB_FIRST_ID


class Job(BaseModel):

    id:Optional[int] = None
    name:Optional[str] = None
    method_to_run:Callable = None
    next_execution:Optional[int] = None
    interval:int = JOB_INTERVAL_DEFAULT


    def __init__(self, *args, **kwargs):
        global job_id

        super().__init__(*args, **kwargs)
        self.id = job_id
        job_id += 1

        if not self.next_execution:
            self.next_execution = get_unix_time()


    def __hash__(self):
        return hash(self.id)


    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.id == other.id
        else:
            return False


    def __ne__(self, other):
        return not self.__eq__(other)


    def __str__(self):
        return '{} ({})'.format(self.id, self.name)


    def execute(self):
        if self.method_to_run:
            logger.info('executîng job {}'.format(self))
            self.method_to_run()
        else:
            logger.warning('execute job {}: method missing'.format(self))


class Queue(BaseModel):

    queue:set[Job] = set()


    def add(self, job):
        self.queue.add(job)
        logger.info('added job {} to queue. jobs in queue: {}'.format(
            job, len(self.queue)))


    def remove(self, job):
        self.queue.remove(job)
        logger.info('removed job {} from queue. jobs in queue: {}'.format(
            job, len(self.queue)))


    def execute(self):
        logger.debug('checking for scheduled jobs. jobs in queue: {}'.format(len(self.queue)))
        now = get_unix_time()

        for job in self.queue:
            if job.next_execution < now:
                job.execute()

                if job.interval > 0:
                    job.next_execution += job.interval
                    logger.debug('re-scheduled job {} at {}'.format(job, job.next_execution))
                else:
                    self.remove(job)


queue = Queue()