from django.shortcuts import render, HttpResponse
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.permissions import BasePermission
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from dj_rest_auth.registration.views import RegisterView
from django.db.models import Sum, OuterRef, Subquery
from django.http import HttpResponse
from django.utils import timezone
import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
import csv
from django.db.models import Sum, Subquery, OuterRef, Case, When, IntegerField
from datetime import datetime, timedelta
from collections import OrderedDict


from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

# models
from fabricator.models import Fabricator
from marketing_rep.models import MarketingRepresentative, Reports, Task
from distributor.models import Distributor

# serializers
from fabricator.serializers import FabricatorSerializer, ExpandedFabricatorSerializer
from marketing_rep.serializers import (
    MarketingRepresentativeSerializer,
    ReportsSerializer,
    TaskSerializer,
)
from distributor.serializers import DistributorSerializer
from utils.email_handler import (
    fab_status_change_notification,
    send_login_credentials,
    send_marketing_rep_assigned_notification,
)
from utils import dist_upazila_map


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 500
    page_query_param = "p"


# Authenticate User Only Class
class AuthenticateOnlyAdmin(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise PermissionDenied("User is not authenticated.")

        if not getattr(request.user, "is_admin", False):
            raise PermissionDenied("User is not an admin.")

        return True


class DashboardView(APIView):
    permission_classes = [AuthenticateOnlyAdmin]

    def get(self, request, *args, **kwargs):
        applications_count = Fabricator.objects.count()
        approved_count = Fabricator.objects.filter(status="approved").count()
        pending_count = Fabricator.objects.filter(status="pending").count()
        rejected_count = Fabricator.objects.filter(status="rejected").count()
        assigned_count = Fabricator.objects.filter(
            marketing_representative__isnull=False
        ).count()
        marketing_representatives_count = MarketingRepresentative.objects.count()
        distributors_count = Distributor.objects.count()
        sales_vs_date_graph = (
            Reports.objects.values("sales_date")
            .annotate(total_sales=Sum("amount"))
            .order_by("sales_date")
        )
        sales_vs_fabricator_graph = (
            Reports.objects.values("fabricator__name")
            .annotate(total_sales=Sum("amount"))
            .order_by("-total_sales")
        )

        return Response(
            {
                "applications_count": applications_count,
                "approved_count": approved_count,
                "pending_count": pending_count,
                "rejected_count": rejected_count,
                "assigned_count": assigned_count,
                "marketing_representatives_count": marketing_representatives_count,
                "distributors_count": distributors_count,
                "sales_vs_date_graph": list(sales_vs_date_graph),
                "sales_vs_fabricator_graph": list(sales_vs_fabricator_graph)[
                    :10
                ],  # Limit to top 10 fabricators
            },
            status=status.HTTP_200_OK,
        )


class FabricatorView(APIView):
    permission_classes = [AuthenticateOnlyAdmin]

    def get(self, request, *args, **kwargs):
        if request.query_params.get("id"):
            fabricator_id = request.query_params.get("id")
            try:
                fabricator = Fabricator.objects.get(id=fabricator_id)
                serializer = ExpandedFabricatorSerializer(fabricator)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except Fabricator.DoesNotExist:
                return JsonResponse(
                    {"success": False, "message": "Fabricator not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        if request.query_params.get("view") == "pending":
            fabricators = Fabricator.objects.filter(status="pending").order_by(
                "-created_at"
            )
        elif request.query_params.get("view") == "approved":
            fabricators = Fabricator.objects.filter(
                status="approved",
            ).order_by("-created_at")
        elif request.query_params.get("view") == "rejected":
            fabricators = Fabricator.objects.filter(status="rejected").order_by(
                "-created_at"
            )
        elif request.query_params.get("view") == "all":
            fabricators = Fabricator.objects.all().order_by("-created_at")
        elif request.query_params.get("view") == "assigned":
            fabricators = Fabricator.objects.filter(
                status="approved",
                marketing_representative__isnull=False,
            ).order_by("-created_at")

        else:
            return JsonResponse(
                {"success": False, "message": "Invalid view parameter."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        paginator = StandardResultsSetPagination()
        result_page = paginator.paginate_queryset(fabricators, request)
        serializer = ExpandedFabricatorSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def patch(self, request, *args, **kwargs):
        if request.query_params.get("action") == "status":
            fabricator_id = request.data.get("id")
            fstatus = request.data.get("status")
            if not fabricator_id or not fstatus:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "ID and status parameters are required.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                fabricator = Fabricator.objects.get(id=fabricator_id)
            except Fabricator.DoesNotExist:
                return JsonResponse(
                    {"success": False, "message": "Fabricator not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if fstatus not in ["pending", "approved", "rejected"]:
                return JsonResponse(
                    {"success": False, "message": "Invalid status."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            fabricator.status = fstatus
            fabricator.save()
            serializer = ExpandedFabricatorSerializer(fabricator)

            # send email notification to the fabricator if status is approved or rejected
            fab_status_change_notification(
                fab_name=fabricator.name,
                status=fstatus,
                date=fabricator.created_at.strftime("%Y-%m-%d"),
                fab_email=(
                    fabricator.marketing_representative.email
                    if fabricator.marketing_representative
                    else None
                ),
            )
            return JsonResponse(
                {
                    "success": True,
                    "message": "Fabricator status updated successfully.",
                    **serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        if request.query_params.get("action") == "assign":
            fabricator_id = request.data.get("id")
            marketing_rep_id = request.data.get("marketing_rep_id")

            if not fabricator_id or not marketing_rep_id:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Fabricator ID and Marketing Representative ID are required.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                fabricator = Fabricator.objects.get(id=fabricator_id)
            except Fabricator.DoesNotExist:
                return JsonResponse(
                    {"success": False, "message": "Fabricator not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            try:
                marketing_rep = MarketingRepresentative.objects.get(id=marketing_rep_id)
            except MarketingRepresentative.DoesNotExist:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Marketing Representative not found.",
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            # check if the fabricator is already assigned to a marketing representative
            if fabricator.marketing_representative:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Fabricator is already assigned to a Marketing Representative.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # check if the fabricator is approved
            if fabricator.status != "approved":
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Fabricator must be approved before assigning a Marketing Representative.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            fabricator.marketing_representative = marketing_rep
            fabricator.save()
            serializer = FabricatorSerializer(fabricator)

            # send email notification to the marketing representative
            send_marketing_rep_assigned_notification(
                user_name=marketing_rep.name,
                fab_name=fabricator.name,
                fab_phone_number=fabricator.phone_number,
                fab_registration_number=fabricator.registration_number,
                fab_district=fabricator.district,
                fab_sub_district=fabricator.sub_district,
                marketing_rep_email=marketing_rep.email,
            )
            return JsonResponse(
                {
                    "success": True,
                    "message": "Marketing Representative assigned to Fabricator successfully. An email notification has been sent to the Marketing Representative.",
                },
                status=status.HTTP_200_OK,
            )


class MarketingRepresentativeView(APIView):
    permission_classes = [AuthenticateOnlyAdmin]

    def get(self, request, *args, **kwargs):
        if request.query_params.get("view") == "tasks":
            if not request.query_params.get("id"):
                return JsonResponse(
                    {"success": False, "message": "ID parameter is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                rep = MarketingRepresentative.objects.get(
                    id=request.query_params.get("id")
                )
            except MarketingRepresentative.DoesNotExist:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Marketing Representative not found.",
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )
            tasks = Task.objects.filter(marketing_rep=rep).order_by("-created_at")
            paginator = StandardResultsSetPagination()
            result_page = paginator.paginate_queryset(tasks, request)
            serializer = TaskSerializer(result_page, many=True)
            return paginator.get_paginated_response(serializer.data)

        if request.query_params.get("id"):
            rep_id = request.query_params.get("id")
            try:
                rep = MarketingRepresentative.objects.get(id=rep_id)
                fab_count = Fabricator.objects.filter(
                    marketing_representative=rep
                ).count()
                serializer = MarketingRepresentativeSerializer(rep)
                return Response(
                    {"assigned_fabricators_count": fab_count, **serializer.data},
                    status=status.HTTP_200_OK,
                )
            except MarketingRepresentative.DoesNotExist:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Marketing Representative not found.",
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

        reps = MarketingRepresentative.objects.all().order_by("-created_at")
        paginator = StandardResultsSetPagination()
        result_page = paginator.paginate_queryset(reps, request)
        serializer = MarketingRepresentativeSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, *args, **kwargs):
        if request.query_params.get("action") == "assign":
            if not request.data.get("id"):
                return JsonResponse(
                    {"success": False, "message": "ID parameter is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                rep = MarketingRepresentative.objects.get(id=request.data["id"])
            except MarketingRepresentative.DoesNotExist:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Marketing Representative not found.",
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )
            if not request.data.get("description"):
                return JsonResponse(
                    {"success": False, "message": "Description is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            Task.objects.create(
                marketing_rep=rep,
                description=request.data["description"],
                status="pending",
            )
            return JsonResponse(
                {
                    "success": True,
                    "message": "Task assigned to Marketing Representative successfully.",
                },
                status=status.HTTP_201_CREATED,
            )

        serializer = MarketingRepresentativeSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):

            # check if a marketing representative with the same email already exists
            if MarketingRepresentative.objects.filter(
                email=serializer.validated_data["email"]
            ).exists():
                return JsonResponse(
                    {
                        "success": False,
                        "message": "A marketing representative with this email already exists.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # create a new user for the marketing representative with password
            User = get_user_model()
            random_password = get_random_string(length=6)
            user_instance = User.objects.create_user(
                username=serializer.validated_data["email"],
                password=random_password,
                email=serializer.validated_data["email"],
                first_name=serializer.validated_data["name"],
                is_marketing_representative=True,
            )

            serializer.save(marketing_rep=user_instance)

            # send email to the marketing representative with login credentials
            send_login_credentials(
                username=serializer.validated_data["name"],
                email=serializer.validated_data["email"],
                password=random_password,
            )

            return Response(
                {
                    "success": True,
                    "message": "Marketing Representative created successfully. Login credentials have been sent to the email.",
                    **serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )

    def put(self, request, *args, **kwargs):
        rep_id = request.query_params.get("id")
        if not rep_id:
            return JsonResponse(
                {"success": False, "message": "ID parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            rep = MarketingRepresentative.objects.get(id=rep_id)
        except MarketingRepresentative.DoesNotExist:
            return JsonResponse(
                {"success": False, "message": "Marketing Representative not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = MarketingRepresentativeSerializer(rep, data=request.data)
        if serializer.is_valid(raise_exception=True):
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return JsonResponse(
            {"success": False, "message": "Invalid data."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def delete(self, request, *args, **kwargs):
        rep_id = request.query_params.get("id")
        if not rep_id:
            return JsonResponse(
                {"success": False, "message": "ID parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            rep = MarketingRepresentative.objects.get(id=rep_id)

            # Also delete the associated user
            if rep.marketing_rep:
                user = rep.marketing_rep
            rep.delete()
            user.delete()

            return JsonResponse(
                {
                    "success": True,
                    "message": "Marketing Representative deleted successfully.",
                },
                status=status.HTTP_204_NO_CONTENT,
            )
        except MarketingRepresentative.DoesNotExist:
            return JsonResponse(
                {"success": False, "message": "Marketing Representative not found."},
                status=status.HTTP_404_NOT_FOUND,
            )


class DistributorView(APIView):
    permission_classes = [AuthenticateOnlyAdmin]

    def get(self, request, *args, **kwargs):
        if request.query_params.get("id"):
            distributor_id = request.query_params.get("id")
            try:
                distributor = Distributor.objects.get(id=distributor_id)
                serializer = DistributorSerializer(distributor)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except Distributor.DoesNotExist:
                return JsonResponse(
                    {"success": False, "message": "Distributor not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        distributors = Distributor.objects.all().order_by("-created_at")
        paginator = StandardResultsSetPagination()
        result_page = paginator.paginate_queryset(distributors, request)
        serializer = DistributorSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request, *args, **kwargs):
        serializer = DistributorSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

    def put(self, request, *args, **kwargs):
        distributor_id = request.query_params.get("id")
        if not distributor_id:
            return JsonResponse(
                {"success": False, "message": "ID parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            distributor = Distributor.objects.get(id=distributor_id)
        except Distributor.DoesNotExist:
            return JsonResponse(
                {"success": False, "message": "Distributor not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = DistributorSerializer(distributor, data=request.data)
        if serializer.is_valid(raise_exception=True):
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return JsonResponse(
            {"success": False, "message": "Invalid data."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def delete(self, request, *args, **kwargs):
        distributor_id = request.query_params.get("id")
        if not distributor_id:
            return JsonResponse(
                {"success": False, "message": "ID parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            distributor = Distributor.objects.get(id=distributor_id)
            distributor.delete()
            return JsonResponse(
                {
                    "success": True,
                    "message": "Distributor deleted successfully.",
                },
                status=status.HTTP_204_NO_CONTENT,
            )
        except Distributor.DoesNotExist:
            return JsonResponse(
                {"success": False, "message": "Distributor not found."},
                status=status.HTTP_404_NOT_FOUND,
            )


# file upload
class UploadFile(APIView):
    def post(self, request):
        file = request.FILES.get("file")
        if not file:
            return Response(
                {"success": False, "message": "No file provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        url = "https://transfer.ongshak.com/upload/"
        params = {
            "key": settings.TRANSFER_ONGSHAK_API_KEY,
            "path": "article39",
        }

        # if file size exceeds 20MB, return error
        if file.size > 20 * 1024 * 1024:
            return Response(
                {"success": False, "message": "File size exceeds 20MB"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # if file size is an image, and greater than 2MB, set compression level to 50
        if file.size > 2 * 1024 * 1024 and file.name.lower().endswith(
            (".jpg", ".jpeg", ".png")
        ):
            params["compression_level"] = "50"

        response = requests.post(url, params=params, files={"file": file})

        return Response(
            {
                "success": True,
                **response.json(),
            },
            status=status.HTTP_201_CREATED,
        )


class ReportView(APIView):
    permission_classes = [AuthenticateOnlyAdmin]

    def get(self, request, *args, **kwargs):
        if request.query_params.get("id"):
            report_id = request.query_params.get("id")
            try:
                report = Reports.objects.get(id=report_id)
                serializer = ReportsSerializer(report)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except Reports.DoesNotExist:
                return JsonResponse(
                    {"success": False, "message": "Report not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        from_date = request.query_params.get("from_date")
        to_date = request.query_params.get("to_date")

        # Validate date format
        if from_date and to_date:
            try:
                from_date = timezone.datetime.fromisoformat(from_date)
                to_date = timezone.datetime.fromisoformat(to_date)
            except ValueError:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Invalid date format. Use ISO format (YYYY-MM-DD).",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if request.query_params.get("view") == "fabricators":
            report = Reports.objects.all().order_by("-sales_date")

            if from_date and to_date:
                report = report.filter(sales_date__range=(from_date, to_date))

            paginator = StandardResultsSetPagination()
            result_page = paginator.paginate_queryset(report, request)
            serializer = ReportsSerializer(
                result_page,
                many=True,
                hide_fields=[
                    "distributor_name",
                    "distributor_phone_number",
                    "distributor_district",
                    "distributor_sub_district",
                ],
            )
            return paginator.get_paginated_response(serializer.data)

        elif request.query_params.get("view") == "marketing_representatives":
            report = Reports.objects.all().order_by("-sales_date")

            if from_date and to_date:
                report = report.filter(sales_date__range=(from_date, to_date))

            paginator = StandardResultsSetPagination()
            result_page = paginator.paginate_queryset(report, request)
            serializer = ReportsSerializer(
                result_page,
                many=True,
                hide_fields=[
                    "fabricator_name",
                    "fabricator_registration_number",
                    "fabricator_phone_number",
                    "fabricator_district",
                    "fabricator_sub_district",
                ],
            )
            return paginator.get_paginated_response(serializer.data)

        elif request.query_params.get("view") == "summary":
            # Individual subqueries for each distributor field
            distributor_name = Subquery(
                Reports.objects.filter(fabricator=OuterRef("fabricator"))
                .order_by("id")
                .values("distributor__name")[:1]
            )
            distributor_phone = Subquery(
                Reports.objects.filter(fabricator=OuterRef("fabricator"))
                .order_by("id")
                .values("distributor__phone_number")[:1]
            )
            distributor_district = Subquery(
                Reports.objects.filter(fabricator=OuterRef("fabricator"))
                .order_by("id")
                .values("distributor__district")[:1]
            )
            distributor_sub_district = Subquery(
                Reports.objects.filter(fabricator=OuterRef("fabricator"))
                .order_by("id")
                .values("distributor__sub_district")[:1]
            )

            # Individual subqueries for each marketing_rep field
            rep_name = Subquery(
                Reports.objects.filter(fabricator=OuterRef("fabricator"))
                .order_by("id")
                .values("marketing_rep__name")[:1]
            )
            rep_phone = Subquery(
                Reports.objects.filter(fabricator=OuterRef("fabricator"))
                .order_by("id")
                .values("marketing_rep__phone_number")[:1]
            )
            rep_district = Subquery(
                Reports.objects.filter(fabricator=OuterRef("fabricator"))
                .order_by("id")
                .values("marketing_rep__district")[:1]
            )
            rep_sub_district = Subquery(
                Reports.objects.filter(fabricator=OuterRef("fabricator"))
                .order_by("id")
                .values("marketing_rep__sub_district")[:1]
            )

            # date filter
            report = Reports.objects.all()
            if from_date and to_date:
                report = report.filter(sales_date__range=(from_date, to_date))

            # Final grouped query
            fabricator_summary = (
                report.values(
                    "fabricator",
                    "fabricator__name",
                    "fabricator__registration_number",
                    "fabricator__phone_number",
                    "fabricator__district",
                    "fabricator__sub_district",
                )
                .annotate(
                    total_amount=Sum("amount"),
                    distributor_name=distributor_name,
                    distributor_phone=distributor_phone,
                    distributor_district=distributor_district,
                    distributor_sub_district=distributor_sub_district,
                    marketing_rep_name=rep_name,
                    marketing_rep_phone=rep_phone,
                    marketing_rep_district=rep_district,
                    marketing_rep_sub_district=rep_sub_district,
                )
                .order_by("-total_amount")
            )
            paginator = StandardResultsSetPagination()
            result_page = paginator.paginate_queryset(fabricator_summary, request)
            return paginator.get_paginated_response(result_page)

        return JsonResponse(
            {"success": False, "message": "Invalid view parameter."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def post(self, request, *args, **kwargs):
        from_date = request.data.get("from_date")
        to_date = request.data.get("to_date")

        if from_date and to_date:
            try:
                from_date = timezone.datetime.fromisoformat(from_date)
                to_date = timezone.datetime.fromisoformat(to_date)
            except ValueError:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Invalid date format. Use ISO format (YYYY-MM-DD).",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if request.query_params.get("action") == "csv":
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = (
                f'attachment; filename="report-{timezone.now().strftime("%Y-%m-%d")}.csv"'
            )
            writer = csv.writer(response)

            if request.query_params.get("view") == "fabricators":
                reports = Reports.objects.all().order_by("-sales_date")
                if from_date and to_date:
                    report = report.filter(sales_date__range=(from_date, to_date))
                writer.writerow(
                    [
                        "Fabricator Name",
                        "Registration Number",
                        "Phone Number",
                        "District",
                        "Sub-District",
                        "Sales Date",
                        "Amount",
                        "Invoice Number",
                    ]
                )

                for report in reports:
                    writer.writerow(
                        [
                            report.fabricator.name,
                            report.fabricator.registration_number,
                            report.fabricator.phone_number,
                            report.fabricator.district,
                            report.fabricator.sub_district,
                            report.sales_date.strftime("%Y-%m-%d"),
                            report.amount,
                            report.invoice_number,
                        ]
                    )

                return response

            # TODO: its actually distributors
            elif request.query_params.get("view") == "marketing_representatives":
                reports = Reports.objects.all().order_by("-sales_date")
                if from_date and to_date:
                    report = report.filter(sales_date__range=(from_date, to_date))
                writer.writerow(
                    [
                        "Dist. Name",
                        "Phone Number",
                        "District",
                        "Sub-District",
                        "Sales Date",
                        "Amount",
                        "Invoice Number",
                    ]
                )

                for report in reports:
                    writer.writerow(
                        [
                            report.distributor.name,
                            report.distributor.phone_number,
                            report.distributor.district,
                            report.distributor.sub_district,
                            report.sales_date.strftime("%Y-%m-%d"),
                            report.amount,
                            report.invoice_number,
                        ]
                    )

                return response

        if request.query_params.get("view") == "summary":
            # Individual subqueries for each distributor field
            distributor_name = Subquery(
                Reports.objects.filter(fabricator=OuterRef("fabricator"))
                .order_by("id")
                .values("distributor__name")[:1]
            )
            distributor_phone = Subquery(
                Reports.objects.filter(fabricator=OuterRef("fabricator"))
                .order_by("id")
                .values("distributor__phone_number")[:1]
            )
            distributor_district = Subquery(
                Reports.objects.filter(fabricator=OuterRef("fabricator"))
                .order_by("id")
                .values("distributor__district")[:1]
            )
            distributor_sub_district = Subquery(
                Reports.objects.filter(fabricator=OuterRef("fabricator"))
                .order_by("id")
                .values("distributor__sub_district")[:1]
            )

            # Individual subqueries for each marketing_rep field
            rep_name = Subquery(
                Reports.objects.filter(fabricator=OuterRef("fabricator"))
                .order_by("id")
                .values("marketing_rep__name")[:1]
            )
            rep_phone = Subquery(
                Reports.objects.filter(fabricator=OuterRef("fabricator"))
                .order_by("id")
                .values("marketing_rep__phone_number")[:1]
            )
            rep_district = Subquery(
                Reports.objects.filter(fabricator=OuterRef("fabricator"))
                .order_by("id")
                .values("marketing_rep__district")[:1]
            )
            rep_sub_district = Subquery(
                Reports.objects.filter(fabricator=OuterRef("fabricator"))
                .order_by("id")
                .values("marketing_rep__sub_district")[:1]
            )

            # Prepare past 12 months
            now = datetime.now()
            months = [(now - timedelta(days=30 * i)).replace(day=1) for i in range(11, -1, -1)]
            months = [(dt.year, dt.month) for dt in months]

            # Create annotations and headers
            monthly_annotations = OrderedDict()
            monthly_headers = []
            for year, month in months:
                label = f"{datetime(year, month, 1).strftime('%B')}'{year}"
                monthly_headers.append(label)
                key = f"sales_{year}_{month}"
                monthly_annotations[key] = Sum(
                    Case(
                        When(
                            sales_date__year=year,
                            sales_date__month=month,
                            then="amount"
                        ),
                        output_field=IntegerField()
                    )
                )

            # Filter by date range if provided
            report = Reports.objects.all()
            if from_date and to_date:
                report = report.filter(sales_date__range=(from_date, to_date))

            # Final query with summary
            fabricator_summary = (
                report.values(
                    "fabricator",
                    "fabricator__name",
                    "fabricator__registration_number",
                    "fabricator__phone_number",
                    "fabricator__district",
                    "fabricator__sub_district",
                )
                .annotate(
                    total_amount=Sum("amount"),
                    distributor_name=distributor_name,
                    distributor_phone=distributor_phone,
                    distributor_district=distributor_district,
                    distributor_sub_district=distributor_sub_district,
                    marketing_rep_name=rep_name,
                    marketing_rep_phone=rep_phone,
                    marketing_rep_district=rep_district,
                    marketing_rep_sub_district=rep_sub_district,
                    **monthly_annotations
                )
                .order_by("-total_amount")
            )

            # Write header to CSV
            writer.writerow(
                [
                    "Fabricator Reg. No.",
                    "Fabricator Name",
                    "Phone Number",
                    "District",
                    "Sub-District",
                    "",
                    "Distributor Name",
                    "Distributor Phone Number",
                    "Distributor District",
                    "Distributor Sub-District",
                    "",
                    "Marketing Representative Name",
                    "Marketing Representative Phone Number",
                    "Marketing Representative District",
                    "Marketing Representative Sub-District",
                    "",
                    *monthly_headers,
                    "Total Amount",
                ]
            )

            # Write rows
            for summary in fabricator_summary:
                writer.writerow(
                    [
                        summary["fabricator__registration_number"],
                        summary["fabricator__name"],
                        summary["fabricator__phone_number"],
                        summary["fabricator__district"],
                        summary["fabricator__sub_district"],
                        "",
                        summary["distributor_name"],
                        summary["distributor_phone"],
                        summary["distributor_district"],
                        summary["distributor_sub_district"],
                        "",
                        summary["marketing_rep_name"],
                        summary["marketing_rep_phone"],
                        summary["marketing_rep_district"],
                        summary["marketing_rep_sub_district"],
                        "",
                        *[summary.get(f"sales_{year}_{month}", 0) for year, month in months],
                        summary["total_amount"],
                    ]
                )

            return response


class SubDistrictView(APIView):
    def get(self, request, *args, **kwargs):
        if request.query_params.get("view") == "districts":
            districts = dist_upazila_map.districts
            return JsonResponse(
                {"success": True, "districts": districts.get("districts", [])},
                status=status.HTTP_200_OK,
            )
        if request.query_params.get("view") == "thanas":
            district_id = request.query_params.get("district-id")
            if not district_id:
                return JsonResponse(
                    {"success": False, "message": "District ID parameter is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            upazilas_thanas = dist_upazila_map.upazilas_thanas.get("upazilas", [])
            wanted_upazilas = []

            for upazila in upazilas_thanas:
                if upazila["district_id"] == district_id:
                    wanted_upazilas.append(upazila)

            if wanted_upazilas:
                return JsonResponse(
                    {"success": True, "upazilas": wanted_upazilas},
                    status=status.HTTP_200_OK,
                )
            return JsonResponse(
                {"success": False, "message": "District not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return JsonResponse(
            {"success": False, "message": "Invalid view parameter."},
            status=status.HTTP_400_BAD_REQUEST,
        )
