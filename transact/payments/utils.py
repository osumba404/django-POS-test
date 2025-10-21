import requests
from django.conf import settings
from requests.auth import HTTPBasicAuth

def get_access_token():
    url = f"{settings.MPESA_BASE_URL}/oauth/v1/generate?grant_type=client_credentials"
    response = requests.get(
        url,
        auth=HTTPBasicAuth(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET),
        headers={"Accept": "application/json"},
        timeout=30,
    )
    # Ensure we have a successful response and valid JSON
    if response.status_code != 200:
        raise Exception(
            f"MPESA OAuth error: status={response.status_code}, body={response.text}"
        )
    try:
        data = response.json()
    except Exception:
        raise Exception(
            f"MPESA OAuth returned non-JSON body: status={response.status_code}, body={response.text}"
        )
    if "access_token" not in data:
        raise Exception(
            f"MPESA OAuth JSON missing access_token: {data}"
        )
    return data["access_token"]
