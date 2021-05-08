import logging

from celery import shared_task
from metagov.core.models import Community, GovernanceProcess, Plugin, ProcessStatus
from metagov.core.plugin_decorators import plugin_registry
from metagov.core.views import get_proxy

logger = logging.getLogger(__name__)


@shared_task
def execute_plugin_tasks():
    # invoke all the plugin tasks (listeners)
    for (plugin_name, cls) in plugin_registry.items():
        if cls._task_function:
            active_plugins = cls.objects.all()
            logger.debug(f"[tasks] calling task function for {active_plugins.count()} instances of {plugin_name}")

        # invoke all the governance process pending task checkers
        for (process_name, process_cls) in cls._process_registry.items():
            active_processes = process_cls.objects.filter(status=ProcessStatus.PENDING.value)
            for process in active_processes:
                logger.debug(f"[tasks] updating process: '{process}'")

                # hack so process has access to parent proxy instance
                process.plugin = get_proxy(process.plugin)

                # Invoke `update`. It may lead to the outcome or status being changed,
                # which will send a callback notification to the Driver from the `pre_save signal`
                process.update()
