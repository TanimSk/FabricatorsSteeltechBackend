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


class ExpandedFabricatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fabricator
        fields = "__all__"
        read_only_fields = ("status",)
        depth = 1

    def to_representation(self, instance):
        data = super().to_representation(instance)

        # Add your custom key here
        data["assigned"] = True if instance.marketing_representative else False

        # You can also compute dynamic values:
        # data["is_active"] = instance.status == "active"

        return data
