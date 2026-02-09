from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0009_plannedexpense_is_paid"),
    ]

    operations = [
        migrations.AddField(
            model_name="plannedexpense",
            name="source_key",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.CreateModel(
            name="CreditCard",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nickname", models.CharField(blank=True, default="", max_length=80)),
                ("last4", models.CharField(max_length=4)),
                ("due_day", models.PositiveSmallIntegerField(default=10)),
                ("best_purchase_day", models.PositiveSmallIntegerField(default=1)),
                ("limit_amount", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("miles_per_point", models.DecimalField(decimal_places=4, default=1, max_digits=8)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="credit_cards", to="accounts.useraccount")),
            ],
        ),
        migrations.CreateModel(
            name="CreditCardExpense",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("category", models.CharField(max_length=80)),
                ("description", models.TextField(blank=True, default="")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("card", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="expenses", to="accounts.creditcard")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="credit_card_expenses", to="accounts.useraccount")),
            ],
        ),
    ]
