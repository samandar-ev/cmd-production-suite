from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0018_login_codes'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='two_factor_enabled',
            field=models.BooleanField(default=False),
        ),
    ]
