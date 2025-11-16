"""Django Views with RAXE Protection"""
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from raxe import Raxe, SecurityException
import json

raxe = Raxe()

@csrf_exempt
@require_http_methods(["POST"])
def chat_view(request):
    """Chat endpoint with automatic RAXE scanning via middleware."""
    try:
        data = json.loads(request.body)
        message = data.get('message', '')

        # Process message (simulate LLM)
        response = f"Echo: {message}"

        # Include scan result if available
        scan_info = {}
        if hasattr(request, 'raxe_scan'):
            scan = request.raxe_scan
            scan_info = {
                'scanned': True,
                'threats_detected': scan.has_threats,
                'severity': scan.severity if scan.has_threats else 'NONE'
            }

        return JsonResponse({
            'response': response,
            'scan_result': scan_info
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def protected_view(request):
    """View with decorator-based protection."""
    try:
        data = json.loads(request.body)
        prompt = data.get('prompt', '')

        @raxe.protect(block=True)
        def generate(text: str) -> str:
            return f"Generated: {text}"

        try:
            result = generate(prompt)
            return JsonResponse({'result': result})
        except SecurityException as e:
            return JsonResponse({
                'error': 'Security threat detected',
                'severity': e.result.severity
            }, status=400)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
