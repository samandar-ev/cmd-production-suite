import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0020_ai_connector'),
    ]

    operations = [
        migrations.AddField(
            model_name='videosubmission',
            name='delivery',
            field=models.CharField(
                choices=[('upload', 'Uploaded'), ('in_person', 'Handed over in person')],
                default='upload',
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name='videosubmission',
            name='handover_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='videosubmission',
            name='handover_media',
            field=models.CharField(
                blank=True,
                choices=[
                    ('hard_drive', 'Hard drive'),
                    ('ssd', 'SSD'),
                    ('memory_card', 'Memory card'),
                    ('usb', 'USB flash drive'),
                    ('other', 'Other'),
                ],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='videosubmission',
            name='handover_to',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='received_handovers',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
