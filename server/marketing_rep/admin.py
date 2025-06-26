from django.contrib import admin
from .models import Reports


@admin.register(Reports)
class ReportsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "marketing_rep",
        "fabricator",
        "distributor",
        "amount",
        "invoice_number",
        "sales_date",
        "created_at",
    )
