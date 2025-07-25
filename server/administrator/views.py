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
import random
from django.db.models import Q


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
from administrator.serializers import MarketingRepAndFabricatorSerializer
from distributor.serializers import DistributorSerializer, SingleDistributorSerializer
from utils.sms_handler import send_sms_via_cloudsms
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

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.page.paginator.count,
                "page_size": self.get_page_size(self.request),
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "num_pages": self.page.paginator.num_pages,
                "current_page": self.page.number,
                "results": data,
            }
        )


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
        if request.query_params.get("search"):
            query = Q()
            search = request.query_params.get("search").strip()

            if search:
                query = (
                    Q(institution__icontains=search)
                    | Q(name__icontains=search)
                    | Q(registration_number__icontains=search)
                    | Q(district__icontains=search)
                    | Q(phone_number__icontains=search)
                )

            filtered_fabricators = Fabricator.objects.filter(query).order_by(
                "-created_at"
            )
            paginator = StandardResultsSetPagination()
            result_page = paginator.paginate_queryset(filtered_fabricators, request)
            serializer = ExpandedFabricatorSerializer(result_page, many=True)
            return paginator.get_paginated_response(serializer.data)

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
                market_rep_name=(
                    fabricator.marketing_representative.name
                    if fabricator.marketing_representative
                    else "N/A"
                ),
                phone_number=fabricator.phone_number,
                registration_number=fabricator.registration_number,
                status=fstatus,
                date=fabricator.created_at.strftime("%Y-%m-%d"),
                fab_email=fabricator.email if fabricator.email else None,
                marketing_rep_email=(
                    fabricator.marketing_representative.email
                    if fabricator.marketing_representative
                    else None
                ),
            )

            # send SMS to the fabricator & mar if status is approved or rejected
            if fstatus in ["approved", "rejected"]:
                send_sms_via_cloudsms(
                    recipient_number=fabricator.phone_number,
                    message=(
                        f"Your reg. request has been {fstatus}.\n "
                        f"{fabricator.name}\n "
                        f"{fabricator.phone_number}\n "
                        f"Reg. No: {fabricator.registration_number}\n "
                        f"- STEELTECH"
                    ),
                )
                if fabricator.marketing_representative:
                    send_sms_via_cloudsms(
                        recipient_number=fabricator.marketing_representative.phone_number,
                        message=(
                            f"Fabricator request {fstatus}.\n "
                            f"{fabricator.name}\n "
                            f"{fabricator.phone_number}\n "
                            f"Reg. No.: {fabricator.registration_number}\n "
                            f"- STEELTECH"
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
            # if fabricator.marketing_representative:
            #     return JsonResponse(
            #         {
            #             "success": False,
            #             "message": "Fabricator is already assigned to a Marketing Representative.",
            #         },
            #         status=status.HTTP_400_BAD_REQUEST,
            #     )
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

            # send SMS to marketing representative
            send_sms_via_cloudsms(
                recipient_number=marketing_rep.phone_number,
                message=(
                    f"Fabricator assigned:\n"
                    f"{fabricator.name}\n"
                    f"{fabricator.phone_number}\n"
                    f"Reg. No.: {fabricator.registration_number}\n"
                    f"- STEELTECH"
                ),
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
        if request.query_params.get("search"):
            query = Q()
            search = request.query_params.get("search").strip()

            if search:
                if "@" in search:
                    query = Q(email__icontains=search)
                else:
                    query = (
                        Q(name__icontains=search)
                        | Q(district__icontains=search)
                        | Q(phone_number__icontains=search)
                    )

            filtered_mar = MarketingRepresentative.objects.filter(query).order_by(
                "-created_at"
            )
            paginator = StandardResultsSetPagination()
            result_page = paginator.paginate_queryset(filtered_mar, request)
            serializer = MarketingRepresentativeSerializer(result_page, many=True)
            return paginator.get_paginated_response(serializer.data)

        if request.query_params.get("view") == "all-fabricator-list":
            fabricators = Fabricator.objects.filter(
                status="approved",
            ).order_by("-created_at")
            return Response(
                FabricatorSerializer(fabricators, many=True).data,
                status=status.HTTP_200_OK,
            )

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
            if request.query_params.get("view") == "assigned-fabricators":
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
                fabricators = Fabricator.objects.filter(
                    marketing_representative=rep
                ).order_by("-created_at")
                paginator = StandardResultsSetPagination()
                result_page = paginator.paginate_queryset(fabricators, request)
                serializer = FabricatorSerializer(result_page, many=True)
                return paginator.get_paginated_response(serializer.data)

            if request.query_params.get("view") == "assigned-distributors":
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
                distributors = Distributor.objects.filter(
                    marketing_representative=rep
                ).order_by("-created_at")
                paginator = StandardResultsSetPagination()
                result_page = paginator.paginate_queryset(distributors, request)
                serializer = DistributorSerializer(result_page, many=True)
                return paginator.get_paginated_response(serializer.data)

            rep_id = request.query_params.get("id")
            try:
                rep = MarketingRepresentative.objects.get(id=rep_id)
                fab_count = Fabricator.objects.filter(
                    marketing_representative=rep
                ).count()
                dist_count = Distributor.objects.filter(
                    marketing_representative=rep
                ).count()
                serializer = MarketingRepresentativeSerializer(rep)
                return Response(
                    {
                        "assigned_fabricators_count": fab_count,
                        "assigned_distributors_count": dist_count,
                        **serializer.data,
                    },
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

        if request.query_params.get("action") == "assign-fabricator":
            fabricators = request.data.get("fabricators", [])
            if not fabricators:
                return JsonResponse(
                    {"success": False, "message": "Fabricators list is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            mar_id = request.query_params.get("id")
            if not mar_id:
                return JsonResponse(
                    {"success": False, "message": "ID parameter is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                rep = MarketingRepresentative.objects.get(id=mar_id)
            except MarketingRepresentative.DoesNotExist:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Marketing Representative not found.",
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            for fab_id in fabricators:
                try:
                    fab = Fabricator.objects.get(id=fab_id)
                except Fabricator.DoesNotExist:
                    return JsonResponse(
                        {
                            "success": False,
                            "message": f"Fabricator with ID {fab_id} not found.",
                        },
                        status=status.HTTP_404_NOT_FOUND,
                    )
                fab.marketing_representative = rep
                fab.save()
            return JsonResponse(
                {
                    "success": True,
                    "message": "Fabricators assigned to Marketing Representative successfully.",
                },
                status=status.HTTP_200_OK,
            )

        if request.query_params.get("action") == "assign-distributor":
            distributors = request.data.get("distributors", [])
            if not distributors:
                return JsonResponse(
                    {"success": False, "message": "Distributors list is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            mar_id = request.query_params.get("id")
            if not mar_id:
                return JsonResponse(
                    {"success": False, "message": "ID parameter is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                rep = MarketingRepresentative.objects.get(id=mar_id)
            except MarketingRepresentative.DoesNotExist:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Marketing Representative not found.",
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            for dist_id in distributors:
                try:
                    dist = Distributor.objects.get(id=dist_id)
                except Distributor.DoesNotExist:
                    return JsonResponse(
                        {
                            "success": False,
                            "message": f"Distributor with ID {dist_id} not found.",
                        },
                        status=status.HTTP_404_NOT_FOUND,
                    )
                dist.marketing_representative = rep
                dist.save()
            return JsonResponse(
                {
                    "success": True,
                    "message": "Distributors assigned to Marketing Representative successfully.",
                },
                status=status.HTTP_200_OK,
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
            random_password = f"S{random.randint(0, 9)}{str(MarketingRepresentative.objects.count() + 1).zfill(4)}"
            user_instance = User.objects.create_user(
                username=serializer.validated_data["email"],
                password=random_password,
                email=serializer.validated_data["email"],
                first_name=serializer.validated_data["name"],
                is_marketing_representative=True,
            )

            mar = serializer.save(marketing_rep=user_instance)
            mar.password_txt = random_password
            mar.save()

            # send email to the marketing representative with login credentials
            send_login_credentials(
                username=serializer.validated_data["name"],
                email=serializer.validated_data["email"],
                password=random_password,
            )
            # send SMS
            send_sms_via_cloudsms(
                recipient_number=mar.phone_number,
                message=(
                    f"Email: {mar.email}\nPassword: {mar.password_txt}\n"
                    f"Login to the mobile app with this credentials."
                    f"\n- STEELTECH"
                ),
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
                {"success": False, "message": "Mar. ID parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if request.query_params.get("action") == "remove-distributor":
            if not request.query_params.get("distributor_id"):
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Distributor ID parameter is required.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            distributor_id = request.query_params.get("distributor_id")
            try:
                distributor = Distributor.objects.get(
                    id=distributor_id, marketing_representative__id=rep_id
                )
            except Distributor.DoesNotExist:
                return JsonResponse(
                    {"success": False, "message": "Distributor not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            distributor.marketing_representative = None
            distributor.save()
            return JsonResponse(
                {
                    "success": True,
                    "message": "Distributor removed from Marketing Representative successfully.",
                },
                status=status.HTTP_200_OK,
            )

        if request.query_params.get("action") == "remove-fabricator":
            if not request.query_params.get("fabricator_id"):
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Fabricator ID parameter is required.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            fabricator_id = request.query_params.get("fabricator_id")
            try:
                fabricator = Fabricator.objects.get(
                    id=fabricator_id, marketing_representative__id=rep_id
                )
            except Fabricator.DoesNotExist:
                return JsonResponse(
                    {"success": False, "message": "Fabricator not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            fabricator.marketing_representative = None
            fabricator.save()
            return JsonResponse(
                {
                    "success": True,
                    "message": "Fabricator removed from Marketing Representative successfully.",
                },
                status=status.HTTP_200_OK,
            )

        try:
            rep = MarketingRepresentative.objects.get(id=rep_id)
            rep.delete()
            # Also delete the associated user
            if rep.marketing_rep:
                user = rep.marketing_rep
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
        if request.query_params.get("search"):
            query = Q()
            search = request.query_params.get("search").strip()

            if search:
                query = (
                    Q(name__icontains=search)
                    | Q(district__icontains=search)
                    | Q(phone_number__icontains=search)
                )

            filtered_mar = Distributor.objects.filter(query).order_by("-created_at")
            paginator = StandardResultsSetPagination()
            result_page = paginator.paginate_queryset(filtered_mar, request)
            serializer = DistributorSerializer(result_page, many=True)
            return paginator.get_paginated_response(serializer.data)

        if request.query_params.get("id"):
            distributor_id = request.query_params.get("id")
            try:
                distributor = Distributor.objects.get(id=distributor_id)
                serializer = SingleDistributorSerializer(distributor)
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
            "path": "steeltech",
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

        print(response.text)
        if response.status_code != 200:
            # log the error in file
            print(f"Error uploading file: {response.text}")
            with open("errors.log", "a") as log_file:
                log_file.write(f"{timezone.now()}: {response.text}\n")

            return Response(
                {"success": False, "message": response.text},
                status=status.HTTP_400_BAD_REQUEST,
            )

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
        if request.query_params.get("view") == "marketing-rep-and-fabricator":
            if request.query_params.get("id"):
                try:
                    fabricator = Fabricator.objects.get(
                        id=request.query_params.get("id")
                    )
                except Fabricator.DoesNotExist:
                    return JsonResponse(
                        {"success": False, "message": "Fabricator not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )
                serializer = MarketingRepAndFabricatorSerializer(fabricator)
                return Response(serializer.data, status=status.HTTP_200_OK)

            if request.query_params.get("marketing-rep-id"):
                try:
                    mar = MarketingRepresentative.objects.get(
                        id=request.query_params.get("marketing-rep-id")
                    )
                except MarketingRepresentative.DoesNotExist:
                    return JsonResponse(
                        {"success": False, "message": "Marketing Rep not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )
                fabricators = Fabricator.objects.filter(
                    marketing_representative=mar
                ).order_by("marketing_representative__name")
            else:
                fabricators = Fabricator.objects.filter(
                    marketing_representative__isnull=False
                ).order_by("marketing_representative__name")

            paginator = StandardResultsSetPagination()
            # set page size if not set in parameters
            if not request.query_params.get("page_size"):
                paginator.page_size = 20

            result_page = paginator.paginate_queryset(fabricators, request)
            serializer = MarketingRepAndFabricatorSerializer(result_page, many=True)

            return Response(
                {
                    "approved": fabricators.filter(status="approved").count(),
                    "pending": fabricators.filter(status="pending").count(),
                    "rejected": fabricators.filter(status="rejected").count(),
                    "data": paginator.get_paginated_response(serializer.data).data,
                },
                status=status.HTTP_200_OK,
            )

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
            report = Reports.objects.all()

            if from_date and to_date:
                report = report.filter(sales_date__range=(from_date, to_date))

            report = report.order_by("-sales_date")

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

        elif (
            request.query_params.get("view") == "distributor"
            or request.query_params.get("view") == "marketing_representatives"
        ):
            report = Reports.objects.all()

            if from_date and to_date:
                report = report.filter(sales_date__range=(from_date, to_date))

            report = report.order_by("-sales_date")

            paginator = StandardResultsSetPagination()
            result_page = paginator.paginate_queryset(report, request)
            serializer = ReportsSerializer(
                result_page,
                many=True,
                hide_fields=[
                    "fabricator_name",
                    "fabricator_institution",
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
        from_date = request.GET.get("from_date")
        to_date = request.GET.get("to_date")

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
                    report = reports.filter(sales_date__range=(from_date, to_date))
                writer.writerow(
                    [
                        "Fabricator Name",
                        "Institution",
                        "Registration Number",
                        "Phone Number",
                        "District",
                        "Sub-District",
                        "Sales Date",
                        "Distributor Name",
                        "Amount",
                        "Invoice Number",
                    ]
                )

                for report in reports:
                    writer.writerow(
                        [
                            report.fabricator.name,
                            report.fabricator.institution,
                            report.fabricator.registration_number,
                            report.fabricator.phone_number,
                            report.fabricator.district,
                            report.fabricator.sub_district,
                            report.sales_date.strftime("%Y-%m-%d"),
                            report.distributor.name,
                            report.amount,
                            report.invoice_number,
                        ]
                    )

                return response

            # TODO: its actually distributors
            elif (
                request.query_params.get("view") == "marketing_representatives"
                or request.query_params.get("view") == "distributor"
            ):
                reports = Reports.objects.all().order_by("-sales_date")
                if from_date and to_date:
                    reports = reports.filter(sales_date__range=(from_date, to_date))
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

        if request.query_params.get("view") == "marketing-rep-and-fabricator":
            if request.query_params.get("marketing-rep-id"):
                try:
                    mar = MarketingRepresentative.objects.get(
                        id=request.query_params.get("marketing-rep-id")
                    )
                except MarketingRepresentative.DoesNotExist:
                    return JsonResponse(
                        {"success": False, "message": "Marketing Rep not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )
                fabricators = Fabricator.objects.filter(
                    marketing_representative=mar
                ).order_by("marketing_representative__name")

            else:
                fabricators = Fabricator.objects.filter(
                    marketing_representative__isnull=False
                ).order_by("marketing_representative__name")

            serializer = MarketingRepAndFabricatorSerializer(fabricators, many=True)
            writer.writerow(
                [
                    "Marketing Representative",
                    "Phone Number",
                    "Employee ID",
                    "District",
                    "Thana",
                    "email",
                    "Fabricator",
                    "Registration Number",
                    "Institution",
                    "District",
                    "Thana",
                    "Status",
                ]
            )
            for fabricator in serializer.data:
                writer.writerow(
                    [
                        fabricator["marketing_rep_name"],
                        fabricator["marketing_rep_phone_number"],
                        fabricator["employee_id"],
                        fabricator["marketing_rep_district"],
                        fabricator["marketing_rep_sub_district"],
                        fabricator["email"],
                        fabricator["name"],
                        fabricator["registration_number"],
                        fabricator["institution"],
                        fabricator["district"],
                        fabricator["sub_district"],
                        fabricator["status"],
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

            if from_date and to_date:
                # list of months of from date to to_date
                months = []
                from_month = from_date.month
                from_year = from_date.year
                to_month = to_date.month
                to_year = to_date.year

                while (from_year < to_year) or (
                    from_year == to_year and from_month <= to_month
                ):
                    months.append((from_year, from_month))
                    from_month += 1
                    if from_month > 12:
                        from_month = 1
                        from_year += 1

            else:
                # Prepare past 12 months
                now = datetime.now()
                months = [
                    (now - timedelta(days=30 * i)).replace(day=1)
                    for i in range(11, -1, -1)
                ]
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
                            then="amount",
                        ),
                        output_field=IntegerField(),
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
                    **monthly_annotations,
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
                        *[
                            summary.get(f"sales_{year}_{month}", 0)
                            for year, month in months
                        ],
                        summary["total_amount"],
                    ]
                )

            return response

        return JsonResponse(
            {"success": False, "message": "Invalid action parameter."},
            status=status.HTTP_400_BAD_REQUEST,
        )


class SubDistrictView(APIView):
    def get(self, request, *args, **kwargs):
        if request.query_params.get("view") == "districts":
            districts = list(dist_upazila_map.dist_upazila_map.keys())
            formatted_districts = [
                {"id": index, "name": district}
                for index, district in enumerate(districts, start=1)
            ]
            return JsonResponse(
                {"success": True, "districts": formatted_districts},
                status=status.HTTP_200_OK,
            )
        if request.query_params.get("view") == "thanas":
            district_id = request.query_params.get("district-id")
            if not district_id:
                return JsonResponse(
                    {"success": False, "message": "District ID parameter is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                target_district = list(dist_upazila_map.dist_upazila_map.keys())[
                    int(district_id) - 1
                ]
            except (IndexError, ValueError):
                return JsonResponse(
                    {"success": False, "message": "District not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            wanted_upazilas = []
            upazilas_thanas = dist_upazila_map.dist_upazila_map[target_district]

            for index, upazila in enumerate(upazilas_thanas, start=1):
                wanted_upazilas.append(
                    {
                        "id": index,
                        "name": upazila,
                    }
                )

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
