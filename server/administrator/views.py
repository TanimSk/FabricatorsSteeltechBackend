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
from utils.email_handler import send_login_credentials


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


class FabricatorView(APIView):
    permission_classes = [AuthenticateOnlyAdmin]

    def get(self, request, *args, **kwargs):
        if request.query_params.get("id"):
            fabricator_id = request.query_params.get("id")
            try:
                fabricator = Fabricator.objects.get(id=fabricator_id)
                serializer = FabricatorSerializer(fabricator)
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
            fabricators = Fabricator.objects.filter(status="approved").order_by(
                "-created_at"
            )
        elif request.query_params.get("view") == "rejected":
            fabricators = Fabricator.objects.filter(status="rejected").order_by(
                "-created_at"
            )
        elif request.query_params.get("view") == "all":
            fabricators = Fabricator.objects.all().order_by("-created_at")

        else:
            return JsonResponse(
                {"success": False, "message": "Invalid view parameter."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        paginator = StandardResultsSetPagination()
        result_page = paginator.paginate_queryset(fabricators, request)
        serializer = FabricatorSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    def patch(self, request, *args, **kwargs):
        fabricator_id = request.data.get("id")
        fstatus = request.data.get("status")
        if not fabricator_id or not fstatus:
            return JsonResponse(
                {"success": False, "message": "ID and status parameters are required."},
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
        serializer = FabricatorSerializer(fabricator)
        return JsonResponse(
            {
                "success": True,
                "message": "Fabricator status updated successfully.",
                **serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class MarketingRepresentativeView(APIView):
    permission_classes = [AuthenticateOnlyAdmin]

    def get(self, request, *args, **kwargs):
        if request.query_params.get("id"):
            rep_id = request.query_params.get("id")
            try:
                rep = MarketingRepresentative.objects.get(id=rep_id)
                serializer = MarketingRepresentativeSerializer(rep)
                return Response(serializer.data, status=status.HTTP_200_OK)
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
        serializer = MarketingRepresentativeSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):

            # create a new user for the marketing representative with password
            User = get_user_model()
            random_password = get_random_string(length=6)
            user_instance = User.objects.create_user(
                username=serializer.validated_data["email"],
                password=random_password,
                email=serializer.validated_data["email"],
                first_name=serializer.validated_data["name"],
                is_student=True,
            )

            serializer.save(marketing_rep=user_instance)

            # send email to the marketing representative with login credentials
            send_login_credentials(
                username=serializer.validated_data["name"],
                email=serializer.validated_data["email"],
                password=random_password,
            )

            return Response(serializer.data, status=status.HTTP_201_CREATED)

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
            rep.delete()
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

        print(response.text)

        return Response(
            {
                "success": True,
                **response.json(),
            },
            status=status.HTTP_201_CREATED,
        )
