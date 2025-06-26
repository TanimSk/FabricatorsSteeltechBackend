from django.shortcuts import render, HttpResponse
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.permissions import BasePermission
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from dj_rest_auth.registration.views import RegisterView
from django.db.models import Sum
from django.http import HttpResponse
from django.utils import timezone
from django.db import transaction


from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

# models
from fabricator.models import Fabricator
from marketing_rep.models import MarketingRepresentative
from distributor.models import Distributor

# serializers
from fabricator.serializers import FabricatorSerializer
from marketing_rep.serializers import MarketingRepresentativeSerializer
from distributor.serializers import DistributorSerializer
from utils.email_handler import fab_registered_notification


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 500
    page_query_param = "p"


class FabricatorView(APIView):
    serializer_class = FabricatorSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid(raise_exception=True):
            with transaction.atomic():
                fab_instance = serializer.save()

                # send email notification to admin
                fab_registered_notification(
                    fab_name=fab_instance.name,
                    fab_phone_number=fab_instance.phone_number,
                    fab_registration_number=fab_instance.registration_number,
                    fab_district=fab_instance.district,
                    fab_sub_district=fab_instance.sub_district,
                )
            return Response(
                {
                    "success": True,
                    "message": "Fabricator created successfully.",
                    **serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )

    def get(self, request, *args, **kwargs):
        if request.query_params.get("view") == "distributor":
            fabricators = Distributor.objects.all()
            serializer = DistributorSerializer(fabricators, many=True)
            return Response(
                {
                    "success": True,
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        elif request.query_params.get("view") == "marketing-rep":
            market_reps = MarketingRepresentative.objects.all()
            serializer = MarketingRepresentativeSerializer(market_reps, many=True)
            return Response(
                {
                    "success": True,
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )
