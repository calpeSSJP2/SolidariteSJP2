from django.views.generic import CreateView, ListView
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import redirect
from .forms import AccountStatementForm
from .models import AccountStatement
from .services import LedgerService
from django.db.models import Q
from datetime import datetime, time
from django.utils import timezone

from django.utils.dateparse import parse_date
from django.db.models import Q, Sum
from decimal import Decimal
from django.contrib.auth.mixins import LoginRequiredMixin
from accounts.models import User  # adjust if needed

class AccountStatementListView(LoginRequiredMixin, ListView):
    model = AccountStatement
    template_name = 'ledger/list_statement.html'
    context_object_name = 'transactions'
    paginate_by = 10
    ordering = ['-date', '-id']

    def get_queryset(self):
        qs = super().get_queryset().select_related('account')

        user = self.request.user
        active_role = self.request.session.get("active_role")

        # fallback
        if not active_role:
            active_role = user.roles.first().name if user.roles.exists() else None

        # ----------------------------
        # ACCESS RULES BASED ON ACTIVE ROLE
        # ----------------------------

        if active_role in ['officer', 'manager', 'itadmin']:
            pass  # full access

        elif active_role == 'auditor':
            pass  # maybe limited financial view

        elif active_role == 'ordinary_member':
            qs = qs.filter(account__member__user=user)

        else:
            qs = qs.none()

        # filters (unchanged)
        search = self.request.GET.get('search', '')
        txn_type = self.request.GET.get('transaction_type', '')
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')

        if search:
            qs = qs.filter(
                Q(account__account_number__icontains=search) |
                Q(account__member__user__first_name__icontains=search) |
                Q(account__member__user__last_name__icontains=search) |
                Q(reference__icontains=search)
            )

        if txn_type:
            qs = qs.filter(transaction_type=txn_type)

        if start_date:
            qs = qs.filter(date__date__gte=parse_date(start_date))

        if end_date:
            qs = qs.filter(date__date__lte=parse_date(end_date))

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # 🔥 Use full filtered queryset (not paginated)
        full_queryset = self.get_queryset()

        totals = full_queryset.aggregate(
            total_debit=Sum('debit'),
            total_credit=Sum('credit')
        )

        total_debit = totals['total_debit'] or Decimal('0.00')
        total_credit = totals['total_credit'] or Decimal('0.00')

        context['total_debit'] = total_debit
        context['total_credit'] = total_credit
        context['net_balance'] = total_credit - total_debit

        # Preserve filters
        context['search'] = self.request.GET.get('search', '')
        context['start_date'] = self.request.GET.get('start_date', '')
        context['end_date'] = self.request.GET.get('end_date', '')

        return context




class AccountStatementCreateView(CreateView):
    model = AccountStatement
    form_class = AccountStatementForm
    template_name = 'ledger/create_statement.html'
    success_url = reverse_lazy('ledger:account_statement_list')

    def form_valid(self, form):
        data = form.cleaned_data
        LedgerService.create_statement(
            account=data['account'],
            transaction_type=data['transaction_type'],
            debit=data['debit'],
            credit=data['credit'],
            reference=data.get('reference')
        )
        messages.success(self.request, "Account statement created successfully.")
        return redirect(self.success_url)  # ⬅ do NOT call super()

class AccountStatementListView1(ListView):
    model = AccountStatement
    template_name = 'ledger/list_statement.html'
    context_object_name = 'transactions'
    paginate_by = 20
    ordering = ['-date','-id']

    def get_queryset(self):
        qs = super().get_queryset().select_related('account')
        search = self.request.GET.get('search','')
        txn_type = self.request.GET.get('transaction_type','')

        if search:
            qs = qs.filter(
                Q(account__account_number__icontains=search) |
                Q(reference__icontains=search)
            )
        if txn_type:
            qs = qs.filter(transaction_type=txn_type)
        return qs


from django.views import View
from django.http import HttpResponse
import openpyxl
from .utils import FilterTransactionsMixin
from .models import AccountStatement
from django.views import View
from django.http import HttpResponse
import openpyxl
from django.db.models import Q
from ledger.models import AccountStatement
from accounts.models import MemberAccount

class ExportTransactionsExcelView1(View):
    def get(self, request, *args, **kwargs):
        statements = AccountStatement.objects.all()

        search = request.GET.get('search')
        if search:
            # Filter on fields of MemberAccount safely
            matching_accounts = MemberAccount.objects.filter(
                Q(account_number__icontains=search) | Q(member__user__first_name__icontains=search) | Q(
                    member__user__last_name__icontains=search)
            )

        start_date = request.GET.get('start_date')
        if start_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            start_dt = timezone.make_aware(
                datetime.combine(start_dt, time.min)
            )
            statements = statements.filter(date__gte=start_dt)

        end_date = request.GET.get('end_date')
        if end_date:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            end_dt = timezone.make_aware(
                datetime.combine(end_dt, time.max)
            )
            statements = statements.filter(date__lte=end_dt)

        # Generate Excel
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Account Statements"

        headers = ["Date", "Account Number", "Member Name", "Type", "Debit", "Credit", "Balance After", "Reference"]
        ws.append(headers)

        for stmt in statements:
            ws.append([
                stmt.date.strftime("%Y-%m-%d %H:%M"),
                stmt.account.account_number,
                f"{stmt.account.member.user.first_name} {stmt.account.member.user.last_name}",
                stmt.transaction_type.capitalize(),
                stmt.debit if stmt.debit > 0 else '',
                stmt.credit if stmt.credit > 0 else '',
                stmt.balance_after,
                stmt.reference,
            ])

        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = 'attachment; filename=account_statements.xlsx'
        wb.save(response)
        return response

from django.contrib.auth.mixins import LoginRequiredMixin
from accounts.models import User
from django.db.models import Q

class ExportTransactionsExcelView(LoginRequiredMixin, View):

    def get(self, request, *args, **kwargs):

        statements = AccountStatement.objects.select_related(
            'account__member__user'
        )

        user = request.user

        # ✅ ROLE-BASED ACCESS
        if not user.has_any_role('officer', 'manager',"itadmin"):
            statements = statements.filter(account__member__user=user)

        # ✅ SEARCH FILTER
        search = request.GET.get('search')
        if search:
            statements = statements.filter(
                Q(account__account_number__icontains=search) |
                Q(account__member__user__first_name__icontains=search) |
                Q(account__member__user__last_name__icontains=search) |
                Q(reference__icontains=search)
            )

        # ✅ START DATE FILTER
        start_date = request.GET.get('start_date')
        if start_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            start_dt = timezone.make_aware(
                datetime.combine(start_dt, time.min)
            )
            statements = statements.filter(date__gte=start_dt)

        # ✅ END DATE FILTER
        end_date = request.GET.get('end_date')
        if end_date:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            end_dt = timezone.make_aware(
                datetime.combine(end_dt, time.max)
            )
            statements = statements.filter(date__lte=end_dt)

        # =========================
        # Generate Excel
        # =========================
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Account Statements"

        headers = [
            "Date", "Account Number", "Member Name",
            "Type", "Debit", "Credit", "Balance After", "Reference"
        ]
        ws.append(headers)

        for stmt in statements:
            ws.append([
                stmt.date.strftime("%Y-%m-%d %H:%M"),
                stmt.account.account_number,
                f"{stmt.account.member.user.first_name} {stmt.account.member.user.last_name}",
                stmt.transaction_type.capitalize(),
                stmt.debit if stmt.debit > 0 else '',
                stmt.credit if stmt.credit > 0 else '',
                stmt.balance_after,
                stmt.reference,
            ])

        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = 'attachment; filename=account_statements.xlsx'

        wb.save(response)
        return response