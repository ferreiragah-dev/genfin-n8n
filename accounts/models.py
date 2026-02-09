from django.db import models
from django.contrib.auth.hashers import check_password, identify_hasher, make_password

class UserAccount(models.Model):
    phone_number = models.CharField(max_length=20, unique=True)
    first_name = models.CharField(max_length=80, blank=True, default="")
    last_name = models.CharField(max_length=80, blank=True, default="")
    email = models.EmailField(unique=True, null=True, blank=True)
    password = models.CharField(max_length=128, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        try:
            identify_hasher(self.password)
            return check_password(raw_password, self.password)
        except Exception:
            # Compatibilidade temporaria: registros antigos/alterados manualmente no admin
            return self.password == raw_password

    def __str__(self):
        return self.phone_number


class FinancialEntry(models.Model):
    ENTRY_TYPE_CHOICES = (
        ("RECEITA", "Receita"),
        ("DESPESA", "Despesa"),
    )

    user = models.ForeignKey(
        UserAccount,
        on_delete=models.CASCADE,
        related_name="entries"
    )

    entry_type = models.CharField(
        max_length=10,
        choices=ENTRY_TYPE_CHOICES
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    category = models.CharField(max_length=100)

    date = models.DateField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.entry_type} - {self.amount}"


class PlannedExpense(models.Model):
    user = models.ForeignKey(
        UserAccount,
        on_delete=models.CASCADE,
        related_name="planned_expenses"
    )
    date = models.DateField()
    category = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_recurring = models.BooleanField(default=False)
    is_paid = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.date} - {self.category} - {self.amount}"


class PlannedIncome(models.Model):
    user = models.ForeignKey(
        UserAccount,
        on_delete=models.CASCADE,
        related_name="planned_incomes"
    )
    date = models.DateField()
    category = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_recurring = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.date} - {self.category} - {self.amount}"


class PlannedReserve(models.Model):
    user = models.ForeignKey(
        UserAccount,
        on_delete=models.CASCADE,
        related_name="planned_reserves"
    )
    date = models.DateField()
    category = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_recurring = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.date} - {self.category} - {self.amount}"


class Vehicle(models.Model):
    user = models.ForeignKey(
        UserAccount,
        on_delete=models.CASCADE,
        related_name="vehicles"
    )
    name = models.CharField(max_length=80)
    brand = models.CharField(max_length=80, blank=True, default="")
    model = models.CharField(max_length=80, blank=True, default="")
    year = models.PositiveIntegerField(null=True, blank=True)
    fipe_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    fipe_variation_percent = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    documentation_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    ipva_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    licensing_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    financing_remaining_installments = models.PositiveIntegerField(default=0)
    financing_installment_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.brand} {self.model})".strip()


class VehicleExpense(models.Model):
    EXPENSE_TYPE_CHOICES = (
        ("COMBUSTIVEL", "Combustível"),
        ("MANUTENCAO", "Manutenção"),
        ("SEGURO", "Seguro"),
        ("PEDAGIO", "Pedágio"),
        ("ESTACIONAMENTO", "Estacionamento"),
        ("OUTRO", "Outro"),
    )
    user = models.ForeignKey(
        UserAccount,
        on_delete=models.CASCADE,
        related_name="vehicle_expenses"
    )
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name="expenses"
    )
    date = models.DateField()
    expense_type = models.CharField(max_length=30, choices=EXPENSE_TYPE_CHOICES)
    description = models.TextField(blank=True, default="")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_recurring = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.vehicle.name} - {self.expense_type} - {self.amount}"
