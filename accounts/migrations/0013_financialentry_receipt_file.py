from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0012_creditcard_closing_day"),
    ]

    operations = [
        migrations.AddField(
            model_name="financialentry",
            name="receipt_file",
            field=models.FileField(blank=True, null=True, upload_to="entry_receipts/"),
        ),
    ]
