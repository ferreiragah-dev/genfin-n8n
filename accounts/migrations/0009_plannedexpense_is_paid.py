from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0008_vehicle_and_expenses"),
    ]

    operations = [
        migrations.AddField(
            model_name="plannedexpense",
            name="is_paid",
            field=models.BooleanField(default=False),
        ),
    ]
