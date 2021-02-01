from django.db import models
from metagov.core.plugin_models import GovernanceProcessProvider, GovernanceProcessStatus
from django.db.models.signals import post_save
from django.dispatch import receiver
import logging
import json

logger = logging.getLogger('django')


class DataStore(models.Model):
    data_store = models.TextField()

    def _get_data_store(self):
        if self.data_store != '':
            return json.loads(self.data_store)
        else:
            return {}

    def _set_data_store(self, obj):
        self.data_store = json.dumps(obj)
        self.save()

    def get(self, key):
        obj = self._get_data_store()
        return obj.get(key, None)

    def set(self, key, value):
        obj = self._get_data_store()
        obj[key] = value
        self._set_data_store(obj)
        return True

    def remove(self, key):
        obj = self._get_data_store()
        res = obj.pop(key, None)
        self._set_data_store(obj)
        if not res:
            return False
        return True


class GovernanceProcess(models.Model):
    plugin_name = models.CharField(max_length=30)
    status = models.CharField(
        max_length=10,
        default=GovernanceProcessStatus.CREATED,
    )
    job_state = models.OneToOneField(
        DataStore,
        on_delete=models.CASCADE,
        verbose_name='job state',
        null=True,
        related_name='state_of',
    )

    # FIXME make nicer https://docs.djangoproject.com/en/3.1/ref/models/instances/
    # only needs the one selected plugin
    plugins = GovernanceProcessProvider.plugins

    def save(self, *args, **kwargs):
        # the first time it is saved, create empty job state
        if not self.pk:
            self.job_state = DataStore.objects.create()
        super(GovernanceProcess, self).save(*args, **kwargs)

    def start(self, querydict):
        PluginClass = self.plugins.get(self.plugin_name)
        result = PluginClass.start(self.job_state, querydict)
        return Result(self.pk, self.status, result)

    def cancel(self):
        """cancel governance process"""
        pass

    def close(self):
        """close governance process, return outcome"""
        return None

    def __str__(self):
        return self.plugin_name

    def handle_webhook(self, querydict):
        """process webhook, possibly updating state"""
        PluginClass = self.plugins.get(self.plugin_name)
        PluginClass.handle_webhook(self.job_state, querydict)

class Result(object):
    def __init__(self, instance_id, status, data):
        self.instance_id = instance_id
        self.status = status.name
        self.data = data

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__ if hasattr(o, '__dict__') else str(o),
                          sort_keys=True)


@receiver(post_save, sender=DataStore, dispatch_uid="update_job_status")
def update_status(sender, instance, **kwargs):
    """Update GovernanceProcess status after its job state is saved"""
    model = GovernanceProcess.objects.filter(job_state=instance).first()
    if model is not None:
        PluginClass = model.plugins.get(model.plugin_name)
        old_status = model.status
        new_status = PluginClass.get_status(instance)
        if new_status is not old_status:
            model.status = new_status
            model.save()
        if new_status is GovernanceProcessStatus.COMPLETED:
            outcome = PluginClass.get_outcome(model.job_state)
            result = Result(model.pk, new_status, outcome)
            logger.info(result.toJSON())
            # TODO notify Driver
