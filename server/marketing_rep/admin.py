from django.contrib import admin
from .models import Reports, MarketingRepresentative


admin.site.register(Reports)

@admin.register(MarketingRepresentative)
class MarketingRepresentativeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "phone_number",
        "email",
        "district",
        "sub_district",
        "created_at",
    )
    search_fields = ("name", "phone_number", "email", "district", "sub_district")
    list_filter = ("district", "sub_district")
    ordering = ("-created_at",)
    list_per_page = 100