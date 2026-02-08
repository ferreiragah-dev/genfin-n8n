from django.db import migrations, models
from django.contrib.auth.hashers import make_password


def backfill_user_fields(apps, schema_editor):
    UserAccount = apps.get_model('accounts', 'UserAccount')
    for user in UserAccount.objects.all().iterator():
        changed = False
        if not user.first_name:
            user.first_name = 'Usuario'
            changed = True
        if user.last_name is None:
            user.last_name = ''
            changed = True
        if not user.email:
            user.email = f"{user.phone_number}@genfin.local"
            changed = True
        if not user.password:
            user.password = make_password('123456')
            changed = True
        if changed:
            user.save(update_fields=['first_name', 'last_name', 'email', 'password'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_plannedreserve'),
    ]

    operations = [
        migrations.AddField(
            model_name='useraccount',
            name='email',
            field=models.EmailField(blank=True, max_length=254, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='useraccount',
            name='first_name',
            field=models.CharField(blank=True, default='', max_length=80),
        ),
        migrations.AddField(
            model_name='useraccount',
            name='last_name',
            field=models.CharField(blank=True, default='', max_length=80),
        ),
        migrations.AddField(
            model_name='useraccount',
            name='password',
            field=models.CharField(blank=True, default='', max_length=128),
        ),
        migrations.RunPython(backfill_user_fields, migrations.RunPython.noop),
    ]
