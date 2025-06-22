from dj_rest_auth.registration.serializers import RegisterSerializer
from rest_framework import serializers
import json

# models
from marketing_rep.models import MarketingRepresentative, Reports


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


class ReportsSerializer(serializers.ModelSerializer):
    marketing_rep_name = serializers.CharField(
        source="marketing_rep.name", read_only=True
    )
    fabricator_name = serializers.CharField(source="fabricator.name", read_only=True)
    distributor_name = serializers.CharField(source="distributor.name", read_only=True)

    class Meta:
        model = Reports
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        # Accept an optional context variable to exclude `promo_code`
        hidden_keys = kwargs.pop("hide_fields", False)
        super().__init__(*args, **kwargs)

        if hidden_keys:
            for key in hidden_keys:
                if key in self.fields:
                    self.fields.pop(key, None)
