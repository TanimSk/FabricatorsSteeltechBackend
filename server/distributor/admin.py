from django.contrib import admin
from distributor.models import Distributor

@admin.register(Distributor)
class DistributorAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'district', 'created_at')
    search_fields = ('name', 'email', 'phone')    
