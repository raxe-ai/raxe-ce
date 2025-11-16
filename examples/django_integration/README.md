# Django Integration with RAXE

Protect Django applications with RAXE middleware and decorators.

## Setup

1. Add middleware to `settings.py`:

```python
MIDDLEWARE = [
    # ...
    'myapp.middleware.RaxeSecurityMiddleware',
]
```

2. Add views to `urls.py`:

```python
from myapp import views

urlpatterns = [
    path('api/chat/', views.chat_view),
    path('api/protected/', views.protected_view),
]
```

## Features

- Automatic request scanning via middleware
- View-level protection with decorators
- Threat blocking for HIGH/CRITICAL severity
- Scan result logging

## Usage

```bash
# Start Django server
python manage.py runserver

# Test endpoint
curl -X POST http://localhost:8000/api/chat/ \
    -H "Content-Type: application/json" \
    -d '{"message": "Hello"}'
```

## Learn More

- [Django Docs](https://docs.djangoproject.com)
- [RAXE Documentation](https://docs.raxe.ai)
