from dj_rest_auth.registration.serializers import RegisterSerializer
from rest_framework import serializers
import json

# serializers
from rest_framework.views import exception_handler

# models
from marketing_rep.models import MarketingRepresentative
from fabricator.models import Fabricator


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        if isinstance(response.data, dict):
            # Extract error messages from dict
            plain_errors = []
            for field, messages in response.data.items():
                if isinstance(messages, list):
                    for message in messages:
                        plain_errors.append(f"({field}) {message}")
                else:
                    plain_errors.append(f"({field}) {messages}")
            message = "\n".join(plain_errors)
        elif isinstance(response.data, list):
            # If it's a list, join messages
            message = "\n".join(str(msg) for msg in response.data)
        else:
            # Fallback for any other format (e.g., string)
            message = str(response.data)

        response.data = {"success": False, "message": message}

    return response


class CustomPasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password1 = serializers.CharField(required=True)
    new_password2 = serializers.CharField(required=True)

    def validate(self, data):
        # Check if the new passwords match
        if data["new_password1"] != data["new_password2"]:
            raise serializers.ValidationError("The two new passwords must match.")
        return data

    def validate_old_password(self, value):
        # Validate the old password against the current password
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value


class MarketingRepAndFabricatorSerializer(serializers.ModelSerializer):
    marketing_rep_name = serializers.CharField(source="marketing_representative.name")
    marketing_rep_phone_number = serializers.CharField(
        source="marketing_representative.phone_number"
    )
    employee_id = serializers.CharField(source="marketing_representative.employee_id")
    email = serializers.EmailField(source="marketing_representative.email")
    district = serializers.CharField(source="marketing_representative.district")
    sub_district = serializers.CharField(source="marketing_representative.sub_district")

    class Meta:
        model = Fabricator
        fields = "__all__"
