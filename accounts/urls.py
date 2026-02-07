from django.urls import path

from .views import (
    DailyStatsView,
    DashboardCategoryView,
    DashboardView,
    FinancialEntryCreateView,
    FinancialEntryListView,
    MonthlyStatsView,
    PhoneLoginView,
    PlannerCreateView,
    PlannerDetailView,
    PlannerListView,
    ValidatePhoneView,
    WeeklyStatsView,
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
    path("planner/<int:expense_id>/", PlannerDetailView.as_view()),
    path("stats/daily/", DailyStatsView.as_view()),
    path("stats/weekly/", WeeklyStatsView.as_view()),
    path("stats/monthly/", MonthlyStatsView.as_view()),
]
