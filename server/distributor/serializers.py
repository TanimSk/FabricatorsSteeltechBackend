from dj_rest_auth.registration.serializers import RegisterSerializer
from rest_framework import serializers

# models
from distributor.models import Distributor
from marketing_rep.serializers import MarketingRepresentativeSerializer


class DistributorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Distributor
        fields = "__all__"


class SingleDistributorSerializer(serializers.ModelSerializer):
    marketing_representative = MarketingRepresentativeSerializer(read_only=True)

    class Meta:
        model = Distributor
        fields = "__all__"
        read_only_fields = (
            "id",
            "created_at",            
        )
