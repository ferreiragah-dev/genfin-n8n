import calendar
from collections import defaultdict
from datetime import datetime, timedelta

import json
from urllib import request as urllib_request
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    CreditCard,
    CreditCardExpense,
    FinancialEntry,
    PlannedExpense,
    PlannedIncome,
    PlannedReserve,
    UserAccount,
    Vehicle,
    VehicleExpense,
)


def get_logged_user(request):
    phone = request.session.get("user_phone")
    if not phone:
        return None
    return UserAccount.objects.filter(phone_number=phone).first()


def parse_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def clamp_day(year, month, day):
    max_day = calendar.monthrange(year, month)[1]
    return max(1, min(int(day), max_day))


def shift_month(year, month, delta):
    idx = (year * 12 + (month - 1)) + delta
    new_year = idx // 12
    new_month = (idx % 12) + 1
    return new_year, new_month


def card_invoice_period_and_due(card, purchase_date):
    # Regra simples:
    # compra apos a "melhor data" cai na proxima fatura
    base_year = purchase_date.year
    base_month = purchase_date.month
    if purchase_date.day > int(card.best_purchase_day):
        base_year, base_month = shift_month(base_year, base_month, 1)
    due_day = clamp_day(base_year, base_month, int(card.due_day))
    due_date = datetime(base_year, base_month, due_day).date()
    return base_year, base_month, due_date


def sync_credit_card_bills(user, card):
    grouped = defaultdict(lambda: {"amount": 0.0, "due_date": None})
    expenses = user.credit_card_expenses.filter(card=card).order_by("date", "id")
    for expense in expenses:
        p_year, p_month, due_date = card_invoice_period_and_due(card, expense.date)
        key = f"CC:{card.id}:{p_year:04d}-{p_month:02d}"
        grouped[key]["amount"] += float(expense.amount or 0)
        grouped[key]["due_date"] = due_date

    active_keys = set(grouped.keys())
    existing_qs = user.planned_expenses.filter(source_key__startswith=f"CC:{card.id}:")
    for planned in existing_qs:
        if planned.source_key not in active_keys:
            planned.delete()

    for source_key, data in grouped.items():
        due_date = data["due_date"]
        total = round(data["amount"], 2)
        period = source_key.split(":")[-1]
        defaults = {
            "date": due_date,
            "category": f"Fatura Cartão {card.last4}",
            "description": f"Fatura cartão final {card.last4} ({period})",
            "amount": total,
            "is_recurring": True,
        }
        planned, created = PlannedExpense.objects.get_or_create(
            user=user,
            source_key=source_key,
            defaults=defaults,
        )
        if not created:
            planned.date = defaults["date"]
            planned.category = defaults["category"]
            planned.description = defaults["description"]
            planned.amount = defaults["amount"]
            planned.is_recurring = True
            planned.save()


class ValidatePhoneView(APIView):
    def post(self, request):
        phone_number = request.data.get("phone_number")

        if not phone_number:
            return Response(
                {"error": "phone_number is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        exists = UserAccount.objects.filter(
            phone_number=phone_number,
            is_active=True,
        ).exists()

        if exists:
            return Response(
                {"message": "User exists"},
                status=status.HTTP_200_OK,
            )

        return Response(
            {"message": "User not found"},
            status=status.HTTP_400_BAD_REQUEST,
        )


@method_decorator(csrf_exempt, name="dispatch")
class RegisterView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        first_name = str(request.data.get("first_name", "")).strip()
        last_name = str(request.data.get("last_name", "")).strip()
        email = str(request.data.get("email", "")).strip().lower()
        phone_number = str(request.data.get("phone_number", "")).strip()
        password = str(request.data.get("password", ""))

        if not first_name or not last_name or not email or not phone_number or not password:
            return Response(
                {"error": "first_name, last_name, email, phone_number e password sao obrigatorios"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(password) < 6:
            return Response(
                {"error": "Senha deve ter pelo menos 6 caracteres"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_email(email)
        except ValidationError:
            return Response(
                {"error": "Email invalido"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if UserAccount.objects.filter(phone_number=phone_number).exists():
            return Response(
                {"error": "Telefone ja cadastrado"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if UserAccount.objects.filter(email=email).exists():
            return Response(
                {"error": "Email ja cadastrado"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = UserAccount(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_number=phone_number,
            is_active=True,
        )
        user.set_password(password)
        user.save()

        request.session["user_phone"] = user.phone_number

        return Response(
            {"message": "Cadastro realizado com sucesso"},
            status=status.HTTP_201_CREATED,
        )


class FinancialEntryCreateView(APIView):
    def post(self, request):
        phone_number = request.data.get("phone_number")
        categoria = request.data.get("categoria")
        data_str = request.data.get("data")

        receita = request.data.get("receita")
        despesa = request.data.get("despesa")

        if not phone_number or not categoria or not data_str:
            return Response(
                {"error": "phone_number, categoria e data sao obrigatorios"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if receita is None and despesa is None:
            return Response(
                {"error": "Informe receita ou despesa"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            entry_date = datetime.strptime(data_str, "%d/%m/%Y").date()
        except ValueError:
            return Response(
                {"error": "Formato de data invalido. Use DD/MM/YYYY"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = UserAccount.objects.get(phone_number=phone_number)
        except UserAccount.DoesNotExist:
            return Response(
                {"error": "Usuario nao encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if receita is not None:
            entry_type = "RECEITA"
            amount = receita
        else:
            entry_type = "DESPESA"
            amount = despesa

        entry = FinancialEntry.objects.create(
            user=user,
            entry_type=entry_type,
            amount=amount,
            category=categoria,
            date=entry_date,
        )

        return Response(
            {
                "message": "Lancamento criado com sucesso",
                "id": entry.id,
                "tipo": entry.entry_type,
                "valor": entry.amount,
                "categoria": entry.category,
                "data": entry.date,
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_exempt, name="dispatch")
class PhoneLoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        phone_number = request.data.get("phone_number")
        password = request.data.get("password")

        if not phone_number or not password:
            return Response(
                {"error": "phone_number e password sao obrigatorios"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = UserAccount.objects.get(
                phone_number=phone_number,
                is_active=True,
            )
        except UserAccount.DoesNotExist:
            return Response(
                {"error": "Usuario nao encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user.check_password(password):
            return Response(
                {"error": "Senha invalida"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        request.session["user_phone"] = user.phone_number

        return Response(
            {"message": "Login realizado com sucesso"},
            status=status.HTTP_200_OK,
        )


class DashboardView(APIView):
    def get(self, request):
        user = get_logged_user(request)

        if not user:
            return Response(
                {"error": "Nao autenticado"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        receitas = user.entries.filter(entry_type="RECEITA")
        despesas = user.entries.filter(entry_type="DESPESA")

        total_receita = receitas.aggregate(total=Sum("amount"))["total"] or 0
        total_despesa = despesas.aggregate(total=Sum("amount"))["total"] or 0

        return Response(
            {
                "phone_number": user.phone_number,
                "total_receita": total_receita,
                "total_despesa": total_despesa,
                "saldo": total_receita - total_despesa,
            },
            status=status.HTTP_200_OK,
        )


@ensure_csrf_cookie
def login_page(request):
    return render(request, "login.html")


@ensure_csrf_cookie
def dashboard_page(request):
    if not request.session.get("user_phone"):
        return redirect("/login/")
    return render(request, "dashboard.html")


@ensure_csrf_cookie
def transactions_page(request):
    if not request.session.get("user_phone"):
        return redirect("/login/")
    return render(request, "transactions.html")


@ensure_csrf_cookie
def fixed_expenses_page(request):
    if not request.session.get("user_phone"):
        return redirect("/login/")
    return render(request, "fixed_expenses.html")


@ensure_csrf_cookie
def fixed_incomes_page(request):
    if not request.session.get("user_phone"):
        return redirect("/login/")
    return render(request, "fixed_incomes.html")


@ensure_csrf_cookie
def reserves_page(request):
    if not request.session.get("user_phone"):
        return redirect("/login/")
    return render(request, "reserves.html")


@ensure_csrf_cookie
def vehicles_page(request):
    if not request.session.get("user_phone"):
        return redirect("/login/")
    return render(request, "vehicles.html")


@ensure_csrf_cookie
def credit_cards_page(request):
    if not request.session.get("user_phone"):
        return redirect("/login/")
    return render(request, "credit_cards.html")


@ensure_csrf_cookie
def logout_page(request):
    request.session.flush()
    return redirect("/login/")


class FinancialEntryListView(APIView):
    def get(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            limit = int(request.query_params.get("limit", 20))
        except ValueError:
            limit = 20
        limit = max(1, min(limit, 500))

        entries = user.entries.order_by("-date")[:limit]

        return Response(
            [
                {
                    "id": e.id,
                    "date": e.date.strftime("%d/%m/%Y"),
                    "category": e.category,
                    "entry_type": e.entry_type,
                    "amount": e.amount,
                }
                for e in entries
            ]
        )


@method_decorator(csrf_exempt, name="dispatch")
class FinancialEntryDetailView(APIView):
    def put(self, request, entry_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            entry = user.entries.get(id=entry_id)
        except FinancialEntry.DoesNotExist:
            return Response(
                {"error": "Movimentacao nao encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        category = request.data.get("category")
        amount = request.data.get("amount")
        data_str = request.data.get("date")

        if not category or amount in (None, "") or not data_str:
            return Response(
                {"error": "date, category e amount sao obrigatorios"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        entry_type = request.data.get("entry_type")
        if entry_type and entry_type in {"RECEITA", "DESPESA"}:
            entry.entry_type = entry_type

        try:
            if "/" in str(data_str):
                entry.date = datetime.strptime(data_str, "%d/%m/%Y").date()
            else:
                entry.date = datetime.strptime(data_str, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"error": "Formato de data invalido. Use DD/MM/YYYY ou YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        entry.category = category
        entry.amount = amount
        entry.save()

        return Response({"message": "Movimentacao atualizada"}, status=status.HTTP_200_OK)

    def delete(self, request, entry_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            entry = user.entries.get(id=entry_id)
        except FinancialEntry.DoesNotExist:
            return Response(
                {"error": "Movimentacao nao encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        entry.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DashboardCategoryView(APIView):
    def get(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        data = (
            user.entries.filter(entry_type="DESPESA")
            .values("category")
            .annotate(total=Sum("amount"))
            .order_by("-total")
        )

        return Response(list(data))


class PlannerListView(APIView):
    def get(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        data = user.planned_expenses.all().order_by("date")

        return Response(
            [
                {
                    "id": p.id,
                    "date": p.date.strftime("%Y-%m-%d"),
                    "category": p.category,
                    "description": p.description,
                    "amount": p.amount,
                    "is_recurring": p.is_recurring,
                    "is_paid": p.is_paid,
                }
                for p in data
            ]
        )


class PlannedIncomeListView(APIView):
    def get(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        data = user.planned_incomes.all().order_by("date")

        return Response(
            [
                {
                    "id": p.id,
                    "date": p.date.strftime("%Y-%m-%d"),
                    "category": p.category,
                    "description": p.description,
                    "amount": p.amount,
                    "is_recurring": p.is_recurring,
                }
                for p in data
            ]
        )


class PlannedReserveListView(APIView):
    def get(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        data = user.planned_reserves.all().order_by("date")

        return Response(
            [
                {
                    "id": p.id,
                    "date": p.date.strftime("%Y-%m-%d"),
                    "category": p.category,
                    "description": p.description,
                    "amount": p.amount,
                    "is_recurring": p.is_recurring,
                }
                for p in data
            ]
        )


class VehicleListView(APIView):
    def get(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        data = user.vehicles.all().order_by("-created_at")
        return Response(
            [
                {
                    "id": v.id,
                    "name": v.name,
                    "brand": v.brand,
                    "model": v.model,
                    "year": v.year,
                    "fipe_value": v.fipe_value,
                    "fipe_variation_percent": v.fipe_variation_percent,
                    "documentation_cost": v.documentation_cost,
                    "ipva_cost": v.ipva_cost,
                    "licensing_cost": v.licensing_cost,
                    "financing_remaining_installments": v.financing_remaining_installments,
                    "financing_installment_value": v.financing_installment_value,
                }
                for v in data
            ]
        )


@method_decorator(csrf_exempt, name="dispatch")
class VehicleCreateView(APIView):
    def post(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        name = str(request.data.get("name", "")).strip()
        if not name:
            return Response({"error": "name e obrigatorio"}, status=status.HTTP_400_BAD_REQUEST)

        vehicle = Vehicle.objects.create(
            user=user,
            name=name,
            brand=request.data.get("brand", "") or "",
            model=request.data.get("model", "") or "",
            year=request.data.get("year") or None,
            fipe_value=request.data.get("fipe_value") or 0,
            fipe_variation_percent=request.data.get("fipe_variation_percent") or 0,
            documentation_cost=request.data.get("documentation_cost") or 0,
            ipva_cost=request.data.get("ipva_cost") or 0,
            licensing_cost=request.data.get("licensing_cost") or 0,
            financing_remaining_installments=request.data.get("financing_remaining_installments") or 0,
            financing_installment_value=request.data.get("financing_installment_value") or 0,
        )
        return Response({"message": "Veiculo criado", "id": vehicle.id}, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name="dispatch")
class VehicleDetailView(APIView):
    def put(self, request, vehicle_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        try:
            vehicle = user.vehicles.get(id=vehicle_id)
        except Vehicle.DoesNotExist:
            return Response({"error": "Veiculo nao encontrado"}, status=status.HTTP_404_NOT_FOUND)

        name = str(request.data.get("name", "")).strip()
        if not name:
            return Response({"error": "name e obrigatorio"}, status=status.HTTP_400_BAD_REQUEST)

        vehicle.name = name
        vehicle.brand = request.data.get("brand", "") or ""
        vehicle.model = request.data.get("model", "") or ""
        vehicle.year = request.data.get("year") or None
        vehicle.fipe_value = request.data.get("fipe_value") or 0
        vehicle.fipe_variation_percent = request.data.get("fipe_variation_percent") or 0
        vehicle.documentation_cost = request.data.get("documentation_cost") or 0
        vehicle.ipva_cost = request.data.get("ipva_cost") or 0
        vehicle.licensing_cost = request.data.get("licensing_cost") or 0
        vehicle.financing_remaining_installments = request.data.get("financing_remaining_installments") or 0
        vehicle.financing_installment_value = request.data.get("financing_installment_value") or 0
        vehicle.save()
        return Response({"message": "Veiculo atualizado"}, status=status.HTTP_200_OK)

    def delete(self, request, vehicle_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        try:
            vehicle = user.vehicles.get(id=vehicle_id)
        except Vehicle.DoesNotExist:
            return Response({"error": "Veiculo nao encontrado"}, status=status.HTTP_404_NOT_FOUND)
        vehicle.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class VehicleExpenseListView(APIView):
    def get(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        data = user.vehicle_expenses.select_related("vehicle").all().order_by("-date")
        vehicle_id = request.query_params.get("vehicle_id")
        if vehicle_id:
            data = data.filter(vehicle_id=vehicle_id)

        return Response(
            [
                {
                    "id": e.id,
                    "vehicle_id": e.vehicle_id,
                    "vehicle_name": e.vehicle.name,
                    "date": e.date.strftime("%Y-%m-%d"),
                    "expense_type": e.expense_type,
                    "description": e.description,
                    "amount": e.amount,
                    "is_recurring": e.is_recurring,
                }
                for e in data
            ]
        )


@method_decorator(csrf_exempt, name="dispatch")
class VehicleExpenseCreateView(APIView):
    def post(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        vehicle_id = request.data.get("vehicle_id")
        date = request.data.get("date")
        expense_type = request.data.get("expense_type")
        amount = request.data.get("amount")
        if not vehicle_id or not date or not expense_type or amount in (None, ""):
            return Response({"error": "vehicle_id, date, expense_type e amount sao obrigatorios"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            vehicle = user.vehicles.get(id=vehicle_id)
        except Vehicle.DoesNotExist:
            return Response({"error": "Veiculo nao encontrado"}, status=status.HTTP_404_NOT_FOUND)

        item = VehicleExpense.objects.create(
            user=user,
            vehicle=vehicle,
            date=date,
            expense_type=expense_type,
            description=request.data.get("description", "") or "",
            amount=amount,
            is_recurring=parse_bool(request.data.get("is_recurring", False)),
        )
        return Response({"message": "Gasto criado", "id": item.id}, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name="dispatch")
class VehicleExpenseDetailView(APIView):
    def put(self, request, expense_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        try:
            item = user.vehicle_expenses.get(id=expense_id)
        except VehicleExpense.DoesNotExist:
            return Response({"error": "Gasto nao encontrado"}, status=status.HTTP_404_NOT_FOUND)

        vehicle_id = request.data.get("vehicle_id")
        if vehicle_id:
            try:
                item.vehicle = user.vehicles.get(id=vehicle_id)
            except Vehicle.DoesNotExist:
                return Response({"error": "Veiculo nao encontrado"}, status=status.HTTP_404_NOT_FOUND)

        date = request.data.get("date")
        expense_type = request.data.get("expense_type")
        amount = request.data.get("amount")
        if not date or not expense_type or amount in (None, ""):
            return Response({"error": "date, expense_type e amount sao obrigatorios"}, status=status.HTTP_400_BAD_REQUEST)

        item.date = date
        item.expense_type = expense_type
        item.description = request.data.get("description", "") or ""
        item.amount = amount
        item.is_recurring = parse_bool(request.data.get("is_recurring", False))
        item.save()
        return Response({"message": "Gasto atualizado"}, status=status.HTTP_200_OK)

    def delete(self, request, expense_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        try:
            item = user.vehicle_expenses.get(id=expense_id)
        except VehicleExpense.DoesNotExist:
            return Response({"error": "Gasto nao encontrado"}, status=status.HTTP_404_NOT_FOUND)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class VehicleSummaryView(APIView):
    def get(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        today = timezone.now().date()
        try:
            month = int(request.query_params.get("month", today.month))
        except ValueError:
            month = today.month
        try:
            year = int(request.query_params.get("year", today.year))
        except ValueError:
            year = today.year

        vehicles = list(user.vehicles.all())
        recurring_expenses = user.vehicle_expenses.filter(is_recurring=True)
        month_expenses = user.vehicle_expenses.filter(date__year=year, date__month=month, is_recurring=False)

        by_category = {
            "COMBUSTIVEL": 0,
            "MANUTENCAO": 0,
            "SEGURO": 0,
            "PEDAGIO": 0,
            "ESTACIONAMENTO": 0,
            "OUTRO": 0,
            "DOCUMENTACAO": 0,
            "IPVA": 0,
            "LICENCIAMENTO": 0,
            "FINANCIAMENTO": 0,
        }

        vehicle_totals = []
        monthly_total = 0
        for v in vehicles:
            base_doc = float(v.documentation_cost or 0) / 12
            base_ipva = float(v.ipva_cost or 0) / 12
            base_lic = float(v.licensing_cost or 0) / 12
            financing = float(v.financing_installment_value or 0) if int(v.financing_remaining_installments or 0) > 0 else 0

            recurrent_total = sum(float(e.amount or 0) for e in recurring_expenses.filter(vehicle=v))
            month_total = sum(float(e.amount or 0) for e in month_expenses.filter(vehicle=v))

            vehicle_monthly_total = base_doc + base_ipva + base_lic + financing + recurrent_total + month_total
            monthly_total += vehicle_monthly_total

            by_category["DOCUMENTACAO"] += base_doc
            by_category["IPVA"] += base_ipva
            by_category["LICENCIAMENTO"] += base_lic
            by_category["FINANCIAMENTO"] += financing
            for e in recurring_expenses.filter(vehicle=v):
                by_category[e.expense_type] += float(e.amount or 0)
            for e in month_expenses.filter(vehicle=v):
                by_category[e.expense_type] += float(e.amount or 0)

            vehicle_totals.append(
                {
                    "vehicle_id": v.id,
                    "name": v.name,
                    "monthly_cost": round(vehicle_monthly_total, 2),
                    "fipe_value": float(v.fipe_value or 0),
                    "fipe_variation_percent": float(v.fipe_variation_percent or 0),
                    "financing_remaining_installments": int(v.financing_remaining_installments or 0),
                }
            )

        category_rows = [
            {"category": k, "total": round(val, 2)}
            for k, val in by_category.items()
            if val > 0
        ]
        category_rows.sort(key=lambda x: x["total"], reverse=True)
        vehicle_totals.sort(key=lambda x: x["monthly_cost"], reverse=True)

        return Response(
            {
                "month": month,
                "year": year,
                "monthly_total": round(monthly_total, 2),
                "vehicle_count": len(vehicles),
                "by_category": category_rows,
                "vehicle_totals": vehicle_totals,
            }
        )


class CreditCardListView(APIView):
    def get(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        data = user.credit_cards.all().order_by("-created_at")
        return Response(
            [
                {
                    "id": c.id,
                    "nickname": c.nickname,
                    "last4": c.last4,
                    "due_day": c.due_day,
                    "best_purchase_day": c.best_purchase_day,
                    "limit_amount": c.limit_amount,
                    "miles_per_point": c.miles_per_point,
                }
                for c in data
            ]
        )


@method_decorator(csrf_exempt, name="dispatch")
class CreditCardCreateView(APIView):
    def post(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        last4 = "".join(ch for ch in str(request.data.get("last4", "")) if ch.isdigit())
        try:
            due_day = int(request.data.get("due_day") or 0)
            best_purchase_day = int(request.data.get("best_purchase_day") or 0)
        except (TypeError, ValueError):
            return Response({"error": "Vencimento e melhor dia devem ser números válidos"}, status=status.HTTP_400_BAD_REQUEST)
        if len(last4) != 4:
            return Response({"error": "Informe os 4 últimos dígitos do cartão"}, status=status.HTTP_400_BAD_REQUEST)
        if due_day < 1 or due_day > 31:
            return Response({"error": "Vencimento deve estar entre 1 e 31"}, status=status.HTTP_400_BAD_REQUEST)
        if best_purchase_day < 1 or best_purchase_day > 31:
            return Response({"error": "Melhor data deve estar entre 1 e 31"}, status=status.HTTP_400_BAD_REQUEST)

        card = CreditCard.objects.create(
            user=user,
            nickname=str(request.data.get("nickname", "")).strip(),
            last4=last4,
            due_day=due_day,
            best_purchase_day=best_purchase_day,
            limit_amount=request.data.get("limit_amount") or 0,
            miles_per_point=request.data.get("miles_per_point") or 1,
        )
        return Response({"message": "Cartão criado", "id": card.id}, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name="dispatch")
class CreditCardDetailView(APIView):
    def put(self, request, card_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        try:
            card = user.credit_cards.get(id=card_id)
        except CreditCard.DoesNotExist:
            return Response({"error": "Cartão não encontrado"}, status=status.HTTP_404_NOT_FOUND)

        last4 = "".join(ch for ch in str(request.data.get("last4", card.last4)) if ch.isdigit())
        try:
            due_day = int(request.data.get("due_day") or card.due_day)
            best_purchase_day = int(request.data.get("best_purchase_day") or card.best_purchase_day)
        except (TypeError, ValueError):
            return Response({"error": "Vencimento e melhor dia devem ser números válidos"}, status=status.HTTP_400_BAD_REQUEST)
        if len(last4) != 4:
            return Response({"error": "Informe os 4 últimos dígitos do cartão"}, status=status.HTTP_400_BAD_REQUEST)
        if due_day < 1 or due_day > 31:
            return Response({"error": "Vencimento deve estar entre 1 e 31"}, status=status.HTTP_400_BAD_REQUEST)
        if best_purchase_day < 1 or best_purchase_day > 31:
            return Response({"error": "Melhor data deve estar entre 1 e 31"}, status=status.HTTP_400_BAD_REQUEST)

        card.nickname = str(request.data.get("nickname", card.nickname)).strip()
        card.last4 = last4
        card.due_day = due_day
        card.best_purchase_day = best_purchase_day
        card.limit_amount = request.data.get("limit_amount") or 0
        card.miles_per_point = request.data.get("miles_per_point") or 1
        card.save()
        sync_credit_card_bills(user, card)
        return Response({"message": "Cartão atualizado"}, status=status.HTTP_200_OK)

    def delete(self, request, card_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        try:
            card = user.credit_cards.get(id=card_id)
        except CreditCard.DoesNotExist:
            return Response({"error": "Cartão não encontrado"}, status=status.HTTP_404_NOT_FOUND)

        user.planned_expenses.filter(source_key__startswith=f"CC:{card.id}:").delete()
        card.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CreditCardExpenseListView(APIView):
    def get(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        data = user.credit_card_expenses.select_related("card").all().order_by("-date", "-id")
        card_id = request.query_params.get("card_id")
        if card_id:
            data = data.filter(card_id=card_id)
        return Response(
            [
                {
                    "id": e.id,
                    "card_id": e.card_id,
                    "card_last4": e.card.last4,
                    "card_name": e.card.nickname or f"****{e.card.last4}",
                    "date": e.date.strftime("%Y-%m-%d"),
                    "category": e.category,
                    "description": e.description,
                    "amount": e.amount,
                }
                for e in data
            ]
        )


@method_decorator(csrf_exempt, name="dispatch")
class CreditCardExpenseCreateView(APIView):
    def post(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        card_id = request.data.get("card_id")
        date = request.data.get("date")
        category = str(request.data.get("category", "")).strip()
        amount = request.data.get("amount")
        if not card_id or not date or not category or amount in (None, ""):
            return Response(
                {"error": "card_id, date, category e amount são obrigatórios"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            card = user.credit_cards.get(id=card_id)
        except CreditCard.DoesNotExist:
            return Response({"error": "Cartão não encontrado"}, status=status.HTTP_404_NOT_FOUND)

        expense = CreditCardExpense.objects.create(
            user=user,
            card=card,
            date=date,
            category=category,
            description=request.data.get("description", "") or "",
            amount=amount,
        )
        sync_credit_card_bills(user, card)
        return Response({"message": "Gasto no cartão criado", "id": expense.id}, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name="dispatch")
class CreditCardExpenseDetailView(APIView):
    def put(self, request, expense_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        try:
            expense = user.credit_card_expenses.get(id=expense_id)
        except CreditCardExpense.DoesNotExist:
            return Response({"error": "Gasto não encontrado"}, status=status.HTTP_404_NOT_FOUND)

        old_card = expense.card
        card_id = request.data.get("card_id") or expense.card_id
        try:
            card = user.credit_cards.get(id=card_id)
        except CreditCard.DoesNotExist:
            return Response({"error": "Cartão não encontrado"}, status=status.HTTP_404_NOT_FOUND)

        date = request.data.get("date")
        category = str(request.data.get("category", "")).strip()
        amount = request.data.get("amount")
        if not date or not category or amount in (None, ""):
            return Response(
                {"error": "date, category e amount são obrigatórios"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        expense.card = card
        expense.date = date
        expense.category = category
        expense.description = request.data.get("description", "") or ""
        expense.amount = amount
        expense.save()

        sync_credit_card_bills(user, card)
        if old_card.id != card.id:
            sync_credit_card_bills(user, old_card)
        return Response({"message": "Gasto no cartão atualizado"}, status=status.HTTP_200_OK)

    def delete(self, request, expense_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        try:
            expense = user.credit_card_expenses.get(id=expense_id)
        except CreditCardExpense.DoesNotExist:
            return Response({"error": "Gasto não encontrado"}, status=status.HTTP_404_NOT_FOUND)

        card = expense.card
        expense.delete()
        sync_credit_card_bills(user, card)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CreditCardSummaryView(APIView):
    def get(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        today = timezone.now().date()
        try:
            month = int(request.query_params.get("month", today.month))
        except ValueError:
            month = today.month
        try:
            year = int(request.query_params.get("year", today.year))
        except ValueError:
            year = today.year

        cards = list(user.credit_cards.all())
        expenses = user.credit_card_expenses.filter(date__year=year, date__month=month).select_related("card")
        total_spent = sum(float(e.amount or 0) for e in expenses)
        total_limit = sum(float(c.limit_amount or 0) for c in cards)

        by_category = defaultdict(float)
        by_card = defaultdict(float)
        miles_total = 0.0
        for expense in expenses:
            by_category[expense.category] += float(expense.amount or 0)
            by_card[f"****{expense.card.last4}"] += float(expense.amount or 0)
            miles_total += float(expense.amount or 0) * float(expense.card.miles_per_point or 0)

        by_category_rows = [{"category": k, "total": round(v, 2)} for k, v in by_category.items()]
        by_category_rows.sort(key=lambda x: x["total"], reverse=True)
        by_card_rows = [{"card": k, "total": round(v, 2)} for k, v in by_card.items()]
        by_card_rows.sort(key=lambda x: x["total"], reverse=True)

        upcoming = user.planned_expenses.filter(
            source_key__startswith="CC:",
            date__year=year,
            date__month=month,
        ).order_by("date")
        upcoming_rows = [
            {
                "id": p.id,
                "date": p.date.strftime("%Y-%m-%d"),
                "category": p.category,
                "amount": p.amount,
                "is_paid": p.is_paid,
            }
            for p in upcoming
        ]

        return Response(
            {
                "month": month,
                "year": year,
                "card_count": len(cards),
                "total_spent": round(total_spent, 2),
                "total_limit": round(total_limit, 2),
                "usage_percent": round((total_spent / total_limit) * 100, 2) if total_limit > 0 else 0,
                "estimated_miles": round(miles_total, 2),
                "by_category": by_category_rows,
                "by_card": by_card_rows,
                "upcoming_bills": upcoming_rows,
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class PlannerCreateView(APIView):
    def post(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        date = request.data.get("date")
        category = request.data.get("category")
        amount = request.data.get("amount")

        if not date or not category or amount in (None, ""):
            return Response(
                {"error": "date, category e amount sao obrigatorios"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        planned = PlannedExpense.objects.create(
            user=user,
            date=date,
            category=category,
            description=request.data.get("description", ""),
            amount=amount,
            is_recurring=parse_bool(request.data.get("is_recurring", False)),
            is_paid=parse_bool(request.data.get("is_paid", False)),
        )

        return Response(
            {
                "message": "Despesa fixa criada",
                "id": planned.id,
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_exempt, name="dispatch")
class PlannedIncomeCreateView(APIView):
    def post(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        date = request.data.get("date")
        category = request.data.get("category")
        amount = request.data.get("amount")

        if not date or not category or amount in (None, ""):
            return Response(
                {"error": "date, category e amount sao obrigatorios"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        planned = PlannedIncome.objects.create(
            user=user,
            date=date,
            category=category,
            description=request.data.get("description", ""),
            amount=amount,
            is_recurring=parse_bool(request.data.get("is_recurring", False)),
        )

        return Response(
            {
                "message": "Entrada fixa criada",
                "id": planned.id,
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_exempt, name="dispatch")
class PlannedReserveCreateView(APIView):
    def post(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        date = request.data.get("date")
        category = request.data.get("category")
        amount = request.data.get("amount")

        if not date or not category or amount in (None, ""):
            return Response(
                {"error": "date, category e amount sao obrigatorios"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        planned = PlannedReserve.objects.create(
            user=user,
            date=date,
            category=category,
            description=request.data.get("description", ""),
            amount=amount,
            is_recurring=parse_bool(request.data.get("is_recurring", False)),
        )

        return Response(
            {
                "message": "Reserva criada",
                "id": planned.id,
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_exempt, name="dispatch")
class PlannerDetailView(APIView):
    def put(self, request, expense_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            planned = user.planned_expenses.get(id=expense_id)
        except PlannedExpense.DoesNotExist:
            return Response(
                {"error": "Despesa fixa nao encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        date = request.data.get("date")
        category = request.data.get("category")
        amount = request.data.get("amount")

        if not date or not category or amount in (None, ""):
            return Response(
                {"error": "date, category e amount sao obrigatorios"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        planned.date = date
        planned.category = category
        planned.description = request.data.get("description", "")
        planned.amount = amount
        planned.is_recurring = parse_bool(request.data.get("is_recurring", False))
        planned.is_paid = parse_bool(request.data.get("is_paid", False))
        planned.save()

        return Response({"message": "Despesa fixa atualizada"}, status=status.HTTP_200_OK)

    def delete(self, request, expense_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            planned = user.planned_expenses.get(id=expense_id)
        except PlannedExpense.DoesNotExist:
            return Response(
                {"error": "Despesa fixa nao encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        planned.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_exempt, name="dispatch")
class PlannedIncomeDetailView(APIView):
    def put(self, request, income_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            planned = user.planned_incomes.get(id=income_id)
        except PlannedIncome.DoesNotExist:
            return Response(
                {"error": "Entrada fixa nao encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        date = request.data.get("date")
        category = request.data.get("category")
        amount = request.data.get("amount")

        if not date or not category or amount in (None, ""):
            return Response(
                {"error": "date, category e amount sao obrigatorios"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        planned.date = date
        planned.category = category
        planned.description = request.data.get("description", "")
        planned.amount = amount
        planned.is_recurring = parse_bool(request.data.get("is_recurring", False))
        planned.save()

        return Response({"message": "Entrada fixa atualizada"}, status=status.HTTP_200_OK)

    def delete(self, request, income_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            planned = user.planned_incomes.get(id=income_id)
        except PlannedIncome.DoesNotExist:
            return Response(
                {"error": "Entrada fixa nao encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        planned.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_exempt, name="dispatch")
class PlannedReserveDetailView(APIView):
    def put(self, request, reserve_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            planned = user.planned_reserves.get(id=reserve_id)
        except PlannedReserve.DoesNotExist:
            return Response(
                {"error": "Reserva nao encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        date = request.data.get("date")
        category = request.data.get("category")
        amount = request.data.get("amount")

        if not date or not category or amount in (None, ""):
            return Response(
                {"error": "date, category e amount sao obrigatorios"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        planned.date = date
        planned.category = category
        planned.description = request.data.get("description", "")
        planned.amount = amount
        planned.is_recurring = parse_bool(request.data.get("is_recurring", False))
        planned.save()

        return Response({"message": "Reserva atualizada"}, status=status.HTTP_200_OK)

    def delete(self, request, reserve_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            planned = user.planned_reserves.get(id=reserve_id)
        except PlannedReserve.DoesNotExist:
            return Response(
                {"error": "Reserva nao encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        planned.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class StatsBaseView(APIView):
    delta_days = 1

    def get(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        start_date = timezone.now().date() - timedelta(days=self.delta_days - 1)

        qs = FinancialEntry.objects.filter(user=user, date__gte=start_date)

        total_receita = qs.filter(entry_type="RECEITA").aggregate(total=Sum("amount"))["total"] or 0
        total_despesa = qs.filter(entry_type="DESPESA").aggregate(total=Sum("amount"))["total"] or 0
        movimentacoes = qs.count()

        total = total_receita + total_despesa or 1

        percent_receita = round((total_receita / total) * 100)
        percent_despesa = round((total_despesa / total) * 100)

        return Response(
            {
                "total_receita": total_receita,
                "total_despesa": total_despesa,
                "movimentacoes": movimentacoes,
                "percent_receita": percent_receita,
                "percent_despesa": percent_despesa,
            }
        )


class DailyStatsView(StatsBaseView):
    delta_days = 1


class WeeklyStatsView(StatsBaseView):
    delta_days = 7


class MonthlyStatsView(StatsBaseView):
    delta_days = 30


class WhatsAppSummaryWebhookView(APIView):
    def post(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        text = str(request.data.get("text", "")).strip()
        if not text:
            return Response(
                {"error": "text e obrigatorio"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        outbound = {
            "phone_number": user.phone_number,
            "text": text,
        }

        mode = str(request.data.get("mode", "prod")).strip().lower()
        if user.phone_number != "5511913305093":
            mode = "prod"
        if mode == "dev":
            webhook_url = "https://n8n.lowcodeforward.com/webhook-test/genfinWpp"
        else:
            webhook_url = "https://n8n.lowcodeforward.com/webhook/genfinWpp"
        req = urllib_request.Request(
            webhook_url,
            data=json.dumps(outbound).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib_request.urlopen(req, timeout=12) as resp:
                webhook_status = resp.getcode()
        except Exception as exc:
            return Response(
                {"error": "Falha ao enviar para webhook", "detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {"message": "Resumo enviado", "webhook_status": webhook_status, "mode": mode},
            status=status.HTTP_200_OK,
        )


