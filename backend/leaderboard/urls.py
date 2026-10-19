"""API routes. Paths match openapi.yaml exactly, with no trailing slashes."""

from django.urls import path

from leaderboard import views

urlpatterns = [
    path("health", views.health, name="health"),
    path("families", views.families, name="families"),
    # Listed before families/<id>; <int:...> wouldn't match "join" anyway, but the order makes that obvious.
    path("families/join", views.join_family, name="join-family"),
    path("families/<int:family_id>", views.family_detail, name="family-detail"),
    path("families/<int:family_id>/members", views.family_members, name="family-members"),
    path("members/<int:member_id>/steps", views.member_steps, name="member-steps"),
    path("steps", views.log_steps, name="log-steps"),
]
