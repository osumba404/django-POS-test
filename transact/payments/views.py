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

    # Extract receipt if present
    receipt = None
    metadata = stk.get("CallbackMetadata", {}).get("Item", [])
    for item in metadata:
        if item.get("Name") == "MpesaReceiptNumber":
            receipt = item.get("Value")
            break

    if txn:
        if result_code == 0:
            txn.status = 'SUCCESS'
            if receipt:
                txn.mpesa_receipt_number = receipt
            txn.save(update_fields=['status', 'mpesa_receipt_number', 'updated_at'])
        else:
            txn.status = 'FAILED'
            txn.save(update_fields=['status', 'updated_at'])

    return HttpResponse(status=200)

def transactions_list(request):
    transactions = Transaction.objects.order_by('-created_at')
    return render(request, 'payments/transactions_list.html', {"transactions": transactions})
