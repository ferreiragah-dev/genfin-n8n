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
