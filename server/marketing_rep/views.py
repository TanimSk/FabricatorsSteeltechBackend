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
import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
import csv


from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

# models
from marketing_rep.models import Reports, RecentActivity
from fabricator.models import Fabricator

# serializers
from marketing_rep.serializers import ReportsSerializer, RecentActivitySerializer


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 500
    page_query_param = "p"


# Authenticate User Only Class
class AuthenticateOnlyMar(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise PermissionDenied("User is not authenticated.")

        if not getattr(request.user, "is_marketing_representative", False):
            raise PermissionDenied("User is not an Marketing Representative.")

        return True


class DashboardView(APIView):
    permission_classes = [AuthenticateOnlyMar]

    def get(self, request, *args, **kwargs):
        """
        Get the dashboard data for the marketing representative.
        """
        marketing_rep = request.user.marketingrepresentative

        assigned_fabricators = Fabricator.objects.filter(
            marketing_representative=marketing_rep
        ).count()

        recent_activities = RecentActivity.objects.filter(
            marketing_rep=marketing_rep
        ).order_by("-created_at")[:5]

        recent_activities_data = RecentActivitySerializer(
            recent_activities, many=True
        ).data

        monthly_sales = (
            Reports.objects.filter(
                marketing_rep=marketing_rep,
                created_at__month=timezone.now().month,
                created_at__year=timezone.now().year,
            )
            .aggregate(total_sales=Sum("amount"))
            .get("total_sales", 0)
        )

        total_reports = Reports.objects.filter(marketing_rep=marketing_rep).count()

        return Response(
            {
                "assigned_fabricators": assigned_fabricators,
                "monthly_sales": monthly_sales,
                "total_reports": total_reports,
                "recent_activities": recent_activities_data,
            },
            status=status.HTTP_200_OK,
        )


class ReportsView(APIView):
    permission_classes = [AuthenticateOnlyMar]

    def get(self, request, *args, **kwargs):
        """
        List of fabricators and distributors for option list.
        """
        if request.query_params.get("view") == "fabricators":
            fabricators = Fabricator.objects.filter(
                marketing_representative=request.user.marketingrepresentative
            ).values(
                "id",
                "name",
                "registration_number",
                "distributor__name",
            )
            return Response(fabricators, status=status.HTTP_200_OK)

    def post(self, request):
        """
        Create a new report.
        """
        serializer = ReportsSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            serializer.save(marketing_rep=request.user.marketingrepresentative)
            # record recent activity
            RecentActivity.objects.create(
                marketing_rep=request.user.marketingrepresentative,
                description=f"Report submitted for fabricator {serializer.validated_data['fabricator'].name}",
            )
            return Response(
                {
                    "success": True,
                    "message": "Report created successfully.",
                    **serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )
