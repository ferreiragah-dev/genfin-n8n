from django.db import models

class UserAccount(models.Model):
    phone_number = models.CharField(
        max_length=20,
        unique=True
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.phone_number
