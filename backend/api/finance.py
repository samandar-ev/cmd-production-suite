import calendar
import csv
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction as db_transaction
from django.db.models import ProtectedError, Q, Sum
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .models import FinanceAccount, FinanceCategory, Project, RecurringTransaction, Transaction, TxType
from .permissions import IsOwnerOrAdmin

ZERO = Decimal('0')
EXPENSE_GROUPS = ('direct', 'payroll', 'operating', 'tax')


def add_months(d, n):
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def next_occurrence(d, frequency):
    if frequency == 'weekly':
        return d + timedelta(weeks=1)
    return add_months(d, {'monthly': 1, 'quarterly': 3, 'yearly': 12}[frequency])


def post_due_recurring(today=None):
    today = today or timezone.localdate()
    with db_transaction.atomic():
        for r in RecurringTransaction.objects.select_for_update().filter(active=True, next_date__lte=today):
            while r.active and r.next_date <= today:
                if r.end_date and r.next_date > r.end_date:
                    r.active = False
                    break
                Transaction.objects.create(
                    type=r.type,
                    date=r.next_date,
                    due_date=r.next_date,
                    amount=r.amount,
                    account=r.account,
                    category=r.category,
                    project=r.project,
                    client=r.project.client if r.project else None,
                    counterparty=r.counterparty,
                    description=r.description,
                    status='pending',
                    recurring=r,
                )
                r.next_date = next_occurrence(r.next_date, r.frequency)
            r.save()


class AccountSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()

    class Meta:
        model = FinanceAccount
        fields = ['id', 'name', 'kind', 'opening_balance', 'archived', 'balance']

    def get_balance(self, obj):
        if 'balances' not in self.context:
            self.context['balances'] = account_balances()
        return self.context['balances'].get(obj.id, obj.opening_balance)


class CategorySerializer(serializers.ModelSerializer):
    type = serializers.CharField(read_only=True)
    transactions_count = serializers.IntegerField(source='transactions.count', read_only=True)

    class Meta:
        model = FinanceCategory
        fields = ['id', 'name', 'group', 'type', 'monthly_budget', 'archived', 'transactions_count']


def _check_entry(data, instance=None):
    get = lambda k: data.get(k, getattr(instance, k, None))
    if get('amount') is not None and get('amount') <= 0:
        raise ValidationError({'amount': _('Enter an amount greater than zero.')})
    category = get('category')
    if get('type') == TxType.TRANSFER:
        return
    if not category:
        raise ValidationError({'category': _('Choose a category.')})
    if category.type != get('type'):
        raise ValidationError(
            {
                'category': (
                    _('“%(name)s” is an income category.')
                    if category.type == 'income'
                    else _('“%(name)s” is an expense category.')
                )
                % {'name': category.name}
            }
        )


class TransactionSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='account.name', read_only=True)
    to_account_name = serializers.CharField(source='to_account.name', read_only=True, default=None)
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)
    category_group = serializers.CharField(source='category.group', read_only=True, default=None)
    project_name = serializers.CharField(source='project.name', read_only=True, default=None)
    client_name = serializers.CharField(source='client.client_name', read_only=True, default=None)
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = [
            'id',
            'type',
            'date',
            'amount',
            'account',
            'account_name',
            'to_account',
            'to_account_name',
            'category',
            'category_name',
            'category_group',
            'project',
            'project_name',
            'client',
            'client_name',
            'counterparty',
            'description',
            'reference',
            'status',
            'paid_date',
            'due_date',
            'is_overdue',
            'recurring',
            'created_at',
        ]
        read_only_fields = ['recurring']

    def get_is_overdue(self, obj):
        return obj.status == 'pending' and obj.due_date is not None and obj.due_date < timezone.localdate()

    def validate(self, data):
        _check_entry(data, self.instance)
        get = lambda k: data.get(k, getattr(self.instance, k, None))
        if get('type') == TxType.TRANSFER:
            if not get('to_account') or get('to_account') == get('account'):
                raise ValidationError({'to_account': _('Choose a different account to move the money to.')})
            data.update(category=None, project=None, client=None, status='paid')
        else:
            data['to_account'] = None
        if data.get('project') and not data.get('client'):
            data['client'] = data['project'].client
        if (get('status') or 'paid') == 'paid':
            data['paid_date'] = get('paid_date') or get('date')
        else:
            data['paid_date'] = None
        return data


class RecurringSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='account.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True, default=None)
    monthly_equivalent = serializers.SerializerMethodField()

    class Meta:
        model = RecurringTransaction
        fields = [
            'id',
            'type',
            'amount',
            'account',
            'account_name',
            'category',
            'category_name',
            'project',
            'project_name',
            'counterparty',
            'description',
            'frequency',
            'next_date',
            'end_date',
            'active',
            'monthly_equivalent',
        ]

    def get_monthly_equivalent(self, obj):
        return round(
            obj.amount
            * {'weekly': Decimal('52') / 12, 'monthly': 1, 'quarterly': Decimal(1) / 3, 'yearly': Decimal(1) / 12}[
                obj.frequency
            ],
            2,
        )

    def validate(self, data):
        _check_entry(data, self.instance)
        return data


class ProtectedDeleteMixin:
    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            raise ValidationError(
                {'error': _('It is used by transactions. Archive it instead to keep your history intact.')}
            ) from None


class AccountViewSet(ProtectedDeleteMixin, viewsets.ModelViewSet):
    permission_classes = [IsOwnerOrAdmin]
    serializer_class = AccountSerializer
    queryset = FinanceAccount.objects.all()


class CategoryViewSet(ProtectedDeleteMixin, viewsets.ModelViewSet):
    permission_classes = [IsOwnerOrAdmin]
    serializer_class = CategorySerializer
    queryset = FinanceCategory.objects.all()


class RecurringViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOwnerOrAdmin]
    serializer_class = RecurringSerializer
    queryset = RecurringTransaction.objects.select_related('account', 'category', 'project')


class TransactionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOwnerOrAdmin]
    serializer_class = TransactionSerializer

    def get_queryset(self):
        p = self.request.query_params
        qs = Transaction.objects.select_related('account', 'to_account', 'category', 'project', 'client')
        for key in ('type', 'status', 'category', 'project', 'client'):
            if p.get(key):
                qs = qs.filter(**{key: p[key]})
        if p.get('account'):
            qs = qs.filter(Q(account=p['account']) | Q(to_account=p['account']))
        if p.get('group'):
            qs = qs.filter(category__group=p['group'])
        if parse_date(p.get('start') or ''):
            qs = qs.filter(date__gte=p['start'])
        if parse_date(p.get('end') or ''):
            qs = qs.filter(date__lte=p['end'])
        if p.get('overdue'):
            qs = qs.filter(status='pending', due_date__lt=timezone.localdate())
        if p.get('q'):
            q = p['q']
            qs = qs.filter(
                Q(counterparty__icontains=q)
                | Q(description__icontains=q)
                | Q(reference__icontains=q)
                | Q(category__name__icontains=q)
                | Q(project__name__icontains=q)
                | Q(client__client_name__icontains=q)
            )
        return qs

    def list(self, request, *args, **kwargs):
        post_due_recurring()
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        tx = self.get_object()
        if tx.status == 'paid':
            raise ValidationError({'error': _('Already paid.')})
        tx.status = 'paid'
        tx.paid_date = parse_date(request.data.get('paid_date') or '') or timezone.localdate()
        if request.data.get('account'):
            tx.account = FinanceAccount.objects.get(pk=request.data['account'])
        tx.save()
        return Response(TransactionSerializer(tx).data)

    @action(detail=False, methods=['get'])
    def export(self, request):
        resp = HttpResponse(content_type='text/csv')
        resp['Content-Disposition'] = 'attachment; filename="transactions.csv"'
        w = csv.writer(resp)
        w.writerow(
            [
                _('Date'),
                _('Type'),
                _('Status'),
                _('Amount'),
                _('Account'),
                _('To account'),
                _('Category'),
                _('Group'),
                _('Client'),
                _('Project'),
                _('Counterparty'),
                _('Description'),
                _('Reference'),
                _('Paid date'),
                _('Due date'),
            ]
        )
        for t in self.get_queryset():
            w.writerow(
                [
                    t.date,
                    _(t.get_type_display()),
                    _(t.get_status_display()),
                    t.amount,
                    t.account.name,
                    t.to_account.name if t.to_account else '',
                    t.category.name if t.category else '',
                    _(t.category.get_group_display()) if t.category else '',
                    t.client.client_name if t.client else '',
                    t.project.name if t.project else '',
                    t.counterparty,
                    t.description,
                    t.reference,
                    t.paid_date or '',
                    t.due_date or '',
                ]
            )
        return resp


def account_balances():
    bal = {a.id: a.opening_balance for a in FinanceAccount.objects.all()}
    paid = Transaction.objects.filter(status='paid')
    sums = lambda qs, key: qs.values(key).annotate(s=Sum('amount')).values_list(key, 's')
    for acc, s in sums(paid.filter(type=TxType.INCOME), 'account'):
        bal[acc] += s
    for acc, s in sums(paid.filter(type__in=[TxType.EXPENSE, TxType.TRANSFER]), 'account'):
        bal[acc] -= s
    for acc, s in sums(paid.filter(type=TxType.TRANSFER), 'to_account'):
        bal[acc] += s
    return bal


def period_qs(start, end, basis):
    qs = Transaction.objects.exclude(type=TxType.TRANSFER)
    if basis == 'cash':
        return qs.filter(status='paid', paid_date__gte=start, paid_date__lte=end)
    return qs.filter(date__gte=start, date__lte=end)


def pnl(start, end, basis):
    rows = (
        period_qs(start, end, basis)
        .values('category', 'category__name', 'category__group')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )
    groups = {g: ZERO for g, _label in FinanceCategory.GROUPS}
    lines = defaultdict(list)
    for r in rows:
        groups[r['category__group']] += r['total']
        lines[r['category__group']].append({'id': r['category'], 'name': r['category__name'], 'total': r['total']})
    gross = groups['revenue'] - groups['direct']
    operating = gross - groups['payroll'] - groups['operating']
    net = operating + groups['other_income'] - groups['tax']
    income = groups['revenue'] + groups['other_income']
    pct = lambda v: round(float(v / groups['revenue'] * 100), 1) if groups['revenue'] else None
    return {
        'groups': groups,
        'lines': lines,
        'income': income,
        'expense': sum(groups[g] for g in EXPENSE_GROUPS),
        'gross_profit': gross,
        'operating_profit': operating,
        'net_profit': net,
        'gross_margin': pct(gross),
        'net_margin': pct(net),
    }


def monthly_trend(end, basis, months=12):
    first = add_months(end.replace(day=1), -(months - 1))
    field = 'paid_date' if basis == 'cash' else 'date'
    buckets = {add_months(first, i).strftime('%Y-%m'): {'income': ZERO, 'expense': ZERO} for i in range(months)}
    for t in period_qs(first, end, basis).values(field, 'type', 'amount'):
        buckets[t[field].strftime('%Y-%m')][t['type']] += t['amount']
    return [{'month': m, **v, 'net': v['income'] - v['expense']} for m, v in buckets.items()]


def pending_summary(type_, today):
    qs = Transaction.objects.filter(type=type_, status='pending').select_related('client', 'project', 'category')
    overdue = qs.filter(due_date__lt=today)
    return {
        'total': qs.aggregate(s=Sum('amount'))['s'] or ZERO,
        'overdue': overdue.aggregate(s=Sum('amount'))['s'] or ZERO,
        'overdue_count': overdue.count(),
        'items': TransactionSerializer(qs.order_by('due_date', 'date')[:8], many=True).data,
    }


def project_profitability():
    agg = defaultdict(lambda: {'invoiced': ZERO, 'collected': ZERO, 'costs': ZERO})
    for t in (
        Transaction.objects.filter(project__isnull=False)
        .exclude(type=TxType.TRANSFER)
        .values('project', 'type', 'status', 'amount')
    ):
        a = agg[t['project']]
        if t['type'] == TxType.INCOME:
            a['invoiced'] += t['amount']
            if t['status'] == 'paid':
                a['collected'] += t['amount']
        else:
            a['costs'] += t['amount']
    projects = (
        Project.objects.filter(Q(id__in=agg.keys()) | Q(service_fee__gt=0))
        .exclude(status='cancelled')
        .select_related('client')
    )
    out = []
    for p in projects:
        a = agg[p.id]
        fee = p.service_fee or ZERO
        profit = a['invoiced'] - a['costs']
        out.append(
            {
                'id': p.id,
                'name': p.name,
                'client': p.client.client_name,
                'status': p.status,
                'contract_value': fee,
                **a,
                'to_invoice': max(fee - a['invoiced'], ZERO),
                'outstanding': a['invoiced'] - a['collected'],
                'profit': profit,
                'margin': round(float(profit / a['invoiced'] * 100), 1) if a['invoiced'] else None,
            }
        )
    return sorted(out, key=lambda r: r['profit'], reverse=True)


class FinanceViewSet(viewsets.ViewSet):
    permission_classes = [IsOwnerOrAdmin]

    @action(detail=False, methods=['get'])
    def summary(self, request):
        post_due_recurring()
        today = timezone.localdate()
        p = request.query_params
        start = parse_date(p.get('start') or '') or today.replace(day=1)
        end = parse_date(p.get('end') or '') or today
        if end < start:
            raise ValidationError({'end': _('End date must be after the start date.')})
        basis = 'cash' if p.get('basis') == 'cash' else 'accrual'

        days = (end - start).days + 1
        prev = pnl(start - timedelta(days=days), start - timedelta(days=1), basis)
        cur = pnl(start, end, basis)
        months = (end.year - start.year) * 12 + end.month - start.month + 1

        spent = {line['id']: line['total'] for group in EXPENSE_GROUPS for line in cur['lines'][group]}
        budgets = [
            {
                'id': c.id,
                'name': c.name,
                'group': c.group,
                'budget': c.monthly_budget * months,
                'spent': spent.get(c.id, ZERO),
            }
            for c in FinanceCategory.objects.filter(monthly_budget__gt=0, archived=False).exclude(
                group__in=FinanceCategory.INCOME_GROUPS
            )
        ]

        balances = account_balances()
        accounts = [
            {'id': a.id, 'name': a.name, 'kind': a.kind, 'balance': balances[a.id]}
            for a in FinanceAccount.objects.filter(archived=False)
        ]
        cash = sum(balances.values(), ZERO)
        burn_from = add_months(today.replace(day=1), -3)
        burn = (
            period_qs(burn_from, today.replace(day=1) - timedelta(days=1), 'cash')
            .filter(type=TxType.EXPENSE)
            .aggregate(s=Sum('amount'))['s']
            or ZERO
        ) / 3

        by_client = (
            period_qs(start, end, basis)
            .filter(type=TxType.INCOME, client__isnull=False)
            .values('client', 'client__client_name')
            .annotate(total=Sum('amount'))
            .order_by('-total')[:8]
        )

        return Response(
            {
                'period': {'start': start, 'end': end, 'basis': basis, 'months': months},
                'pnl': cur,
                'previous': {k: prev[k] for k in ('income', 'expense', 'net_profit', 'gross_profit')},
                'trend': monthly_trend(end, basis),
                'budgets': budgets,
                'by_client': [
                    {'id': c['client'], 'name': c['client__client_name'], 'total': c['total']} for c in by_client
                ],
                'accounts': accounts,
                'cash': cash,
                'monthly_burn': round(burn, 2),
                'runway_months': round(float(cash / burn), 1) if burn > 0 and cash > 0 else None,
                'receivables': pending_summary(TxType.INCOME, today),
                'payables': pending_summary(TxType.EXPENSE, today),
                'projects': project_profitability(),
                'upcoming_recurring': RecurringSerializer(
                    RecurringTransaction.objects.filter(
                        active=True, next_date__lte=today + timedelta(days=30)
                    ).select_related('account', 'category', 'project'),
                    many=True,
                ).data,
            }
        )
