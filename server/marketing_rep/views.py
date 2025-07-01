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
from decimal import Decimal

from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

# models
from marketing_rep.models import Reports, RecentActivity, Task
from fabricator.models import Fabricator
from distributor.models import Distributor

# serializers
from marketing_rep.serializers import (
    ReportsSerializer,
    RecentActivitySerializer,
    TaskSerializer,
)


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
        try:
            marketing_rep = request.user.marketingrepresentative
        except AttributeError:
            return Response(
                {
                    "success": False,
                    "message": "User is not a marketing representative.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        assigned_fabricators = Fabricator.objects.filter(
            marketing_representative=marketing_rep
        ).count()

        recent_activities = RecentActivity.objects.filter(
            marketing_rep=marketing_rep
        ).order_by("-created_at")[:5]

        recent_activities_data = RecentActivitySerializer(
            recent_activities, many=True
        ).data

        monthly_sales = Reports.objects.filter(
            marketing_rep=marketing_rep,
            created_at__month=timezone.now().month,
            created_at__year=timezone.now().year,
        ).aggregate(total_sales=Sum("amount")).get("total_sales") or Decimal("0.00")

        last_month_sales = Reports.objects.filter(
            marketing_rep=marketing_rep,
            created_at__month=timezone.now().month - 1,
            created_at__year=timezone.now().year,
        ).aggregate(total_sales=Sum("amount")).get("total_sales") or Decimal("0.00")

        if last_month_sales == 0:
            revenue_change_percentage = "N/A"
        else:

            revenue_change_percentage = str(
                round((monthly_sales - last_month_sales) / last_month_sales * 100, 2)
            )

        total_reports = Reports.objects.filter(marketing_rep=marketing_rep).count()

        pending_tasks = Task.objects.filter(
            marketing_rep=marketing_rep, status="pending"
        ).count()
        completed_tasks = Task.objects.filter(
            marketing_rep=marketing_rep, status="completed"
        ).count()

        return Response(
            {
                "success": True,
                "assigned_fabricators": assigned_fabricators,
                "name": marketing_rep.name,
                "monthly_sales": monthly_sales,
                "total_reports": total_reports,
                "revenue_change_percentage": revenue_change_percentage,
                "pending_tasks": pending_tasks,
                "completed_tasks": completed_tasks,
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
        if request.query_params.get("view") == "fabricator-wise-reports":
            fabricator_id = request.query_params.get("fabricator_id")
            if not fabricator_id:
                return Response(
                    {"success": False, "message": "Fabricator ID is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            reports = Reports.objects.filter(
                fabricator__id=fabricator_id,
                marketing_rep=request.user.marketingrepresentative,
            ).order_by("-created_at")

            total_amount = reports.aggregate(total_amount=Sum("amount")).get(
                "total_amount"
            ) or Decimal("0.00")

            paginator = StandardResultsSetPagination()
            paginated_reports = paginator.paginate_queryset(reports, request)
            serializer = ReportsSerializer(paginated_reports, many=True)

            response_data = {
                "success": True,
                "total_reports": reports.count(),
                "total_amount": total_amount,
            }
            # Add the pagination metadata and results
            paginated_response = paginator.get_paginated_response(serializer.data)
            paginated_response.data.update(response_data)
            return paginated_response

        if request.query_params.get("view") == "fabricators":
            fabricators = (
                Fabricator.objects.filter(
                    marketing_representative=request.user.marketingrepresentative,
                    status="approved",
                )
                .values(
                    "id",
                    "name",
                    "registration_number",
                )
                .order_by("name")
            )
            return Response(fabricators, status=status.HTTP_200_OK)

        elif request.query_params.get("view") == "distributors":
            distributors = (
                Distributor.objects.filter(
                    marketing_representative=request.user.marketingrepresentative
                )
                .values(
                    "id",
                    "name",
                    "phone_number",
                    "district",
                    "sub_district",
                )
                .order_by("name")
            )
            return Response(distributors, status=status.HTTP_200_OK)

        return Response(
            {"success": False, "message": "Invalid view parameter."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def post(self, request):
        """
        Create a new report.
        """
        serializer = ReportsSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):

            # validate if distributor was under the marketing representative
            distributor = serializer.validated_data.get("distributor")
            if not Distributor.objects.filter(
                id=distributor.id,
                marketing_representative=request.user.marketingrepresentative,
            ).exists():
                return Response(
                    {
                        "success": False,
                        "message": "Distributor does not belong to this marketing representative.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # check if attachments are provided
            if not serializer.validated_data.get("attachements_urls"):
                return Response(
                    {
                        "success": False,
                        "message": "Attachments are required.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # check invoice number uniqueness
            if Reports.objects.filter(
                invoice_number=serializer.validated_data.get("invoice_number")
            ).exists():
                return Response(
                    {
                        "success": False,
                        "message": "A report with this invoice number already exists.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

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


class TaskView(APIView):
    permission_classes = [AuthenticateOnlyMar]

    def get(self, request, *args, **kwargs):
        tasks = Task.objects.filter(
            marketing_rep=request.user.marketingrepresentative
        ).order_by("-created_at")
        paginator = StandardResultsSetPagination()
        paginated_tasks = paginator.paginate_queryset(tasks, request)
        serializer = TaskSerializer(paginated_tasks, many=True)
        return paginator.get_paginated_response(serializer.data)

    def patch(self, request, *args, **kwargs):
        """
        Update a task.
        """
        if request.data.get("id"):
            task = Task.objects.filter(
                id=request.data.get("id"),
                marketing_rep=request.user.marketingrepresentative,
            ).first()
            if not task:
                return Response(
                    {"success": False, "message": "Task not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if not request.data.get("status") in [
                "pending",
                "in_progress",
                "completed",
            ]:
                return Response(
                    {"success": False, "message": "Invalid status."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            task.status = request.data.get("status")
            task.save()
            # record recent activity
            RecentActivity.objects.create(
                marketing_rep=request.user.marketingrepresentative,
                description=f"Task {task.description} updated to {task.status}.",
            )
            return Response(
                {
                    "success": True,
                    "message": "Task updated successfully.",
                    **TaskSerializer(task).data,
                },
                status=status.HTTP_200_OK,
            )
        return Response(
            {"success": False, "message": "Task ID is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
