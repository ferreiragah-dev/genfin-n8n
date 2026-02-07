from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_plannedexpense"),
    ]

    operations = [
        migrations.AddField(
            model_name="plannedexpense",
            name="is_recurring",
            field=models.BooleanField(default=False),
        ),
    ]
