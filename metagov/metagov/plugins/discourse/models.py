import logging

from metagov.core.plugin_models import webhook_listener

logger = logging.getLogger('django')


@webhook_listener("discourse", "listen to events on discourse")
def process_webhook(request):
    instance = request.headers.get('X-Discourse-Instance')
    event_id = request.headers.get('X-Discourse-Event-Id')
    event_type = request.headers.get('X-Discourse-Event-Type')
    event = request.headers.get('X-Discourse-Event')
    logger.info(f"Received event {event} from {instance}")
    # create event, notify core
