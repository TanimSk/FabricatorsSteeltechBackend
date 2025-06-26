from django.db import models
import uuid

# Create your models here.
class Distributor(models.Model):
    """
    Model representing a Distributor.
    """
    marketing_representative = models.ForeignKey(
        "marketing_rep.MarketingRepresentative",
        on_delete=models.DO_NOTHING,
        related_name="distributors",
        blank=True,
        null=True,
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=512)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(max_length=255, unique=True)
    district = models.CharField(max_length=255)
    sub_district = models.CharField(max_length=255)    
    created_at = models.DateTimeField(auto_now_add=True)    