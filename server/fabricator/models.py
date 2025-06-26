from django.db import models
import uuid
from datetime import date
import random


class Fabricator(models.Model):
    """
    Model representing a Fabricator.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=512)
    institution = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20)
    registration_number = models.CharField(max_length=255, blank=True, null=True)
    district = models.CharField(max_length=255)
    sub_district = models.CharField(max_length=255)
    address = models.CharField(max_length=512, blank=True, null=True)
    email = models.EmailField(max_length=255, blank=True, null=True)
    distributor = models.ForeignKey(
        "distributor.Distributor",
        on_delete=models.DO_NOTHING,
        related_name="fabricators",
    )
    marketing_representative = models.ForeignKey(
        "marketing_rep.MarketingRepresentative",
        on_delete=models.DO_NOTHING,
        related_name="fabricators",
        blank=True,
        null=True,
    )
    trade_license_img_url = models.URLField(
        max_length=512,
    )
    visiting_card_img_url = models.URLField(
        max_length=512,
    )
    profile_img_url = models.URLField(
        max_length=512,
    )
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    # create a unique registration number
    def save(self, *args, **kwargs):
        if not self.registration_number:
            self.registration_number = f"HOS-{str(date.today().year)[-1:]}{random.randint(0, 9)}-{str(Fabricator.objects.count() + 1).zfill(4)}"
        super().save(*args, **kwargs)
