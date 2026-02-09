from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0010_credit_cards_and_plannedexpense_source_key"),
    ]

    operations = [
        migrations.AddField(
            model_name="creditcard",
            name="parent_card",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="child_cards",
                to="accounts.creditcard",
            ),
        ),
    ]
