import json
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import Payment
from .services.mpesa import MpesaDarajaClient

@require_POST
def initiate_mpesa_stk(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return HttpResponseBadRequest('Invalid JSON')

    amount = data.get('amount')
    phone = data.get('phone')
    if not amount or not phone:
        return HttpResponseBadRequest('amount and phone are required')

    payment = Payment.objects.create(
        provider=Payment.Provider.MPESA,
        phone_number=str(phone),
        amount=amount,
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

    try:
        resp = client.stk_push(phone=str(phone), amount=float(amount))
        payment.merchant_request_id = resp.get('MerchantRequestID')
        payment.checkout_request_id = resp.get('CheckoutRequestID')
        # On immediate error, API returns errorCode/errorMessage
        if 'errorCode' in resp:
            payment.status = Payment.Status.FAILED
            payment.result_code = resp.get('errorCode')
            payment.result_desc = resp.get('errorMessage')
        payment.save()
        return JsonResponse({
            'payment_id': str(payment.id),
            'provider': payment.provider,
            'status': payment.status,
            'merchant_request_id': payment.merchant_request_id,
            'checkout_request_id': payment.checkout_request_id,
            'raw': resp,
        })
    except Exception as e:
        payment.status = Payment.Status.FAILED
        payment.result_desc = str(e)
        payment.save()
        return JsonResponse({'error': str(e)}, status=500)

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
        # Unknown callback, accept but note
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
        return JsonResponse({'error': 'not found'}, status=404)

    return JsonResponse({
        'payment_id': str(payment.id),
        'provider': payment.provider,
        'amount': float(payment.amount),
        'currency': payment.currency,
        'status': payment.status,
        'result_code': payment.result_code,
        'result_desc': payment.result_desc,
        'created_at': payment.created_at.isoformat(),
        'updated_at': payment.updated_at.isoformat(),
    })
