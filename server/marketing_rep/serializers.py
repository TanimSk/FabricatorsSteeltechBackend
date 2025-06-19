from dj_rest_auth.registration.serializers import RegisterSerializer
from rest_framework import serializers
import json

# models
from marketing_rep.models import MarketingRepresentative


class MarketingRepresentativeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketingRepresentative
        fields = "__all__"
