import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0011_strategy_to_workspace_pages'),
    ]

    operations = [
        migrations.CreateModel(
            name='FinanceAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                (
                    'kind',
                    models.CharField(
                        choices=[('bank', 'Bank'), ('cash', 'Cash'), ('card', 'Card'), ('other', 'Other')],
                        default='bank',
                        max_length=10,
                    ),
                ),
                ('opening_balance', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ('archived', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['archived', 'name'],
            },
        ),
        migrations.CreateModel(
            name='FinanceCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                (
                    'group',
                    models.CharField(
                        choices=[
                            ('revenue', 'Revenue'),
                            ('other_income', 'Other income'),
                            ('direct', 'Direct costs'),
                            ('payroll', 'Payroll'),
                            ('operating', 'Operating expenses'),
                            ('tax', 'Taxes'),
                        ],
                        max_length=20,
                    ),
                ),
                ('monthly_budget', models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ('archived', models.BooleanField(default=False)),
            ],
            options={
                'ordering': ['group', 'name'],
            },
        ),
        migrations.CreateModel(
            name='RecurringTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(choices=[('income', 'Income'), ('expense', 'Expense')], max_length=10)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=14)),
                ('counterparty', models.CharField(blank=True, max_length=255)),
                ('description', models.CharField(blank=True, max_length=255)),
                (
                    'frequency',
                    models.CharField(
                        choices=[
                            ('weekly', 'Weekly'),
                            ('monthly', 'Monthly'),
                            ('quarterly', 'Quarterly'),
                            ('yearly', 'Yearly'),
                        ],
                        default='monthly',
                        max_length=10,
                    ),
                ),
                ('next_date', models.DateField()),
                ('end_date', models.DateField(blank=True, null=True)),
                ('active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'account',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name='+', to='api.financeaccount'
                    ),
                ),
                (
                    'category',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name='+', to='api.financecategory'
                    ),
                ),
                (
                    'project',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='+',
                        to='api.project',
                    ),
                ),
            ],
            options={
                'ordering': ['next_date'],
            },
        ),
        migrations.CreateModel(
            name='Transaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'type',
                    models.CharField(
                        choices=[('income', 'Income'), ('expense', 'Expense'), ('transfer', 'Transfer')], max_length=10
                    ),
                ),
                ('date', models.DateField()),
                ('amount', models.DecimalField(decimal_places=2, max_digits=14)),
                ('counterparty', models.CharField(blank=True, max_length=255)),
                ('description', models.CharField(blank=True, max_length=255)),
                ('reference', models.CharField(blank=True, max_length=100)),
                (
                    'status',
                    models.CharField(choices=[('paid', 'Paid'), ('pending', 'Pending')], default='paid', max_length=10),
                ),
                ('paid_date', models.DateField(blank=True, null=True)),
                ('due_date', models.DateField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'account',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='transactions',
                        to='api.financeaccount',
                    ),
                ),
                (
                    'category',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='transactions',
                        to='api.financecategory',
                    ),
                ),
                (
                    'client',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='transactions',
                        to='api.client',
                    ),
                ),
                (
                    'created_by',
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='+',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'project',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='transactions',
                        to='api.project',
                    ),
                ),
                (
                    'recurring',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='occurrences',
                        to='api.recurringtransaction',
                    ),
                ),
                (
                    'to_account',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='transfers_in',
                        to='api.financeaccount',
                    ),
                ),
            ],
            options={
                'ordering': ['-date', '-id'],
                'indexes': [
                    models.Index(fields=['type', 'date'], name='api_transac_type_bef565_idx'),
                    models.Index(fields=['status', 'due_date'], name='api_transac_status_71a8c1_idx'),
                ],
            },
        ),
    ]
