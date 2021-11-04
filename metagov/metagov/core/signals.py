import django.dispatch
from django.db.models.signals import pre_save
from django.dispatch import receiver
from metagov.core.models import GovernanceProcess, ProcessStatus
import requests
import logging

logger = logging.getLogger(__name__)

governance_process_updated = django.dispatch.Signal()


@receiver(pre_save)
def pre_save_governance_process(sender, instance, **kwargs):
    """
    Pre-save signale for GovernanceProcesses.
    If the ``status`` was changed to ``completed``, OR if the ``outcome`` was changed,
    it will emit a custom signal that can be captured by the driver. If a callback url
    is set on the process, it will post the serialized process to the ``callback_url``."""

    # Need to check if this is a GovernanceProcess using subclass
    # instead of using `sender` because these are Proxy models.
    if not issubclass(sender, GovernanceProcess):
        return

    try:
        obj = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        pass  # process is new
    else:
        if not obj.status == instance.status and instance.status == ProcessStatus.COMPLETED.value:
            logger.debug(f"Status changed: {obj.status}->{instance.status}")
            notify_process_updated(instance)
        elif not obj.outcome == instance.outcome:
            logger.debug(f"Outcome changed: {obj.outcome} -> {instance.outcome}")
            notify_process_updated(instance)


def notify_process_updated(process: GovernanceProcess):
    """Emit custom signal that the process has changed. If callback_url is set,
    notify the Driver that this GovernanceProess has changed."""

    governance_process_updated.send(
        sender=process.__class__, status=process.status, outcome=process.outcome, errors=process.errors
    )

    if process.callback_url:
        logger.debug(f"Posting process to '{process.callback_url}':")

        from metagov.core.serializers import GovernanceProcessSerializer

        serializer = GovernanceProcessSerializer(process)
        logger.debug(serializer.data)
        resp = requests.post(process.callback_url, json=serializer.data)
        if not resp.ok:
            logger.error(f"Error posting outcome to callback url: {resp.status_code} {resp.text}")
