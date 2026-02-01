from django.urls import path
from .views import (
    ValidatePhoneView,
    FinancialEntryCreateView,
    PhoneLoginView, DashboardView
)

urlpatterns = [
    path("validate-phone/", ValidatePhoneView.as_view()),
    path("financial-entry/", FinancialEntryCreateView.as_view()),
        path("login/", PhoneLoginView.as_view()),
    path("dashboard/", DashboardView.as_view()),
    
]
