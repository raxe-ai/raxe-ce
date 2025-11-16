"""Django Middleware for RAXE Security

Add to MIDDLEWARE in settings.py:
    'myapp.middleware.RaxeSecurityMiddleware',
"""
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from raxe import Raxe
import json

# Initialize RAXE once
raxe = Raxe(telemetry=True)

class RaxeSecurityMiddleware(MiddlewareMixin):
    """Automatically scan all POST/PUT/PATCH requests."""

    def process_request(self, request):
        """Scan request before view processing."""
        # Only scan mutation requests
        if request.method in ['POST', 'PUT', 'PATCH']:
            # Skip admin and other safe endpoints
            if request.path.startswith('/admin/'):
                return None

            # Extract body
            try:
                if request.content_type == 'application/json':
                    body = json.loads(request.body)
                    text = str(body)  # Scan entire JSON

                    # Scan
                    result = raxe.scan(text, block_on_threat=False)

                    # Store in request for logging
                    request.raxe_scan = result

                    # Block high/critical threats
                    if result.has_threats and result.severity in ['HIGH', 'CRITICAL']:
                        return JsonResponse({
                            'error': 'Security threat detected',
                            'severity': result.severity,
                            'message': 'Request blocked by security policy'
                        }, status=400)

            except Exception as e:
                # Don't block on scan failures
                pass

        return None
