import json
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST, require_GET, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from django.conf import settings
from .models import Payment
from .services.mpesa import MpesaDarajaClient

@require_http_methods(["GET", "POST"])
def mpesa_initiate(request):
    if request.method == "GET":
        return render(request, "payments/mpesa_initiate.html")

    # POST: process form submission
    amount = request.POST.get('amount')
    phone = request.POST.get('phone')
    if not amount or not phone:
        return render(request, "payments/mpesa_initiate.html", {"error": "amount and phone are required"})

    try:
        amount_val = float(amount)
    except ValueError:
        return render(request, "payments/mpesa_initiate.html", {"error": "amount must be a number"})

    payment = Payment.objects.create(
        provider=Payment.Provider.MPESA,
        phone_number=str(phone),
        amount=amount_val,
        status=Payment.Status.PROCESSING,
    )

    client = MpesaDarajaClient(
        env=getattr(settings, 'MPESA_ENV', 'sandbox'),
        consumer_key=getattr(settings, 'MPESA_CONSUMER_KEY', ''),
        consumer_secret=getattr(settings, 'MPESA_CONSUMER_SECRET', ''),
        shortcode=getattr(settings, 'MPESA_SHORTCODE', ''),
        passkey=getattr(settings, 'MPESA_PASSKEY', ''),
        callback_url=getattr(settings, 'MPESA_CALLBACK_URL', ''),
        account_reference=getattr(settings, 'MPESA_ACCOUNT_REFERENCE', 'ACCOUNT'),
        transaction_desc=getattr(settings, 'MPESA_TRANSACTION_DESC', 'Payment'),
    )

    context = {"payment": payment, "result": None, "error": None}
    try:
        resp = client.stk_push(phone=str(phone), amount=amount_val)
        payment.merchant_request_id = resp.get('MerchantRequestID')
        payment.checkout_request_id = resp.get('CheckoutRequestID')
        if 'errorCode' in resp:
            payment.status = Payment.Status.FAILED
            payment.result_code = resp.get('errorCode')
            payment.result_desc = resp.get('errorMessage')
        payment.save()
        context["result"] = json.dumps({
            'payment_id': str(payment.id),
            'provider': payment.provider,
            'status': payment.status,
            'merchant_request_id': payment.merchant_request_id,
            'checkout_request_id': payment.checkout_request_id,
            'raw': resp,
        }, indent=2)
    except Exception as e:
        payment.status = Payment.Status.FAILED
        payment.result_desc = str(e)
        payment.save()
        context["error"] = str(e)

    return render(request, "payments/mpesa_initiate.html", context)

@csrf_exempt
@require_POST
def mpesa_callback(request):
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return HttpResponseBadRequest('Invalid JSON')

    body = payload.get('Body', {})
    stk = body.get('stkCallback', {})
    merchant_request_id = stk.get('MerchantRequestID')
    checkout_request_id = stk.get('CheckoutRequestID')
    result_code = str(stk.get('ResultCode')) if 'ResultCode' in stk else None
    result_desc = stk.get('ResultDesc')

    payment = Payment.objects.filter(checkout_request_id=checkout_request_id).first() or \
              Payment.objects.filter(merchant_request_id=merchant_request_id).first()

    if not payment:
        return JsonResponse({'status': 'ignored'})

    payment.raw_callback = payload
    payment.result_code = result_code
    payment.result_desc = result_desc

    if result_code == '0':
        payment.status = Payment.Status.SUCCESS
    else:
        payment.status = Payment.Status.FAILED

    payment.save()
    return JsonResponse({'status': payment.status})

@require_GET
def payment_status(request, payment_id):
    try:
        payment = Payment.objects.get(id=payment_id)
    except Payment.DoesNotExist:
        return render(request, "payments/payment_status.html", {"not_found": True}, status=404)

    return render(request, "payments/payment_status.html", {"payment": payment})
