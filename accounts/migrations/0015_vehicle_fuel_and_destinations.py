from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0014_useraccount_profile_address_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicle",
            name="fuel_km_per_liter",
            field=models.DecimalField(decimal_places=3, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name="vehicle",
            name="fuel_price_per_liter",
            field=models.DecimalField(decimal_places=3, default=0, max_digits=10),
        ),
        migrations.CreateModel(
            name="VehicleFrequentDestination",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("periodicity", models.CharField(choices=[("DIARIO", "Diario"), ("SEMANAL", "Semanal"), ("QUINZENAL", "Quinzenal"), ("MENSAL", "Mensal")], default="SEMANAL", max_length=12)),
                ("distance_km", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="vehicle_destinations", to="accounts.useraccount")),
                ("vehicle", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="frequent_destinations", to="accounts.vehicle")),
            ],
        ),
    ]
