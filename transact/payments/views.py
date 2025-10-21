from django.shortcuts import render

# Create your views here.
import requests
import datetime
import base64
from django.http import JsonResponse
from django.conf import settings
from .utils import get_access_token
from .models import Transaction

def initiate_stk_push(request):
    if request.method == 'GET':
        return render(request, 'payments/stk_push.html')

    # POST flow: read inputs and initiate STK push
    phone_number = request.POST.get('phone_number', '').strip()
    amount_str = request.POST.get('amount', '1').strip()
    context = {"phone_number": phone_number, "amount": amount_str}

    # Basic validation
    try:
        amount = int(float(amount_str))
    except ValueError:
        context.update({"error": "Amount must be a number."})
        return render(request, 'payments/stk_push.html', context)

    if not phone_number:
        context.update({"error": "Phone number is required in MSISDN format e.g. 2547XXXXXXXX."})
        return render(request, 'payments/stk_push.html', context)

    try:
        access_token = get_access_token()
    except Exception as e:
        context.update({"error": "Failed to obtain MPESA access token", "details": str(e)})
        return render(request, 'payments/stk_push.html', context)

    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    password_str = settings.MPESA_SHORTCODE + settings.MPESA_PASSKEY + timestamp
    password = base64.b64encode(password_str.encode()).decode('utf-8')

    # Create a pending transaction record
    txn = Transaction.objects.create(
        phone_number=phone_number,
        amount=amount,
        status='PENDING',
    )

    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone_number,
        "PartyB": settings.MPESA_SHORTCODE,
        "PhoneNumber": phone_number,
        "CallBackURL": settings.MPESA_CALLBACK_URL,
        "AccountReference": "Transact Demo",
        "TransactionDesc": "Testing STK Push"
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            f"{settings.MPESA_BASE_URL}/mpesa/stkpush/v1/processrequest",
            json=payload,
            headers=headers,
            timeout=30,
        )
    except Exception as e:
        txn.status = 'FAILED'
        txn.save(update_fields=['status', 'updated_at'])
        context.update({"error": "Failed to reach MPESA STK API", "details": str(e)})
        return render(request, 'payments/stk_push.html', context)

    context.update({"mpesa_status": response.status_code})
    # Try to parse response JSON; if not, include text
    try:
        body = response.json()
        context.update({"mpesa_body": body})
    except Exception:
        context.update({"mpesa_body_text": response.text})

    # Handle STK response semantics
    if response.status_code == 200 and isinstance(context.get('mpesa_body'), dict):
        body = context['mpesa_body']
        # Success acceptance code from Daraja is usually ResponseCode == "0"
        if str(body.get('ResponseCode')) == '0':
            # Save CheckoutRequestID for correlating callback
            checkout_id = body.get('CheckoutRequestID')
            if checkout_id:
                txn.checkout_request_id = checkout_id
                txn.save(update_fields=['checkout_request_id', 'updated_at'])
            context.update({
                "accepted": True,
                "message": "STK Push sent. Enter your M-PESA PIN on your phone to authorize. This page will not auto-update; check Transactions for final status after callback.",
            })
        else:
            txn.status = 'FAILED'
            txn.save(update_fields=['status', 'updated_at'])
            context.update({
                "error": body.get('errorMessage') or "STK Push was not accepted",
                "details": body,
            })
    else:
        txn.status = 'FAILED'
        txn.save(update_fields=['status', 'updated_at'])

    return render(request, 'payments/stk_push.html', context)



from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
import json

@csrf_exempt
def stk_callback(request):
    data = json.loads(request.body.decode('utf-8'))
    print("Callback data:", data)
    stk = data.get("Body", {}).get("stkCallback", {})
    result_code = stk.get("ResultCode")
    checkout_id = stk.get("CheckoutRequestID")

    # Find matching transaction by checkout_request_id
    txn = None
    if checkout_id:
        try:
            txn = Transaction.objects.get(checkout_request_id=checkout_id)
        except Transaction.DoesNotExist:
            txn = None

    # Extract metadata: receipt, phone, amount if present
    receipt = None
    phone_meta = None
    amount_meta = None
    metadata = stk.get("CallbackMetadata", {}).get("Item", [])
    for item in metadata:
        name = item.get("Name")
        if name == "MpesaReceiptNumber":
            receipt = item.get("Value")
        elif name == "PhoneNumber":
            phone_meta = str(item.get("Value")) if item.get("Value") is not None else None
        elif name in ("Amount", "TransactionAmount"):
            amount_meta = item.get("Value")

    # Fallback: if no txn found by checkout_id, match latest pending by phone
    if txn is None and phone_meta:
        try:
            txn = Transaction.objects.filter(phone_number=phone_meta, status='PENDING').order_by('-created_at').first()
        except Exception:
            txn = None

    # Normalize result code comparison
    result_ok = str(result_code) == '0'

    if txn:
        if result_ok:
            txn.status = 'SUCCESS'
            if receipt:
                txn.mpesa_receipt_number = receipt
            # Optionally update amount from callback
            try:
                if amount_meta is not None:
                    # keep as Decimal by casting via str
                    from decimal import Decimal
                    txn.amount = Decimal(str(amount_meta))
            except Exception:
                pass
            txn.save(update_fields=['status', 'mpesa_receipt_number', 'amount', 'updated_at'])
        else:
            txn.status = 'FAILED'
            txn.save(update_fields=['status', 'updated_at'])

    return HttpResponse(status=200)

def transactions_list(request):
    transactions = Transaction.objects.order_by('-created_at')
    return render(request, 'payments/transactions_list.html', {"transactions": transactions})

def callback_test(request):
    return HttpResponse("OK", status=200)

def query_stk_status(request, txn_id):
    try:
        txn = Transaction.objects.get(id=txn_id)
    except Transaction.DoesNotExist:
        return render(request, 'payments/transactions_list.html', {
            "transactions": Transaction.objects.order_by('-created_at'),
            "error": f"Transaction {txn_id} not found"
        })

    if not txn.checkout_request_id:
        return render(request, 'payments/transactions_list.html', {
            "transactions": Transaction.objects.order_by('-created_at'),
            "error": "Cannot query status: missing CheckoutRequestID on this transaction."
        })

    try:
        access_token = get_access_token()
    except Exception as e:
        return render(request, 'payments/transactions_list.html', {
            "transactions": Transaction.objects.order_by('-created_at'),
            "error": "Failed to obtain MPESA access token",
            "details": str(e),
        })

    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    password_str = settings.MPESA_SHORTCODE + settings.MPESA_PASSKEY + timestamp
    password = base64.b64encode(password_str.encode()).decode('utf-8')

    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "CheckoutRequestID": txn.checkout_request_id,
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    try:
        resp = requests.post(
            f"{settings.MPESA_BASE_URL}/mpesa/stkpushquery/v1/query",
            json=payload,
            headers=headers,
            timeout=30,
        )
    except Exception as e:
        return render(request, 'payments/transactions_list.html', {
            "transactions": Transaction.objects.order_by('-created_at'),
            "error": "Failed to reach MPESA STK Query API",
            "details": str(e),
        })

    body = None
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text}

    # Heuristic: if query ResultCode == 0 then success; specific messages may vary
    result_code = str(body.get('ResultCode')) if isinstance(body, dict) else None
    result_desc = body.get('ResultDesc') if isinstance(body, dict) else None
    if result_code == '0':
        txn.status = 'SUCCESS'
        txn.save(update_fields=['status', 'updated_at'])
        message = "Payment confirmed SUCCESS by query."
    elif result_code in {'1032', '2001', '1', '2'}:
        # Common non-success codes; mark as FAILED to unblock
        txn.status = 'FAILED'
        txn.save(update_fields=['status', 'updated_at'])
        message = f"Payment marked FAILED by query (code {result_code})."
    else:
        message = f"Query returned status code {resp.status_code}. Still pending or unknown."

    return render(request, 'payments/transactions_list.html', {
        "transactions": Transaction.objects.order_by('-created_at'),
        "query_result": body,
        "message": message,
        "mpesa_status": resp.status_code,
    })
