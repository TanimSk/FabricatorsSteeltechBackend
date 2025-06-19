from dj_rest_auth.registration.serializers import RegisterSerializer
from rest_framework import serializers

# models
from distributor.models import Distributor


class DistributorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Distributor
        fields = "__all__"
