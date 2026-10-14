from datetime import date
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from api.models import Client, FinanceAccount, FinanceCategory, Project, Transaction, User

API = '/api/v1/finance/'


class FinanceTest(TestCase):
    def test_finance(self):
        owner = User.objects.create_user('o', password='x', role='OWNER')
        pm = User.objects.create_user('p', password='x', role='PROJECT_MANAGER')
        owner_api, pm_api = APIClient(), APIClient()
        owner_api.force_authenticate(owner)
        pm_api.force_authenticate(pm)
        assert pm_api.get(f'{API}summary/').status_code == 403
        assert pm_api.get(f'{API}transactions/').status_code == 403

        bank = FinanceAccount.objects.get(name='Main bank account')
        cash = FinanceAccount.objects.get(name='Cash')
        bank.opening_balance = 1000
        bank.save()
        cat = lambda n: FinanceCategory.objects.get(name=n).id
        cl = Client.objects.create(client_name='Acme', contact_person='A')
        pr = Project.objects.create(client=cl, name='Launch', service_fee=5000)

        def tx(**kw):
            res = owner_api.post(f'{API}transactions/', {'account': bank.id, 'date': '2026-03-10', **kw}, format='json')
            assert res.status_code == 201, res.data
            return res.data

        inv = tx(
            type='income',
            amount='3000',
            category=cat('Client services'),
            project=pr.id,
            status='pending',
            due_date='2026-03-20',
        )
        assert inv['client'] == cl.id and inv['paid_date'] is None
        tx(type='income', amount='2000', category=cat('Client services'), project=pr.id)
        tx(type='expense', amount='800', category=cat('Freelancers & contractors'), project=pr.id)
        tx(type='expense', amount='1200', category=cat('Salaries'))
        tx(type='expense', amount='300', category=cat('Taxes'))
        tx(type='transfer', amount='500', to_account=cash.id)
        bad = owner_api.post(
            f'{API}transactions/',
            {'account': bank.id, 'date': '2026-03-10', 'type': 'expense', 'amount': '5', 'category': cat('Retainers')},
            format='json',
        )
        assert bad.status_code == 400 and 'category' in bad.data
        assert (
            owner_api.post(
                f'{API}transactions/',
                {
                    'account': bank.id,
                    'date': '2026-03-10',
                    'type': 'expense',
                    'amount': '0',
                    'category': cat('Salaries'),
                },
                format='json',
            ).status_code
            == 400
        )

        q = {'start': '2026-03-01', 'end': '2026-03-31'}
        s = owner_api.get(f'{API}summary/', q).data['pnl']
        assert (s['income'], s['gross_profit'], s['operating_profit'], s['net_profit']) == (5000, 4200, 3000, 2700), s
        assert s['gross_margin'] == 84.0 and s['net_margin'] == 54.0
        c = owner_api.get(f'{API}summary/', {**q, 'basis': 'cash'}).data
        assert c['pnl']['net_profit'] == -300, c['pnl']

        d = owner_api.get(f'{API}summary/', q).data
        bal = {a['name']: a['balance'] for a in d['accounts']}
        assert bal == {'Main bank account': 1000 + 2000 - 800 - 1200 - 300 - 500, 'Cash': 500}, bal
        assert d['receivables']['total'] == 3000
        proj = next(p for p in d['projects'] if p['id'] == pr.id)
        assert (proj['invoiced'], proj['collected'], proj['costs'], proj['to_invoice'], proj['profit']) == (
            5000,
            2000,
            800,
            0,
            4200,
        )

        assert (
            owner_api.post(
                f'{API}transactions/{inv["id"]}/mark_paid/', {'paid_date': '2026-03-25'}, format='json'
            ).status_code
            == 200
        )
        d = owner_api.get(f'{API}summary/', q).data
        assert d['receivables']['total'] == 0 and d['cash'] == 700 + 3000

        assert owner_api.delete(f'{API}categories/{cat("Salaries")}/').status_code == 400

        rent = owner_api.post(
            f'{API}recurring/',
            {
                'type': 'expense',
                'amount': '400',
                'account': bank.id,
                'category': cat('Rent & utilities'),
                'frequency': 'monthly',
                'next_date': '2026-01-31',
            },
            format='json',
        )
        assert rent.status_code == 201, rent.data
        with mock.patch('api.finance.timezone.localdate', return_value=date(2026, 3, 30)):
            owner_api.get(f'{API}transactions/')
            owner_api.get(f'{API}transactions/')
        bills = Transaction.objects.filter(recurring=rent.data['id']).order_by('date')
        assert [b.date for b in bills] == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 28)]
        assert all(b.status == 'pending' for b in bills)

        csv = owner_api.get(f'{API}transactions/export/', q)
        assert csv.status_code == 200 and b'Freelancers & contractors' in csv.content


class LocalizationTest(TestCase):
    def test_language_and_optional_email(self):
        owner = User.objects.create_user('o', password='x', role='OWNER')
        owner_api = APIClient()
        owner_api.force_authenticate(owner)
        res = owner_api.post(
            '/api/v1/users/',
            {'username': 'ed', 'first_name': 'Ed', 'password': 'pw12345!', 'role': 'EDITOR'},
            format='json',
        )
        assert res.status_code == 201, res.data
        assert (
            owner_api.post(
                '/api/v1/users/', {'username': 'x', 'password': 'pw12345!', 'role': 'EDITOR'}, format='json'
            ).status_code
            == 400
        )
        bad = owner_api.post(
            f'{API}transactions/',
            {'type': 'expense', 'amount': '0', 'date': '2026-01-01', 'account': FinanceAccount.objects.first().id},
            format='json',
            HTTP_ACCEPT_LANGUAGE='ru',
        )
        assert 'больше нуля' in str(bad.data), bad.data
        assert (
            owner_api.patch('/api/v1/users/me/', {'language': 'ru', 'role': 'EDITOR'}, format='json').data['language']
            == 'ru'
        )
        from django.utils.translation import gettext_lazy

        from api.views import notify

        owner.refresh_from_db()
        notify(
            [owner],
            gettext_lazy('New order'),
            gettext_lazy('You have a new order: %(title)s'),
            'x',
            params={'title': 'Reel'},
        )
        assert owner.notifications.get().message == 'У вас новый заказ: Reel'
