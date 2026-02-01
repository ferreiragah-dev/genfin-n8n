from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import UserAccount

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