import base64
import datetime as dt
import requests

class MpesaDarajaClient:
    def __init__(self, env, consumer_key, consumer_secret, shortcode, passkey, callback_url, account_reference, transaction_desc):
        self.env = env
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.shortcode = shortcode
        self.passkey = passkey
        self.callback_url = callback_url
        self.account_reference = account_reference
        self.transaction_desc = transaction_desc

        self.base_url = 'https://sandbox.safaricom.co.ke' if env == 'sandbox' else 'https://api.safaricom.co.ke'

    def _access_token(self):
        url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
        resp = requests.get(url, auth=(self.consumer_key, self.consumer_secret), timeout=30)
        resp.raise_for_status()
        return resp.json().get('access_token')

    def _timestamp(self):
        return dt.datetime.now().strftime('%Y%m%d%H%M%S')

    def _password(self, timestamp):
        raw = f"{self.shortcode}{self.passkey}{timestamp}".encode('utf-8')
        return base64.b64encode(raw).decode('utf-8')

    def stk_push(self, phone: str, amount: float):
        token = self._access_token()
        timestamp = self._timestamp()
        password = self._password(timestamp)

        url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {
            "BusinessShortCode": int(self.shortcode),
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(round(amount)),
            "PartyA": phone,
            "PartyB": int(self.shortcode),
            "PhoneNumber": phone,
            "CallBackURL": self.callback_url,
            "AccountReference": self.account_reference,
            "TransactionDesc": self.transaction_desc,
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        # Do not raise for status to capture error payloads from API
        try:
            data = resp.json()
        except Exception:
            resp.raise_for_status()
        return data
