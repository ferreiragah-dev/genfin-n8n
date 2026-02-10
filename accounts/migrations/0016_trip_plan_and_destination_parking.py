from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0015_vehicle_fuel_and_destinations"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehiclefrequentdestination",
            name="has_paid_parking",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="vehiclefrequentdestination",
            name="parking_cost",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.CreateModel(
            name="TripPlan",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(blank=True, default="", max_length=120)),
                ("date", models.DateField(blank=True, null=True)),
                ("distance_km", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("lodging_cost", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("meal_cost", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("extra_cost", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="trip_plans", to="accounts.useraccount")),
                ("vehicle", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="trip_plans", to="accounts.vehicle")),
            ],
        ),
        migrations.CreateModel(
            name="TripToll",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(blank=True, default="", max_length=120)),
                ("amount", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("trip", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="tolls", to="accounts.tripplan")),
            ],
        ),
    ]
