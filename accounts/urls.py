from django.urls import path
from .views import (
    ValidatePhoneView,
    FinancialEntryCreateView,
    PhoneLoginView, DashboardView, FinancialEntryListView ,DashboardCategoryView,PlannerListView,PlannerCreateView
)

urlpatterns = [
    path("validate-phone/", ValidatePhoneView.as_view()),
    path("financial-entry/", FinancialEntryCreateView.as_view()),
        path("login/", PhoneLoginView.as_view()),
    path("dashboard/", DashboardView.as_view()),
    path("entries/", FinancialEntryListView.as_view()),
 path("dashboard/categories/", DashboardCategoryView.as_view()),
     path("planner/", PlannerListView.as_view()),
    path("planner/create/", PlannerCreateView.as_view()),

    
]
