import logging
import traceback

from celery import shared_task
from metagov.core.models import ProcessStatus
from metagov.core.plugin_decorators import plugin_registry

logger = logging.getLogger(__name__)


@shared_task
def execute_plugin_tasks():
    # invoke all the plugin tasks (listeners)
    for (plugin_name, cls) in plugin_registry.items():
        if cls._task_function:
            active_plugins = cls.objects.all()
            if active_plugins.count() > 0:
                logger.debug(f"Calling task function for {active_plugins.count()} instances of {plugin_name}")
            for plugin in active_plugins:
                task_function = getattr(plugin, cls._task_function)
                task_function()

        # invoke all the governance process pending task checkers
        for (process_name, process_cls) in cls._process_registry.items():
            active_processes = process_cls.objects.filter(status=ProcessStatus.PENDING.value)
            if active_processes.count() > 0:
                logger.debug(f"Calling update function for {active_processes.count()} pending {process_name} processes")
            for process in active_processes:
                # Invoke `update`. It may lead to the outcome or status being changed,
                # which will send a callback notification to the Driver from the `pre_save signal`
                try:
                    process.update()
                except Exception as e:
                    logger.error("Error updating process!")
                    logger.error(traceback.format_exc())
