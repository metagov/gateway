from django.db import IntegrityError, models
from metaov.core.models import Community


class Driver(models.Model):
    readable_name = models.CharField(max_length=100, blank=True, help_text="Human-readable name for the driver")
    slug = models.SlugField(
        max_length=36, default=uuid.uuid4, unique=True, help_text="Unique slug identifier for the driver"
    )
    webhooks = models.ArrayField(models.CharField(max_length=200, blank=True))


class APIKey(models.Model):
    key = models.SlugField(
        max_length=36, default=uuid.uuid4, unique=True, help_text="API Key for the driver"
    )
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name="api_keys")


class CommunityDriverLink(models.model):
    driver = models.ForeignKey(to=Driver, on_delete=models.CASCADE)
    community = models.OneToOneField(to=Community, on_delete=models.CASCADE)


class DriverConfig(models.model):
    driver = models.ForeignKey(to=Driver, on_delete=models.CASCADE)
    config_name = models.CharField(max_length=100)
    config_value = models.CharField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["driver", "config_name"], name="unique_driver_config")]
