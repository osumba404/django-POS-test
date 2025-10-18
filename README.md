# django-POS-test

Monolithic Django starter with a pluggable `payments/` app.

Implements M-Pesa (Daraja) STK Push end-to-end and ships placeholders for Stripe, PayPal, and Amazon Pay.

## Features

- **M-Pesa STK Push**: initiate, callback, and status endpoints.
- **Extensible providers**: placeholders for `Stripe`, `PayPal`, `Amazon Pay` under `payments/services/`.
- **Environment-based config** using `.env` (see `.env.example`).

## Project layout

- **`pos_project/`**: Django project settings and URLs.
- **`payments/`**: app with `Payment` model, admin, URLs, views, and provider services.
- **`payments/services/mpesa.py`**: Daraja client for STK Push.
- **`payments/services/{stripe,paypal,amazon}.py`**: placeholders for future integrations.

## Requirements

- Python 3.10+
- Django 5.x

Install Python deps:

```bash
pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` and fill values:

```env
SECRET_KEY=change-me
DEBUG=1
ALLOWED_HOSTS=*

# M-Pesa (Daraja)
MPESA_ENV=sandbox
MPESA_CONSUMER_KEY=your_consumer_key
MPESA_CONSUMER_SECRET=your_consumer_secret
MPESA_SHORTCODE=174379            # Example for sandbox PayBill
MPESA_PASSKEY=your_lipa_na_mpesa_online_passkey
MPESA_CALLBACK_URL=https://<your-domain>/payments/mpesa/callback/
MPESA_ACCOUNT_REFERENCE=ACCOUNT
MPESA_TRANSACTION_DESC=Payment
```

Notes:

- For local testing without a public URL, use a tunnel like `ngrok` to expose `/payments/mpesa/callback/`.
- `MPESA_ENV` accepts `sandbox` or `production`.

## Database and run

```bash
python manage.py migrate
python manage.py createsuperuser   # optional
python manage.py runserver 0.0.0.0:8000
```

## Endpoints

- **Initiate M-Pesa STK**: `POST /payments/mpesa/initiate/`

  Request body:
  ```json
  { "amount": 10, "phone": "2547XXXXXXXX" }
  ```

  Response:
  ```json
  {
    "payment_id": "<uuid>",
    "provider": "mpesa",
    "status": "processing|failed",
    "merchant_request_id": "...",
    "checkout_request_id": "...",
    "raw": { "...": "Daraja response" }
  }
  ```

- **Daraja callback (POST by Safaricom)**: `POST /payments/mpesa/callback/`

  Body shape (example):
  ```json
  {
    "Body": {
      "stkCallback": {
        "MerchantRequestID": "...",
        "CheckoutRequestID": "...",
        "ResultCode": 0,
        "ResultDesc": "The service request is processed successfully.",
        "CallbackMetadata": { "Item": [ {"Name": "MpesaReceiptNumber", "Value": "..."} ] }
      }
    }
  }
  ```

  The app updates the `Payment` record status to `success` when `ResultCode == 0`, otherwise `failed`.

- **Check status**: `GET /payments/<payment_id>/status/`

  Response:
  ```json
  {
    "payment_id": "<uuid>",
    "provider": "mpesa",
    "amount": 10.0,
    "currency": "KES",
    "status": "pending|processing|success|failed|cancelled",
    "result_code": "0",
    "result_desc": "...",
    "created_at": "...",
    "updated_at": "..."
  }
  ```

## How to obtain Daraja credentials (M-Pesa)

- **Create a Safaricom Developer account**: https://developer.safaricom.co.ke/
- **Create an app** and obtain `Consumer Key` and `Consumer Secret`.
- **Get Lipa Na M-Pesa Online (LNMO) Passkey** from your app settings.
- **Shortcode**:
  - Sandbox PayBill: use `174379` (or your assigned one).
  - Production: your PayBill/Till number.
- **Whitelist callback URL** if required by your account settings.

## Provider placeholders

- **Stripe**: `payments/services/stripe.py` contains a `StripeClient` stub.
- **PayPal**: `payments/services/paypal.py` contains a `PayPalClient` stub.
- **Amazon Pay**: `payments/services/amazon.py` contains an `AmazonPayClient` stub.

You can implement these by following the `MpesaDarajaClient` pattern and adding new endpoints in `payments/urls.py` and handlers in `payments/views.py`.

## cURL examples

Initiate STK:

```bash
curl -X POST http://localhost:8000/payments/mpesa/initiate/ \
  -H "Content-Type: application/json" \
  -d '{"amount": 10, "phone": "2547XXXXXXXX"}'
```

Check status:

```bash
curl http://localhost:8000/payments/<payment_id>/status/
```

## Admin

- Visit `/admin/` to view `Payment` records. Login with your superuser.