from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0013_financialentry_receipt_file"),
    ]

    operations = [
        migrations.AddField(
            model_name="useraccount",
            name="address_line",
            field=models.CharField(blank=True, default="", max_length=200),
        ),
        migrations.AddField(
            model_name="useraccount",
            name="city",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
        migrations.AddField(
            model_name="useraccount",
            name="country",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
        migrations.AddField(
            model_name="useraccount",
            name="state",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
        migrations.AddField(
            model_name="useraccount",
            name="zip_code",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
    ]
