import django.dispatch

governance_process_updated = django.dispatch.Signal(providing_args=["instance", "status", "outcome", "errors"])
platform_event_created = django.dispatch.Signal(providing_args=["instance", "event_type", "data", "initiator", "timestamp"])
