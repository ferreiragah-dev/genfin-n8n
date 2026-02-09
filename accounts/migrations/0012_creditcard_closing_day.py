from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0011_creditcard_parent_card"),
    ]

    operations = [
        migrations.AddField(
            model_name="creditcard",
            name="closing_day",
            field=models.PositiveSmallIntegerField(default=20),
        ),
    ]
