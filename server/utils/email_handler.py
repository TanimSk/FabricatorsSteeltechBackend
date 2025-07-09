from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from rest_framework.views import exception_handler
from django.shortcuts import render
import threading
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from server.settings import DEFAULT_FROM_EMAIL
from django.template.loader import render_to_string
from weasyprint import HTML


# This function is used to send HTML emails with optional attachments.
class EmailThread(threading.Thread):
    def __init__(
        self, subject, html_content, recipient_list, sender, images=None, pdfs=None
    ):
        self.subject = subject
        self.recipient_list = recipient_list
        self.html_content = html_content
        self.sender = sender
        self.images = images
        self.pdfs = pdfs
        threading.Thread.__init__(self)

    def run(self):
        if not self.recipient_list:
            print("No recipient list provided. Email not sent.")
            return
        msg = EmailMessage(self.subject, None, self.sender, self.recipient_list)

        # Attaching images
        if self.images is not None:
            for image in self.images:
                if isinstance(image, tuple):
                    attachment_name, attachment_content, attachment_mime_type = image
                    msg.attach(
                        attachment_name, attachment_content, attachment_mime_type
                    )

        # Attaching PDFs
        if self.pdfs is not None:
            for pdf in self.pdfs:
                pdf_data = HTML(string=pdf["content"]).write_pdf()
                msg.attach(pdf["name"], pdf_data, "application/pdf")

        msg.content_subtype = "html"
        msg.body = self.html_content
        msg.send()
        print("Email sent successfully!")


def send_html_mail(
    subject, html_content, recipient_list, sender, images=None, pdfs=None
):
    EmailThread(subject, html_content, recipient_list, sender, images, pdfs).start()


def send_login_credentials(
    username: str,
    email: str,
    password: str,
):

    html_content = render_to_string(
        "login_credentials.html",
        {
            "user_name": username,
            "user_email": email,
            "user_password": password,
        },
    )
    subject = "Your login credentials - Steeltech"

    EmailThread(
        subject,
        html_content,
        [email],
        DEFAULT_FROM_EMAIL,
    ).start()


def send_marketing_rep_assigned_notification(
    user_name: str,
    fab_name: str,
    fab_phone_number: str,
    fab_registration_number: str,
    fab_district: str,
    fab_sub_district: str,
    marketing_rep_email: str,
):
    html_content = render_to_string(
        "fabricator_assigned.html",
        {
            "user_name": user_name,
            "fab_name": fab_name,
            "fab_phone_number": fab_phone_number,
            "fab_registration_number": fab_registration_number,
            "fab_district": fab_district,
            "fab_sub_district": fab_sub_district,
        },
    )
    subject = "New Fabricator Assigned - Steeltech"

    EmailThread(
        subject,
        html_content,
        [marketing_rep_email],
        DEFAULT_FROM_EMAIL,
    ).start()


def send_marketing_rep_report_task(
    marketing_rep_name: str,
    marketing_rep_email: str,
    description: str,
):
    html_content = render_to_string(
        "tasks_provided.html",
        {
            "marketing_rep_name": marketing_rep_name,
            "description": description,
        },
    )
    subject = "New Task Assigned - Steeltech"

    EmailThread(
        subject,
        html_content,
        [marketing_rep_email],
        DEFAULT_FROM_EMAIL,
    ).start()


def fab_registered_notification(
    fab_name: str,
    fab_phone_number: str,
    fab_registration_number: str,
    fab_district: str,
    fab_sub_district: str,
):
    html_content = render_to_string(
        "fabricator_registered.html",
        {
            "fab_name": fab_name,
            "fab_phone_number": fab_phone_number,
            "fab_registration_number": fab_registration_number,
            "fab_district": fab_district,
            "fab_sub_district": fab_sub_district,
        },
    )
    subject = "New Fabricator Registered - Steeltech"

    EmailThread(
        subject,
        html_content,
        [
            "ridwan@ongshak.com",
            "sktanim5800+admin@gmail.com",
        ],
        DEFAULT_FROM_EMAIL,
    ).start()


def fab_status_change_notification(
    fab_name: str,
    market_rep_name: str,
    phone_number: str,
    registration_number: str,
    status: str,
    date: str,
    fab_email: str,
    marketing_rep_email: str = None,
):
    if status not in ["approved", "rejected"]:
        return

    if fab_email:
        # send to fabricator
        html_content = render_to_string(
            "fabricator_status.html",
            {
                "name": fab_name,
                "fab_name": fab_name,
                "phone_number": phone_number,
                "registration_number": registration_number,
                "status": status,
                "date": date,
            },
        )
        subject = "Status update - Steeltech"
        EmailThread(
            subject,
            html_content,
            [fab_email],
            DEFAULT_FROM_EMAIL,
        ).start()

    if marketing_rep_email:
        # send to marketing representative
        html_content = render_to_string(
            "fabricator_status.html",
            {
                "name": market_rep_name,
                "fab_name": fab_name,
                "phone_number": phone_number,
                "registration_number": registration_number,
                "status": status,
                "date": date,
            },
        )
        subject = "Fabricator Status Update - Steeltech"
        EmailThread(
            subject,
            html_content,
            [marketing_rep_email],
            DEFAULT_FROM_EMAIL,
        ).start()
