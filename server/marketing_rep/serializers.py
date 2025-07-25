from dj_rest_auth.registration.serializers import RegisterSerializer
from rest_framework import serializers
import json

# models
from marketing_rep.models import MarketingRepresentative, Reports, RecentActivity, Task
from fabricator.models import Fabricator


class MarketingRepresentativeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketingRepresentative
        exclude = ("marketing_rep", "password_txt")
        read_only_fields = (
            "id",
            "created_at",
        )

    def get_fields(self):
        fields = super().get_fields()
        if self.instance:  # Update case
            fields["email"].read_only = True
        return fields


class ReportsSerializer(serializers.ModelSerializer):
    # marketing representative
    marketing_rep_name = serializers.CharField(
        source="marketing_rep.name", read_only=True
    )
    marketing_rep_phone_number = serializers.CharField(
        source="marketing_rep.phone_number", read_only=True
    )
    marketing_rep_district = serializers.CharField(
        source="marketing_rep.district", read_only=True
    )
    marketing_rep_sub_district = serializers.CharField(
        source="marketing_rep.sub_district", read_only=True
    )

    # fabricator
    fabricator_name = serializers.CharField(source="fabricator.name", read_only=True)
    fabricator_institution = serializers.CharField(
        source="fabricator.institution", read_only=True
    )
    fabricator_registration_number = serializers.CharField(
        source="fabricator.registration_number", read_only=True
    )
    fabricator_phone_number = serializers.CharField(
        source="fabricator.phone_number", read_only=True
    )
    fabricator_district = serializers.CharField(
        source="fabricator.district", read_only=True
    )
    fabricator_sub_district = serializers.CharField(
        source="fabricator.sub_district", read_only=True
    )

    # distributor
    distributor_name = serializers.CharField(source="distributor.name", read_only=True)
    distributor_phone_number = serializers.CharField(
        source="distributor.phone_number", read_only=True
    )
    distributor_district = serializers.CharField(
        source="distributor.district", read_only=True
    )
    distributor_sub_district = serializers.CharField(
        source="distributor.sub_district", read_only=True
    )

    class Meta:
        model = Reports
        fields = "__all__"
        read_only_fields = ("marketing_rep",)

    def __init__(self, *args, **kwargs):
        # Accept an optional context variable to exclude `promo_code`
        hidden_keys = kwargs.pop("hide_fields", False)
        super().__init__(*args, **kwargs)

        if hidden_keys:
            for key in hidden_keys:
                if key in self.fields:
                    self.fields.pop(key, None)


class RecentActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = RecentActivity
        fields = "__all__"


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = "__all__"


class MarketingRepresentativeRegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketingRepresentative
        exclude = ("marketing_rep", "password_txt")

    