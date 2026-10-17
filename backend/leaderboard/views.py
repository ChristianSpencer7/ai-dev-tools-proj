from django.db import connection
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response


@api_view(["GET"])
def health(request: Request) -> Response:
    """Liveness check: the backend is up and can reach the database."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return Response({"ok": True})
