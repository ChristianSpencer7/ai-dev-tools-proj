"""API routes. Paths match openapi.yaml exactly, with no trailing slashes."""

from django.urls import path

from leaderboard import views

urlpatterns = [
    path("health", views.health, name="health"),
]
