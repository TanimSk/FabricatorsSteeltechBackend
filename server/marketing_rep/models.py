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
        related_name="marketingrepresentative",
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=512)
    phone_number = models.CharField(max_length=20)
    district = models.CharField(max_length=255)
    sub_district = models.CharField(max_length=255)
    email = models.EmailField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Reports(models.Model):
    """
    Model representing a report submitted by a Marketing Representative.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    marketing_rep = models.ForeignKey(
        MarketingRepresentative,
        on_delete=models.CASCADE,
        related_name="reports",
    )
    fabricator = models.ForeignKey(
        "fabricator.Fabricator",
        on_delete=models.CASCADE,
        related_name="reports",
    )
    distributor = models.ForeignKey(
        "distributor.Distributor",
        on_delete=models.CASCADE,
        related_name="reports",
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    invoice_number = models.CharField(max_length=255, unique=True)
    sales_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    attachements_urls = models.JSONField(
        default=list,
        blank=True,
    )

    def __str__(self):
        return self.title


class Task(models.Model):
    """
    Model representing a task assigned to a Marketing Representative.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    marketing_rep = models.ForeignKey(
        MarketingRepresentative,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    description = models.CharField(max_length=512)
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )

    def __str__(self):
        return self.title


class RecentActivity(models.Model):
    """
    Model representing recent activity of a Marketing Representative.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    marketing_rep = models.ForeignKey(
        MarketingRepresentative,
        on_delete=models.CASCADE,
        related_name="recent_activities",
    )
    description = models.CharField(max_length=512)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.activity_type} by {self.marketing_rep.name}"
