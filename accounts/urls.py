from django.urls import path
from .views import (
    ValidatePhoneView,
    FinancialEntryCreateView
)

urlpatterns = [
    path("validate-phone/", ValidatePhoneView.as_view()),
    path("financial-entry/", FinancialEntryCreateView.as_view()),
]
