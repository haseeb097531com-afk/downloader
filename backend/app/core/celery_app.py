from celery import Celery
from app.core.config import settings
from app.services.processor.resource_guard import ResourceGuard

celery_app = Celery(
    "mediavault_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.scrape_tasks",
        "app.workers.download_tasks",
        "app.workers.processor_tasks",
        "app.workers.monitor_tasks",
        "app.workers.maintenance_tasks",
    ]
)

# Concurrency auto-tune: base recommendation from CPU/RAM, doubled in turbo mode.
_base_concurrency = ResourceGuard.get_recommended_concurrency()
if getattr(settings, "TURBO_MODE", False):
    _base_concurrency = max(1, _base_concurrency * 2)

celery_app.conf.worker_concurrency = _base_concurrency

celery_app.conf.task_routes = {
    "app.workers.*": "main-queue",
}

celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.timezone = "UTC"
celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.beat_schedule = {
    "system-monitor-every-30s": {
        "task": "app.workers.monitor_tasks.system_monitor_task",
        "schedule": 30.0,
    },
    "network-speed-test-every-15m": {
        "task": "app.workers.monitor_tasks.network_speed_test_task",
        "schedule": 900.0,
    },
}