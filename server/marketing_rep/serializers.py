from dj_rest_auth.registration.serializers import RegisterSerializer
from rest_framework import serializers
import json

# models
from marketing_rep.models import MarketingRepresentative


class MarketingRepresentativeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketingRepresentative
        fields = "__all__"
        read_only_fields = (
            "id",
            "created_at",
            "marketing_rep",
        )

    def get_fields(self):
        fields = super().get_fields()
        if self.instance:  # Update case
            fields["email"].read_only = True
        return fields
