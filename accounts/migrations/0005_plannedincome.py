import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_plannedexpense_is_recurring"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlannedIncome",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("category", models.CharField(max_length=50)),
                ("description", models.TextField(blank=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("is_recurring", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="planned_incomes", to="accounts.useraccount")),
            ],
        ),
    ]
