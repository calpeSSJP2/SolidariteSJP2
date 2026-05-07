import logging
from decimal import Decimal
from itertools import chain

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView, FormView, ListView, DetailView

from accounts.models import (  IncomeSource,  ExpensePurpose,  MemberAccount,   SJP2_Account,
)

from .models import (    DepositTransaction,   DepositDueTransaction,   WithdrawalTransaction,    TransferTransaction,
    SJP2Transaction,)

from .forms import (   DepositForm,   MemberAccountSearchForm,   WithdrawalForm,  TransferForm,
    ExpenseForm,    ExternalIncomeForm,)

from .services import (  DepositDueTransactionService,   SJP2TransactionService,   WithdrawalTransactionService,
    TransferTransactionService,)

logger = logging.getLogger(__name__)
# -----------------------------
# 🔹 Shared Base Mixin for Forms
# -----------------------------
class TransactionCreateMixin(LoginRequiredMixin, CreateView):
    template_name = 'transact1_regular_deposit/transaction_form.html'
    title = ''
    button_label = 'Submit'

    def get_account(self):
        # ❌ OLD: self.request.user.account
        # ✔️ NEW: supports teller + customer
        account_id = self.kwargs.get("account_id") or self.request.GET.get("account")
        if account_id:
            return get_object_or_404(MemberAccount, pk=account_id)
        return getattr(self.request.user, "account", None)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()

        account = self.get_account()
        kwargs.update({'account': account})

        return kwargs

class RoleRequiredMixin:
    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_any_role(*self.allowed_roles):
            messages.error(request, "You do not have permission to perform this action.")
            return redirect("accounts:customer-dashboard")  # or any safe page
        return super().dispatch(request, *args, **kwargs)

class TransactionHistoryMixin:
    def get_transactions(self, account):
        return sorted(
            chain(
                account.deposit_transactions.all(),
                account.withdrawal_transactions.all(),
                account.transfers_sent.all(),
                account.transfers_received.all(),
            ),
            key=lambda x: x.timestamp,
            reverse=True   )[:5]


# -----------------------------
# 🔹 Deposit View
# -----------------------------
class DepositCreateView( TransactionHistoryMixin, CreateView):

    model = DepositTransaction
    form_class = DepositForm
    template_name = 'transact1_regular_deposit/transaction_form.html'

    title = 'Make a Deposit'
    button_label = 'Deposit Funds'
    success_url = reverse_lazy('transact1_regular_deposit:transaction-success')

    def get_account(self):
        account_id = self.kwargs.get("account_id") or self.request.GET.get("account")
        if account_id:
            return get_object_or_404(MemberAccount, pk=account_id)
        return getattr(self.request.user, "account", None)

    def form_valid(self, form):
        try:
            with transaction.atomic():
                txn = form.save(commit=False)

                account = self.get_account()   # ✔️ FIX

                # ❌ OLD: missing assignment
                # ✔️ NEW: explicitly bind account
                txn.account = account

                txn.deposit_due = form.cleaned_data["deposit_due"]

                DepositDueTransactionService.process(txn)

                self.object = txn

        except Exception as e:
            logger.exception("Deposit processing failed")
            form.add_error(None, f"Deposit failed: {str(e)}")
            return self.form_invalid(form)

        messages.success(self.request, "Deposit successful.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        account = self.get_account()   # ❌ FIX (was request.user.account)

        context.update({
            "transactions": self.get_transactions(account) if account else [],  # ✔️ SAFE
            "account": account,
            "title": self.title,
            "button_label": self.button_label
        })

        return context
##==============Let us use one transaction TellerDepositCreateView is similar to DepsitView

class TellerDepositCreateView(TransactionHistoryMixin, FormView):
    template_name = 'transact1_regular_deposit/transaction_form.html'
    form_class = DepositForm
    success_url = reverse_lazy('transact1_regular_deposit:transaction-success')

    title = 'Make a Deposit'
    button_label = 'Deposit Funds'

    # ✅ ADD THIS (you were missing it)
    def get_account(self):
        account_id = self.kwargs.get("account_id") or self.request.GET.get("account")
        if account_id:
            return get_object_or_404(MemberAccount, pk=account_id)
        return None  # teller must select account

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['account'] = self.get_account()   # ✅ unified source
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        account = self.get_account()   # ✅ now works

        context.update({
            "transactions": self.get_transactions(account) if account else [],
            "account": account,
            "title": self.title,
            "button_label": self.button_label
        })

        return context

    def form_valid(self, form):
        try:
            with transaction.atomic():
                txn = form.save(commit=False)

                account = self.get_account()

                # ✅ CRITICAL (same as DepositCreateView)
                txn.account = account

                txn.deposit_due = form.cleaned_data.get("deposit_due")

                DepositDueTransactionService.process(txn)

                self.object = txn

        except Exception as e:
            messages.error(self.request, f"Deposit failed: {str(e)}")
            return self.form_invalid(form)

        messages.success(self.request, f"Deposit successful for {txn.account}.")
        return super().form_valid(form)

class TellerTransactionSearchView(LoginRequiredMixin, FormView):
    template_name = "transact1_regular_deposit/account_search.html"
    form_class = MemberAccountSearchForm  # optional if you want a form for GET

    # These can be set dynamically from the URL conf
    action_url_name = None
    button_text = None
    button_color = 'primary'
    title = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        q = self.request.GET.get("q", "")
        accounts = MemberAccount.objects.none()

        if q:
            accounts = MemberAccount.objects.filter(
                Q(account_number__icontains=q) |
                Q(member__user__first_name__icontains=q) |
                Q(member__user__last_name__icontains=q)
            )

        context.update({
            "accounts": accounts,
            "query": q,
            "action_url_name": self.action_url_name,
            "button_text": self.button_text,
            "button_color": self.button_color,
            "title": self.title,
        })
        return context

    def get(self, request, *args, **kwargs):
        return self.render_to_response(self.get_context_data())

    def post(self, request, *args, **kwargs):
        q = request.POST.get("q", "")
        if q:
            return redirect(f"{request.path}?q={q}")
        return self.render_to_response(self.get_context_data())


class TellerDepositSearchView(LoginRequiredMixin, TemplateView):
    template_name = "transact1_regular_deposit/account_search.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        q = self.request.GET.get("q", "")
        accounts = []

        if q:
            accounts = MemberAccount.objects.filter(
                Q(account_number__icontains=q) |
                Q(member__user__first_name__icontains=q) |
                Q(member__user__last_name__icontains=q)
            ).select_related('member', 'member__user')

        context.update({
            "accounts": accounts,
            "query": q,
            "action_url_name": 'transact1_regular_deposit:deposit',  # for building URL
            "button_text": 'Deposit',
            "button_color": 'success',
            "title": 'Deposit – Search Member',
        })
        # For withdrawal search
        context.update({
            "accounts": accounts,
            "query": q,
            "action_url_name": 'transact1_regular_deposit:withdraw',
            "button_text": 'Withdraw',
            "button_color": 'danger',
            "title": 'Withdrawal – Search Member',
        })
        return context

    def get(self, request, *args, **kwargs):
        return self.render_to_response(self.get_context_data())

    def post(self, request, *args, **kwargs):
        # redirect to same page with query as GET parameter
        q = request.POST.get("q", "")
        if q:
            return redirect(f"{request.path}?q={q}")
        return self.render_to_response(self.get_context_data())



# -----------------------------
# 🔹 Withdrawal View
# -----------------------------
class WithdrawalCreateView(TransactionHistoryMixin, TransactionCreateMixin, FormView):
    model = WithdrawalTransaction
    form_class = WithdrawalForm
    title = 'Make a Withdrawal'
    button_label = 'Withdraw Funds'
    success_url = reverse_lazy('transact1_regular_deposit:transaction-success')

    # ✔️ SINGLE SOURCE OF TRUTH
    def get_account(self):
        account_id = self.kwargs.get('account_id') or self.request.GET.get('account')
        if account_id:
            return get_object_or_404(MemberAccount, pk=account_id)
        return None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['account'] = self.get_account()   # ✔️ FIX
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        account = self.get_account()  # ✔️ FIX

        context.update({
            "title": self.title,
            "button_label": self.button_label,
            "account": account,
            "transactions": self.get_transactions(account) if account else []
        })

        return context

    def form_valid(self, form):
        account = form.cleaned_data['account']
        amount = form.cleaned_data['amount']

        if amount <= 0:
            form.add_error('amount', 'Withdrawal amount must be positive.')
            return self.form_invalid(form)

        if amount > account.balance:
            form.add_error('amount', 'Withdrawal amount cannot be greater than your balance.')
            return self.form_invalid(form)

        try:
            # ❌ OLD: form.instance blindly passed
            # ✔️ NEW: ensure account is attached
            form.instance.account = account

            txn = WithdrawalTransactionService.process(form.instance)

            self.object = txn  # ✔️ IMPORTANT for CBV consistency

            messages.success(self.request, "Withdrawal successful.")
            return super().form_valid(form)

        except ValidationError as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)

        except Exception as e:
            messages.error(self.request, f"Error processing withdrawal: {str(e)}")
            return self.form_invalid(form)



# -----------------------------
# 🔹 Transfer View
# -----------------------------
class TransferCreateView(TransactionHistoryMixin, TransactionCreateMixin, FormView):
    model = TransferTransaction
    form_class = TransferForm
    title = 'Transfer Funds'
    button_label = 'Send Funds'
    success_url = reverse_lazy('transact1_regular_deposit:transaction-success')

    def get_account(self):
        account_id = self.kwargs.get('account_id') or self.request.GET.get('account')
        return get_object_or_404(MemberAccount, pk=account_id) if account_id else None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['account'] = self.get_account()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        account = self.get_account()

        context.update({
            "title": self.title,
            "button_label": self.button_label,
            "account": account,
            "transactions": self.get_transactions(account) if account else []
        })

        return context

    def form_valid(self, form):
        source_account = form.cleaned_data['source_account']
        destination_account = form.cleaned_data['destination_account']
        amount = form.cleaned_data['amount']

        if source_account == destination_account:
            form.add_error('destination_account', 'You cannot transfer to the same account.')
            return self.form_invalid(form)

        if amount <= 0:
            form.add_error('amount', 'Transfer amount must be positive.')
            return self.form_invalid(form)

        if amount > source_account.balance:
            form.add_error('amount', 'Transfer amount cannot be greater than your balance.')
            return self.form_invalid(form)

        try:
            # ❌ OLD: unsafe service input
            # ✔️ NEW: ensure DB consistency

            form.instance.source_account = source_account
            form.instance.destination_account = destination_account

            txn = TransferTransactionService.process(form.instance)

            self.object = txn

            messages.success(self.request, "Transfer completed successfully.")
            return super().form_valid(form)

        except ValidationError as e:
            messages.error(self.request, f"Validation Error: {str(e)}")
            return self.form_invalid(form)

        except Exception as e:
            messages.error(self.request, f"Error processing transfer: {str(e)}")
            return self.form_invalid(form)


class RegulaTransactionView(TransactionHistoryMixin, CreateView):
    template_name = 'transact1_regular_deposit/transaction_form.html'
    form_class = DepositForm

    def dispatch(self, request, *args, **kwargs):
        self.account = get_object_or_404(MemberAccount, pk=kwargs["account_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["account"] = self.account
        return kwargs

    def form_valid(self, form):
        form.instance.account = self.account
        self.object = form.save()
        return super().form_valid(form)

    def get_success_url(self):
        return self.request.path

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        transactions_list = self.get_transactions(self.account)

        # ✅ PAGINATION
        paginator = Paginator(transactions_list, 5)  # 5 per page
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context.update({
            "account": self.account,
            "transactions": page_obj,   # 🔥 use page_obj
            "page_obj": page_obj,
            "title": "Transaction",
            "button_label": "Submit"
        })

        return context

class MemberAccountSearchView(LoginRequiredMixin, TemplateView):
    template_name = "shared/account_search.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        query = self.request.GET.get("q", "").strip()
        accounts = []

        if query:
            accounts = MemberAccount.objects.select_related(
                "member", "member__user"
            ).filter(
                Q(account_number__icontains=query) |
                Q(member__user__first_name__icontains=query) |
                Q(member__user__last_name__icontains=query)
            )

        context.update({
            "query": query,
            "accounts": accounts,
        })
        return context

# -----------------------------
# 🔹 Transaction History View
# -----------------------------
# 🔹 External Income View
# -----------------------------
class ExternalIncomeCreateView(FormView):
    template_name = 'transact1_regular_deposit/external_income_form.html'
    form_class = ExternalIncomeForm
    success_url = reverse_lazy('transact1_regular_deposit:external-income-create')

    def form_valid(self, form):
        account = form.cleaned_data['account']
        source_name = form.cleaned_data['income_source']
        amount = form.cleaned_data['amount']
        description = form.cleaned_data['description']
        receipt_ref_no = form.cleaned_data['receipt_ref_no']

        income_source, _ = IncomeSource.objects.get_or_create(name=source_name)
        if receipt_ref_no:
            income_source.Receipt_ref_no = receipt_ref_no
            income_source.save()

        try:
            with transaction.atomic():
                SJP2TransactionService.external_income(
                    to_account=account,
                    amount=amount,
                    source=income_source,
                    description=description
                )
            messages.success(self.request, "External income recorded successfully.")
            return super().form_valid(form)
        except ValidationError as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)
        except Exception as e:
            messages.error(self.request, f"Error recording income: {e}")
            return self.form_invalid(form)



    def get_recent_operations(self):
        system_account = SJP2_Account.get_main_account()

        return SJP2Transaction.objects.filter(
            Q(transaction_type=SJP2Transaction.TransactionType.External_Income) |
            Q(transaction_type=SJP2Transaction.TransactionType.Expense),
            Q(to_sjp2_account=system_account) |
            Q(from_sjp2_account=system_account)
        ).order_by("-timestamp")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        operations = self.get_recent_operations()

        paginator = Paginator(operations, 6)  # 10 per page
        page_number = self.request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        context["recent_ops"] = page_obj  # IMPORTANT
        context["page_obj"] = page_obj
        context["is_paginated"] = page_obj.has_other_pages()

        return context
# -----------------------------
# 🔹 Expense View
# -----------------------------
class ExpenseCreateView(FormView):
    template_name = 'transact1_regular_deposit/expense_form.html'
    form_class = ExpenseForm
    success_url = reverse_lazy('transact1_regular_deposit:record-expense')

    def form_valid(self, form):
        account = form.cleaned_data['account']
        purpose_name = form.cleaned_data['expense_purpose']
        amount = form.cleaned_data['amount']
        description = form.cleaned_data['description']
        receipt_ref_no = form.cleaned_data['receipt_ref_no']

        expense_purpose, _ = ExpensePurpose.objects.get_or_create(name=purpose_name)
        if receipt_ref_no:
            expense_purpose.receipt_ref_no = receipt_ref_no
            expense_purpose.save()

        try:
            with transaction.atomic():
                SJP2TransactionService.expense(
                    from_sjp2_account=account,
                    amount=amount,
                    purpose=expense_purpose,
                    description=description
                )
            messages.success(self.request, "Expense recorded successfully.")
            return super().form_valid(form)
        except ValidationError as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)
        except Exception as e:
            messages.error(self.request, f"Error recording expense: {e}")
            return self.form_invalid(form)

    def get_recent_operations(self):
        system_account = SJP2_Account.get_main_account()

        return SJP2Transaction.objects.filter(

            Q(transaction_type=SJP2Transaction.TransactionType.External_Income) |
            Q(transaction_type=SJP2Transaction.TransactionType.Expense),
            Q(to_sjp2_account=system_account) |
            Q(from_sjp2_account=system_account)
        ).order_by("-timestamp")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        operations = self.get_recent_operations()

        paginator = Paginator(operations, 6)  # 10 per page
        page_number = self.request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        context["recent_ops"] = page_obj  # IMPORTANT
        context["page_obj"] = page_obj
        context["is_paginated"] = page_obj.has_other_pages()

        return context
# -----------------------------
# 🔹 SJP2 Transaction List & Detail Views
# -----------------------------
class SJP2TransactionDetailView(DetailView):
    model = SJP2Transaction
    template_name = 'transact1_regular_deposit/ssjp2_transaction_detail.html'
    context_object_name = 'transaction'


class SJP2TransactionListView(ListView):
    model = SJP2Transaction
    template_name = 'transact1_regular_deposit/ssjp2_transaction_list.html'
    context_object_name = 'processed_transactions'
    paginate_by = 10

    def get_queryset(self):
        return SJP2Transaction.objects.select_related(
            'from_member_account',
            'from_sjp2_account',
            'to_member_account',
            'to_sjp2_account',
            'income_source',
            'expense_purpose',
            'distribution_purpose',
        ).order_by('-timestamp', '-id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_transactions = self.get_queryset()
        page_obj = context['page_obj']
        paginated_transactions = page_obj.object_list

        running_balance = Decimal('0.00')
        if page_obj.start_index() > 1:
            for tx in all_transactions[:page_obj.start_index() - 1]:
                running_balance += self._get_signed_amount(tx)

        processed = []
        for tx in paginated_transactions:
            debit = credit = Decimal('0.00')
            if tx.transaction_type in [
                SJP2Transaction.TransactionType.Expense,
                SJP2Transaction.TransactionType.Withdrawal,
                SJP2Transaction.TransactionType.Interest_Distribution,
            ]:
                debit = tx.amount
                running_balance -= debit
            elif tx.transaction_type == SJP2Transaction.TransactionType.Transfer:
                if tx.from_sjp2_account:
                    debit = tx.amount
                    running_balance -= debit
                elif tx.to_sjp2_account:
                    credit = tx.amount
                    running_balance += credit
            else:
                credit = tx.amount
                running_balance += credit

            processed.append({
                'transaction': tx,
                'debit': debit,
                'credit': credit,
                'balance': running_balance,
            })

        context['processed_transactions'] = processed
        context['total_amount'] = sum(self._get_signed_amount(tx) for tx in all_transactions)
        return context

    def _get_signed_amount(self, tx):
        if tx.transaction_type in [
            SJP2Transaction.TransactionType.Expense,
            SJP2Transaction.TransactionType.Withdrawal,
            SJP2Transaction.TransactionType.Interest_Distribution,
        ]:
            return -tx.amount
        elif tx.transaction_type == SJP2Transaction.TransactionType.Transfer:
            if tx.from_sjp2_account:
                return -tx.amount
            elif tx.to_sjp2_account:
                return tx.amount
        return tx.amount
