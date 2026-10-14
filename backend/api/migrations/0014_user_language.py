from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0013_finance_defaults'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='language',
            field=models.CharField(choices=[('en', 'English'), ('ru', 'Русский')], default='en', max_length=5),
        ),
    ]
