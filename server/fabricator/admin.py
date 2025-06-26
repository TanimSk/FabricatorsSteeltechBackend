from django.contrib import admin
from .models import Fabricator

@admin.register(Fabricator)
class FabricatorAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'name', 'institution', 'phone_number', 'registration_number',
        'district', 'sub_district', 'status', 'created_at'
    )
    search_fields = ('name', 'institution', 'phone_number', 'registration_number')
    list_filter = ('status', 'district', 'sub_district')
    ordering = ('-created_at',)

# Register your models here.
