from django.db import migrations

DEFAULTS = {
    'revenue': ['Client services', 'Retainers', 'Ad management fees'],
    'other_income': ['Other income'],
    'direct': [
        'Freelancers & contractors',
        'Equipment rental',
        'Production costs',
        'Client ad spend',
        'Talent & models',
    ],
    'payroll': ['Salaries', 'Bonuses'],
    'operating': [
        'Rent & utilities',
        'Software & subscriptions',
        'Equipment purchases',
        'Marketing',
        'Transport & travel',
        'Bank fees',
        'Office & supplies',
        'Other expenses',
    ],
    'tax': ['Taxes'],
}


def seed(apps, schema_editor):
    Category = apps.get_model('api', 'FinanceCategory')
    Account = apps.get_model('api', 'FinanceAccount')
    if not Category.objects.exists():
        Category.objects.bulk_create(Category(name=n, group=g) for g, names in DEFAULTS.items() for n in names)
    if not Account.objects.exists():
        Account.objects.bulk_create([Account(name='Main bank account', kind='bank'), Account(name='Cash', kind='cash')])


class Migration(migrations.Migration):
    dependencies = [('api', '0012_finance')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
