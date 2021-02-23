import tweepy, logging
from app import core
from .parser import Parser
from .metadata import Metadata

logger = logging.getLogger(__name__)

def run():
    # core.db.drop_tables() # clears database

    meta = Metadata(core.db)
    parser = Parser(core.db, core.api)

    last_status_parsed = meta.retrieve('last_status_parsed')

    new_statuses = []

    logger.info(f'Update started at status #{last_status_parsed}')

    # collects new statuses in reverse chronological order
    for status in tweepy.Cursor(
        core.api.mentions_timeline, 
        tweet_mode="extended", # needed to get full text for longer tweets
        since_id=last_status_parsed, # won't iterate through tweets already in database
        count=200
    ).items():
        new_statuses.append(status)

    logger.info('Fetched {} new statuses'.format(len(new_statuses)))

    # iterates through statuses in chronological order
    for status in reversed(new_statuses):
        try:
            parser.parse(status)
        except tweepy.error.TweepError:
            logger.warn('Duplicate tweet')

        # updates last status id -> next mentions timeline won't see already parsed tweets
        if status.id > last_status_parsed:
            meta.update('last_status_parsed', status.id)
