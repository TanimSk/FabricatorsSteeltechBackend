from django.conf import settings
from django.db import models
import uuid


class MarketingRepresentative(models.Model):
    """
    Model representing a Marketing Representative.
    """

    marketing_rep = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="fabricator",
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=512)
    phone_number = models.CharField(max_length=20)
    district = models.CharField(max_length=255)
    sub_district = models.CharField(max_length=255)

    def __str__(self):
        return self.name
