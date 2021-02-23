from app.database import update
import sched, time, datetime
import logging, traceback

logger = logging.getLogger('app.scheduler')

s = sched.scheduler(time.time, time.sleep)

def scheduled_update(sc):
    s.enter(60, 1, scheduled_update, (sc,))
    before = time.time()
    
    try:
        update.run()
    except Exception as e:
        logger.warn(traceback.format_exc())

    logger.info('Update completed in {0:.3f} seconds!'.format(time.time() - before))

s.enter(0, 1, scheduled_update, (s,))
s.run()