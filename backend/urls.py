"""
URL configuration for backend project.
"""

from django.contrib import admin
from django.urls import include, path

from accounts.views import (
    credit_cards_page,
    dashboard_page,
    fixed_expenses_page,
    fixed_incomes_page,
    landing_page,
    login_page,
    logout_page,
    profile_page,
    reserves_page,
    trips_page,
    transactions_page,
    vehicles_page,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("accounts.urls")),
    path("", landing_page),
    path("login/", login_page),
    path("dashboard/", dashboard_page),
    path("logout/", logout_page),
    path("transactions/", transactions_page),
    path("fixed-expenses/", fixed_expenses_page),
    path("fixed-incomes/", fixed_incomes_page),
    path("reserves/", reserves_page),
    path("vehicles/", vehicles_page),
    path("trips/", trips_page),
    path("credit-cards/", credit_cards_page),
    path("profile/", profile_page),
]
