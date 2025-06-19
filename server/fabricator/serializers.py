from dj_rest_auth.registration.serializers import RegisterSerializer
from rest_framework import serializers
import json

# models
from fabricator.models import Fabricator


class FabricatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fabricator
        fields = "__all__"
        read_only_fields = ("status",)
