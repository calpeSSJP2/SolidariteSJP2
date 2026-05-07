from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, FormView, ListView, TemplateView, DetailView

from accounts.models import User, MemberAccount
from accounts.utils.rbac import has_role, has_any_role, get_user_roles

from .models import (  PeerToPeerLoan,  PeerLoanRepayment,  PeerLendingStatus,  PeerBorrowingStatus,)
from .forms import PeerToPeerLoanForm, PeerLoanRepaymentForm
from .services import PeerLoanRepaymentService


class PeerToPeerLoanCreateView(LoginRequiredMixin, CreateView):
    model = PeerToPeerLoan
    form_class = PeerToPeerLoanForm
    template_name = 'transact3_lending/loan_form_peer.html'
    success_url = reverse_lazy('transact3_lending:peer_loan_list')

    # ----------------------------------
    # RBAC PROTECTION
    # ----------------------------------
    def dispatch(self, request, *args, **kwargs):
        if not has_any_role(request.user, ["officer", "manager", "itadmin"]):
            messages.error(request, "You are not allowed to create peer loans.")
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)

    # ----------------------------------
    # FORM VALIDATION
    # ----------------------------------
    def form_valid(self, form):
        user = self.request.user

        try:
            lender = form.cleaned_data['lender']
            borrower = form.cleaned_data['borrower']

            # 🚫 Business rule
            if lender == borrower:
                form.add_error(None, "Lender and borrower cannot be the same account.")
                return self.form_invalid(form)

            with transaction.atomic():
                form.instance.created_by = user  # optional audit trail
                response = super().form_valid(form)

            messages.success(self.request, "Peer loan created successfully.")
            return response

        except Exception as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)

    # ----------------------------------
    # CONTEXT (CLEANED)
    # ----------------------------------
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # ⚠️ REMOVED PAGINATION FROM CREATE VIEW (WRONG LAYER)
        context['recent_loans'] = (
            PeerToPeerLoan.objects
            .select_related('lender__member', 'borrower__member')
            .order_by('-date')[:10]  # lightweight preview only
        )

        return context


##-----------------------------------------------


class PeerLoanContractDownloadView(View):
    def get(self, request, pk, *args, **kwargs):
        try:
            loan = PeerToPeerLoan.objects.get(pk=pk)
            if not loan.contract:
                raise Http404("No contract attached.")
            # Open file for download
            response = FileResponse(loan.contract.open(), as_attachment=True, filename=loan.contract.name.split('/')[-1])
            return response
        except PeerToPeerLoan.DoesNotExist:
            raise Http404("Loan not found.")

# -------------------------------
# Peer-to-Peer Loan Repayment
# -------------------------------
class PeerLoanRepaymentView(FormView):
    template_name = 'transact3_lending/repayment_form_peer.html'
    form_class = PeerLoanRepaymentForm

    def dispatch(self, request, *args, **kwargs):
        self.loan = get_object_or_404(PeerToPeerLoan, pk=kwargs['pk'])

        # 🔒 ONLY officers can record repayments
        if not has_any_role(request.user, ["officer", "manager", "itadmin"]):
            return HttpResponseForbidden(
                "Only officers are allowed to record peer loan repayments."
            )

        return super().dispatch(request, *args, **kwargs)


    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['peer_loan'] = self.loan
        kwargs['user'] = self.request.user
        return kwargs

    @transaction.atomic
    def form_valid(self, form):
        try:
            # Lock the loan to prevent race conditions
            self.loan = (
                PeerToPeerLoan.objects
                .select_for_update()
                .get(pk=self.loan.pk))

            repayment = PeerLoanRepayment(
                peer_loan=self.loan,
                paid_by=self.request.user,
                amount=form.cleaned_data['amount'])
            repayment.save()

        except ValidationError as e:
            form.add_error(None, e)
            return self.form_invalid(form)

        messages.success(self.request, "Repayment recorded successfully.")
        return redirect('transact3_lending:peer_loan_detail', pk=self.loan.pk)


# -------------------------------
# Peer-to-Peer Loan List

class PeerToPeerLoanListView(LoginRequiredMixin, ListView):
    model = PeerToPeerLoan
    template_name = 'transact3_lending/loan_list_peer.html'
    context_object_name = 'loans'
    paginate_by = 5

    # ----------------------------------
    # RBAC + DATA SCOPE
    # ----------------------------------
    def get_queryset(self):
        user = self.request.user

        qs = (
            PeerToPeerLoan.objects
            .select_related('lender__member', 'borrower__member')
            .order_by('-date')
        )

        # 🧑‍💼 STAFF: sees everything
        if has_any_role(user, ["manager", "officer", "itadmin", "auditor"]):
            return qs

        # 👤 CUSTOMER: sees only their own loans
        if user.account:
            return qs.filter(
                Q(borrower=user.account) | Q(lender=user.account)
            )

        # fallback (safe default)
        return PeerToPeerLoan.objects.none()




class PeerToPeerLoanDetailView(LoginRequiredMixin, DetailView):
    model = PeerToPeerLoan
    template_name = 'transact3_lending/loan_detail_peer.html'
    context_object_name = 'loan'

    # ----------------------------------
    # RBAC + OBJECT LEVEL SECURITY
    # ----------------------------------
    def get_queryset(self):
        user = self.request.user

        qs = (
            PeerToPeerLoan.objects
            .select_related(
                'lender__member',
                'borrower__member'
            )
            .prefetch_related('repayments')
        )

        # 🧑‍💼 STAFF: full access
        if has_any_role(user, ["manager", "officer", "itadmin", "auditor"]):
            return qs

        # 👤 CUSTOMER: only own loans
        if user.account:
            return qs.filter(
                Q(lender=user.account) | Q(borrower=user.account)
            )

        return PeerToPeerLoan.objects.none()

    # ----------------------------------
    # EXTRA SAFETY (double-check access)
    # ----------------------------------
    def get_object(self, queryset=None):
        obj = super().get_object(queryset)

        user = self.request.user

        if has_any_role(user, ["manager", "officer", "itadmin", "auditor"]):
            return obj

        # deny access if not owner
        if user.account and (
            obj.lender != user.account and obj.borrower != user.account
        ):
            raise Http404("You are not allowed to view this loan.")

        return obj

    # ----------------------------------
    # CONTEXT
    # ----------------------------------
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        loan = self.object

        total_paid = loan.total_paid or Decimal('0.00')
        remaining = loan.amount - total_paid

        context.update({
            'total_paid': total_paid,
            'remaining': max(remaining, Decimal('0.00')),
        })

        return context

# Lending/Borrowing Status Overview
# -------------------------------
class LendingStatusView(LoginRequiredMixin, TemplateView):
    template_name = 'transact3_lending/status_overview.html'  # Replace with actual template

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['lender_statuses'] = PeerLendingStatus.objects.select_related('lender')
        context['borrower_statuses'] = PeerBorrowingStatus.objects.select_related('borrower')
        return context

# Lender Status View
class PeerLendingStatusView(LoginRequiredMixin, ListView):
    model = PeerLendingStatus
    template_name = 'transact3_lending/lending_status.html'
    context_object_name = 'statuses'

    def get_queryset(self):
        return PeerLendingStatus.objects.all().select_related('lender')


class BorrowerLoanListView(LoginRequiredMixin, ListView):
    model = PeerToPeerLoan
    template_name = 'transact3_lending/borrower_lender_summary.html'
    context_object_name = 'loans'
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user

        # 🔐 RBAC: only members see their own loans
        if has_role(user, "ordinary_member"):
            account = getattr(user, "account", None)

            if not account:
                return PeerToPeerLoan.objects.none()

            return (
                PeerToPeerLoan.objects
                .filter(borrower=account)
                .select_related('lender')
                .prefetch_related('repayments')
                .order_by('-id')
            )

        # 👮 staff view (optional: full access or restrict further)
        return (
            PeerToPeerLoan.objects
            .all()
            .select_related('lender', 'borrower')
            .prefetch_related('repayments')
            .order_by('-id')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        loans = context["loans"]

        # ⚡ DB-level aggregation (FAST, no Python loops)
        totals = loans.aggregate(
            total_borrowed=Sum('amount')
        )

        # ⚠️ safe total_paid using annotation property fallback
        total_paid = sum(
            getattr(loan, "total_paid", Decimal("0.00"))
            for loan in loans
        )

        context.update({
            "total_borrowed": totals["total_borrowed"] or Decimal("0.00"),
            "total_paid": total_paid,
            "total_outstanding": (totals["total_borrowed"] or Decimal("0.00")) - total_paid,
            "user": self.request.user,
        })

        return context


class MultiLoanRepaymentView(ListView):
    template_name = 'transact3_lending/multi_repayment_form.html'
    model = PeerToPeerLoan
    context_object_name = 'loans'

    # ----------------------------------
    # SELECT BORROWER (RBAC SAFE)
    # ----------------------------------
    def get_selected_borrower(self):
        user = self.request.user

        # 👤 CUSTOMER → only their own account
        if has_role(user, "ordinary_member"):
            return getattr(user, "account", None)

        # 👮 STAFF → can select borrower
        borrower_id = self.request.GET.get("borrower_id")

        if borrower_id and has_any_role(user, ["officer", "manager", "itadmin"]):
            return MemberAccount.objects.filter(id=borrower_id).first()

        return None

    # ----------------------------------
    # QUERY LOANS
    # ----------------------------------
    def get_queryset(self):
        borrower = self.get_selected_borrower()

        if not borrower:
            return PeerToPeerLoan.objects.none()

        return (
            PeerToPeerLoan.objects
            .filter(borrower=borrower, is_fully_paid=False)
            .select_related('lender', 'borrower')
            .prefetch_related('repayments')
            .order_by('-amount')
        )

    # ----------------------------------
    # CONTEXT
    # ----------------------------------
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        loans = context['loans']
        borrower = self.get_selected_borrower()
        user = self.request.user

        context.update({
            'selected_borrower': borrower,
            'total_borrowed': loans.aggregate(total=Sum('amount'))['total'] or Decimal("0.00"),
            'total_paid': sum(getattr(l, "total_paid", 0) for l in loans),
            'search_query': self.request.GET.get('search', ''),
            'user': user,
        })

        # 👮 STAFF ONLY borrower search list
        if has_any_role(user, ["officer", "manager", "itadmin"]):
            search = self.request.GET.get('search')
            borrowers = MemberAccount.objects.all()

            if search:
                borrowers = borrowers.filter(
                    Q(member__user__first_name__icontains=search) |
                    Q(member__user__last_name__icontains=search)
                )

            context['borrowers'] = borrowers

        return context

    # ----------------------------------
    # POST (SECURED RBAC ACTION)
    # ----------------------------------
    def post(self, request, *args, **kwargs):
        user = request.user

        # 🔒 RBAC: only allowed roles can repay
        if not has_any_role(user, ["ordinary_member", "officer", "manager", "itadmin"]):
            messages.error(request, "You are not authorized to perform this action.")
            return redirect('transact3_lending:multi_repayment')

        borrower = self.get_selected_borrower()

        if not borrower:
            messages.error(request, "Please select a valid borrower.")
            return redirect('transact3_lending:multi_repayment')

        loans = self.get_queryset()
        any_success = False

        for loan in loans:
            field_name = f'loan_{loan.id}'
            amount_str = request.POST.get(field_name)

            if not amount_str:
                continue

            try:
                repayment_amount = Decimal(amount_str.replace(',', '').strip())
            except Exception:
                messages.warning(request, f"Invalid input for loan {loan.id}.")
                continue

            if repayment_amount <= 0:
                messages.warning(
                    request,
                    f"Amount must be greater than zero for loan {loan.id}."
                )
                continue

            try:
                repayment = PeerLoanRepayment(
                    peer_loan=loan,
                    amount=repayment_amount,
                    paid_by=user,
                    date=timezone.now().date()
                )
                repayment.save()
                any_success = True

            except ValidationError as e:
                messages.warning(request, f"Loan {loan.id}: {e}")

        if any_success:
            messages.success(request, "Repayments recorded successfully.")
        else:
            messages.error(request, "No valid repayments were processed.")

        return redirect('transact3_lending:multi_repayment')


class BorrowerLoanListSearchView(LoginRequiredMixin, ListView):
    model = PeerToPeerLoan
    template_name = 'transact3_lending/borrower_lender_summary.html'
    context_object_name = 'loans'
    paginate_by = 10

    # ----------------------------------
    # QUERYSET (RBAC FIXED)
    # ----------------------------------
    def get_queryset(self):
        user = self.request.user
        search = self.request.GET.get('search')

        base_qs = PeerToPeerLoan.objects.filter(
            is_fully_paid=False
        ).select_related('borrower__member', 'lender__member')

        # 👤 CUSTOMER: only own loans
        if has_any_role(user, ["ordinary_member"]):
            return base_qs.filter(borrower=user.account).order_by('-amount')

        # 🧑‍💼 STAFF: full visibility + search
        if search:
            base_qs = base_qs.filter(
                Q(borrower__member__user__first_name__icontains=search) |
                Q(borrower__member__user__last_name__icontains=search)
            )

        return base_qs.order_by('-amount')

    # ----------------------------------
    # CONTEXT (OPTIMIZED - NO DOUBLE QUERY)
    # ----------------------------------
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        loans = context['loans']  # already evaluated queryset

        total_borrowed = loans.aggregate(total=Sum('amount'))['total'] or 0
        total_paid = sum(loan.total_paid for loan in loans)

        context.update({
            'total_borrowed': total_borrowed,
            'total_paid': total_paid,
            'total_outstanding': total_borrowed - total_paid,
            'search_query': self.request.GET.get('search', ''),
            'user_roles': get_user_roles(self.request.user),
        })

        return context

