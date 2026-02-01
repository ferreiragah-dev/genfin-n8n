from django.urls import path
from .views import ValidatePhoneView

urlpatterns = [
    path("validate-phone/", ValidatePhoneView.as_view()),
]
