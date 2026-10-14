import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0019_two_factor_optional'),
    ]

    operations = [
        migrations.CreateModel(
            name='OAuthClient',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('client_id', models.CharField(max_length=64, unique=True)),
                ('name', models.CharField(max_length=200)),
                ('redirect_uris', models.JSONField(default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='AIConnection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('access_hash', models.CharField(max_length=64, unique=True)),
                ('access_expires', models.DateTimeField()),
                ('refresh_hash', models.CharField(max_length=64, unique=True)),
                ('refresh_expires', models.DateTimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_used_at', models.DateTimeField(blank=True, null=True)),
                ('revoked', models.BooleanField(default=False)),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='ai_connections',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.oauthclient')),
            ],
        ),
        migrations.CreateModel(
            name='AIApproval',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(max_length=20)),
                ('method', models.CharField(max_length=10)),
                ('path', models.CharField(max_length=500)),
                ('request_hash', models.CharField(max_length=64)),
                ('summary', models.TextField()),
                ('status', models.CharField(default='pending', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('decided_at', models.DateTimeField(blank=True, null=True)),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='ai_approvals',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'connection',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name='approvals', to='api.aiconnection'
                    ),
                ),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AIAuthCode',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code_hash', models.CharField(max_length=64, unique=True)),
                ('redirect_uri', models.TextField()),
                ('code_challenge', models.CharField(max_length=128)),
                ('expires_at', models.DateTimeField()),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.oauthclient')),
            ],
        ),
    ]
