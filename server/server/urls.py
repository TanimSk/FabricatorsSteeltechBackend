"""
URL configuration for xylem_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from dj_rest_auth.registration.views import VerifyEmailView
from rest_framework_simplejwt.views import TokenVerifyView
from dj_rest_auth.views import (
    PasswordResetConfirmView,
    PasswordResetView,
    PasswordChangeView,
)
from django.views.generic import TemplateView
from administrator.auth_views import LoginWthPermission, CustomPasswordChangeView
from administrator.views import UploadFile, SubDistrictView


urlpatterns = [
    path("admin/", admin.site.urls),
    # ---------- Auth ------------
    path("rest-auth/login/", LoginWthPermission.as_view(), name="login_view"),
    # Password Change
    path(
        "rest-auth/password/change/",
        CustomPasswordChangeView.as_view(),
        name="password_change",
    ),
    path("rest-auth/", include("dj_rest_auth.urls")),
    path(
        "rest-auth/registration/account-confirm-email/",
        VerifyEmailView.as_view(),
        name="account_email_verification_sent",
    ),
    path("rest-auth/registration/", include("dj_rest_auth.registration.urls")),
    # Password Reset
    path(
        "rest-auth/password/reset/", PasswordResetView.as_view(), name="password_reset"
    ),
    path(
        "rest-auth/password/reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="rest_password_reset_confirm",
    ),
    path(
        "rest-auth/password/reset/confirm/<str:uidb64>/<str:token>",
        TemplateView.as_view(),
        name="password_reset_confirm",
    ),
    path("get-access-token/", TokenRefreshView.as_view(), name="get-access-token"),
    path("api/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    # ---------- Apps ------------
    path("administrator/", include("administrator.urls")),
    path("fabricator/", include("fabricator.urls")),
    path("marketing-rep/", include("marketing_rep.urls")),
    path("distributor/", include("distributor.urls")),
    # ---------- File Upload ------------
    path("upload-file/", UploadFile.as_view(), name="upload_file"),
    # ---------- District and Sub-District Data ------------
    path("districts/", SubDistrictView.as_view(), name="sub_district_view"),
]
