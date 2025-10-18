from django.http import JsonResponse

def index(request):
    return JsonResponse({
        "message": "Django POS Payments API",
        "endpoints": {
            "admin": "/admin/",
            "mpesa_initiate": "/payments/mpesa/initiate/",
            "mpesa_callback": "/payments/mpesa/callback/",
            "payment_status": "/payments/<payment_id>/status/",
        }
    })
