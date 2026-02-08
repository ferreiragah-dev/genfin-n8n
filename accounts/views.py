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

from .models import FinancialEntry, PlannedExpense, PlannedIncome, PlannedReserve, UserAccount


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
