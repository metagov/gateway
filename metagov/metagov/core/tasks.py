import logging

from celery import shared_task
from metagov.core.models import Community, GovernanceProcess, Plugin, ProcessStatus
from metagov.core.plugin_decorators import plugin_registry
from metagov.core.views import get_proxy

logger = logging.getLogger(__name__)


@shared_task
def execute_plugin_tasks():
    logger.info("execute_plugin_tasks")
    # invoke all the plugin tasks (listeners)
    for (plugin_name, cls) in plugin_registry.items():
        if cls._task_function:
            active_plugins = cls.objects.all()
            logger.info(f"Calling task function for {active_plugins.count()} instances of {plugin_name}")

        # invoke all the governance process pending task checkers
        for (process_name, process_cls) in cls._process_registry.items():
            active_processes = process_cls.objects.filter(status=ProcessStatus.PENDING.value)
            if active_processes.count():
                logger.info(f"{plugin_name}.{process_name} {active_processes.count()} pending processes")

            for process in active_processes:
                logger.info(f"Checking: {process}")
                outcome_prev = process.outcome
                status_prev = process.status

                process.plugin = get_proxy(process.plugin)
                process.update()

                if status_prev != process.status:
                    logger.info(f"Status updated: {status_prev} -> {process.status}")
                if outcome_prev != process.outcome:
                    logger.info(f"Outcome updated: {outcome_prev} -> {process.outcome}")
