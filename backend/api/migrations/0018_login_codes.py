from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0017_telegram'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='login_code_expires',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='login_code_hash',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='user',
            name='login_code_tries',
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]
