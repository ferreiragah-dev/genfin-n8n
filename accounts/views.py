from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from datetime import datetime
from django.db.models import Sum

from .models import UserAccount, FinancialEntry


from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from rest_framework.authentication import BasicAuthentication
from rest_framework.permissions import AllowAny
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator



def get_logged_user(request):
    phone = request.session.get("user_phone")
    if not phone:
        return None
    return UserAccount.objects.filter(phone_number=phone).first()


class ValidatePhoneView(APIView):

    def post(self, request):
        phone_number = request.data.get("phone_number")

        if not phone_number:
            return Response(
                {"error": "phone_number is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        exists = UserAccount.objects.filter(
            phone_number=phone_number,
            is_active=True
        ).exists()

        if exists:
            return Response(
                {"message": "User exists"},
                status=status.HTTP_200_OK
            )

        return Response(
            {"message": "User not found"},
            status=status.HTTP_400_BAD_REQUEST
        )



from datetime import datetime

from .models import UserAccount, FinancialEntry


class FinancialEntryCreateView(APIView):

    def post(self, request):
        phone_number = request.data.get("phone_number")
        categoria = request.data.get("categoria")
        data_str = request.data.get("data")

        receita = request.data.get("receita")
        despesa = request.data.get("despesa")

        if not phone_number or not categoria or not data_str:
            return Response(
                {"error": "phone_number, categoria e data são obrigatórios"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if receita is None and despesa is None:
            return Response(
                {"error": "Informe receita ou despesa"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            entry_date = datetime.strptime(data_str, "%d/%m/%Y").date()
        except ValueError:
            return Response(
                {"error": "Formato de data inválido. Use DD/MM/YYYY"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = UserAccount.objects.get(phone_number=phone_number)
        except UserAccount.DoesNotExist:
            return Response(
                {"error": "Usuário não encontrado"},
                status=status.HTTP_404_NOT_FOUND
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
            date=entry_date
        )

        return Response(
            {
                "message": "Lançamento criado com sucesso",
                "id": entry.id,
                "tipo": entry.entry_type,
                "valor": entry.amount,
                "categoria": entry.category,
                "data": entry.date
            },
            status=status.HTTP_201_CREATED
        )


@method_decorator(csrf_exempt, name="dispatch")
class PhoneLoginView(APIView):
    authentication_classes = []      # 🔥 DESLIGA SessionAuthentication
    permission_classes = [AllowAny]  # 🔓 público

    def post(self, request):
        phone_number = request.data.get("phone_number")

        if not phone_number:
            return Response(
                {"error": "phone_number é obrigatório"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = UserAccount.objects.get(
                phone_number=phone_number,
                is_active=True
            )
        except UserAccount.DoesNotExist:
            return Response(
                {"error": "Usuário não encontrado"},
                status=status.HTTP_404_NOT_FOUND
            )

        # cria sessão manualmente
        request.session["user_phone"] = user.phone_number

        return Response(
            {"message": "Login realizado com sucesso"},
            status=status.HTTP_200_OK
        )



class DashboardView(APIView):

    def get(self, request):
        user = get_logged_user(request)

        if not user:
            return Response(
                {"error": "Não autenticado"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        receitas = user.entries.filter(entry_type="RECEITA")
        despesas = user.entries.filter(entry_type="DESPESA")

        total_receita = receitas.aggregate(
            total=Sum("amount")
        )["total"] or 0

        total_despesa = despesas.aggregate(
            total=Sum("amount")
        )["total"] or 0

        return Response(
            {
                "phone_number": user.phone_number,
                "total_receita": total_receita,
                "total_despesa": total_despesa,
                "saldo": total_receita - total_despesa
            },
            status=status.HTTP_200_OK
        )
    
from django.shortcuts import render, redirect

def login_page(request):
    return render(request, "login.html")


def dashboard_page(request):
    if not request.session.get("user_phone"):
        return redirect("/login/")
    return render(request, "dashboard.html")

class FinancialEntryListView(APIView):
    def get(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=401)

        entries = user.entries.order_by("-date")[:20]

        return Response([
            {
                "date": e.date.strftime("%d/%m/%Y"),
                "category": e.category,
                "entry_type": e.entry_type,
                "amount": e.amount
            } for e in entries
        ])


class DashboardCategoryView(APIView):
    def get(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        data = (
            user.entries
            .filter(entry_type="DESPESA")
            .values("category")
            .annotate(total=Sum("amount"))
            .order_by("-total")
        )

        return Response(list(data))
