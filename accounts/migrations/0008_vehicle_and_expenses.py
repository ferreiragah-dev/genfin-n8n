from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_useraccount_profile_and_password'),
    ]

    operations = [
        migrations.CreateModel(
            name='Vehicle',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=80)),
                ('brand', models.CharField(blank=True, default='', max_length=80)),
                ('model', models.CharField(blank=True, default='', max_length=80)),
                ('year', models.PositiveIntegerField(blank=True, null=True)),
                ('fipe_value', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('fipe_variation_percent', models.DecimalField(decimal_places=2, default=0, max_digits=6)),
                ('documentation_cost', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('ipva_cost', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('licensing_cost', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('financing_remaining_installments', models.PositiveIntegerField(default=0)),
                ('financing_installment_value', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='vehicles', to='accounts.useraccount')),
            ],
        ),
        migrations.CreateModel(
            name='VehicleExpense',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('expense_type', models.CharField(choices=[('COMBUSTIVEL', 'Combustível'), ('MANUTENCAO', 'Manutenção'), ('SEGURO', 'Seguro'), ('PEDAGIO', 'Pedágio'), ('ESTACIONAMENTO', 'Estacionamento'), ('OUTRO', 'Outro')], max_length=30)),
                ('description', models.TextField(blank=True, default='')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('is_recurring', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='vehicle_expenses', to='accounts.useraccount')),
                ('vehicle', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='expenses', to='accounts.vehicle')),
            ],
        ),
    ]
