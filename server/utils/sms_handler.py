import requests
import json
from django.conf import settings

USE_CLOUDSMSBD = True


def send_otp_via_sms_cloudsms(recipient_number, otp_code):
    if not USE_CLOUDSMSBD:
        return send_sms_via_bulksmsbd(
            recipient_number,
            f"Greetings from Up&Pro, your OTP is {otp_code}, OTP is valid for 10 minutes.",
        )
    else:
        return send_sms_via_cloudsms(
            recipient_number,
            f"Greetings from Up&Pro, your OTP is {otp_code}, OTP is valid for 10 minutes.",
        )


def send_sms_via_cloudsms(recipient_number, message):
    if not USE_CLOUDSMSBD:
        return send_sms_via_bulksmsbd(recipient_number, message)

    API_KEY = settings.CLOUDSMSBD_API_KEY
    url = f"https://api.cloudsmsbd.com/sms/?key={API_KEY}"
    headers = {"Content-Type": "application/json"}
    data = {
        "message": message,
        "recipient": recipient_number,
    }
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        print(response.text, response.status_code)
        if response.status_code != 201:
            return {
                "success": False,
            }
        return response.json()
    except requests.RequestException as e:
        return {
            "success": False,
        }


# Bulksmsbd API
def send_otp_via_bulksmsbd(recipient_number, otp_code):
    return send_sms_via_bulksmsbd(
        recipient_number,
        f"Greetings from Up&Pro, your OTP is {otp_code}, OTP is valid for 10 minutes.",
    )


def send_sms_via_bulksmsbd(recipient_number, message):
    url = "http://bulksmsbd.net/api/smsapi"
    api_key = settings.BULK_SMS_API_KEY
    senderid = "8809617613088"
    number = recipient_number

    data = {
        "api_key": api_key,
        "senderid": senderid,
        "number": number,
        "message": message,
    }

    try:
        response = requests.post(
            url, data=data, verify=False
        )  # verify=False to ignore SSL warnings
        print(response.text, response.status_code)

        if response.status_code == 200:
            response_data = response.json()
            return {
                "success": True,
                "message": response_data.get("success_message", ""),
            }
        else:
            return {
                "success": False,
            }

    except requests.RequestException as e:
        return {
            "success": False,
            "error": str(e),
        }
