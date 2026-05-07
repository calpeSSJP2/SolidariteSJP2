from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from .models import LoanWorkflow
from accounts.utils.rbac import has_any_role, has_role, has_active_role
from .forms import MoveStageForm
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import (
    TemplateView, DetailView, CreateView, ListView, FormView)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import TemplateView, View

from django.contrib import messages

from .models import Loan, LoanWorkflow

from accounts.models import SJP2_Account, MemberAccount
from ledger.models import AccountStatement
from ledger.services import LedgerService
from transact1_regular_deposit.models import SJP2Transaction
from transact3_lending.models import PeerToPeerLoan, PeerLoanRepayment

from .models import Loan, LoanPayment
from .forms import ( LoanRequestForm, LoanPaymentForm,  TopUpLoanForm,   AccountLookupForm,
    EmergencyLoanRequestForm,)
from .services import LoanLimitService


class TellerAccountSearchView(LoginRequiredMixin, TemplateView):
    template_name = "transact2_loans/member_search.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get("q", "")

        # Filter accounts based on search query
        if query:
            accounts = MemberAccount.objects.filter(
                Q(account_number__icontains=query) |
                Q(member__user__first_name__icontains=query) |
                Q(member__user__last_name__icontains=query)
            ).select_related('member', 'member__user')
        else:
            accounts = []

        context.update({
            "accounts": accounts,
            "query": query,
            "action_url_name": 'transact2_loans:loan_action',  # Adjust this to the correct URL name for loan creation
            "button_text": 'Create Loan',
            "button_color": 'success',
            "title": 'Loan – Search Member',
        })
        return context



class LoanRequestView(View):
    template_name = 'transact2_loans/loan_request_form.html'

    def get_latest_regular_loan(self, account):
        """
        Returns the latest REGULAR loan that is ACTIVE or PENDING
        """
        return (
            Loan.objects.open_loans_for_account(account)
            .filter( loan_type=Loan.LoanType.REGULAR,
                status__in=[Loan.LoanStatus.ACTIVE, Loan.LoanStatus.PENDING],   )
            .order_by('-issued_on')
            .first()  )

    def dispatch(self, request, *args, **kwargs):
        """
        Centralized gatekeeper for both GET and POST
        Handles:
        - Authorization
        - Loan state rules
        """

        # 1️⃣ Always resolve account first
        self.account = get_object_or_404(MemberAccount, pk=kwargs['account_id'])

        # 2️⃣ 🔒 Authorization MUST be global (not conditional)
        if not request.user.has_any_role('officer','itadmin'):
            messages.error(request, "Only officers or managers ot admin  can create loans.")
            return redirect("accounts:customer-dashboard")

        # 3️⃣ Fetch existing loan AFTER auth
        self.existing_loan = self.get_latest_regular_loan(self.account)

        # 4️⃣ Apply business rules
        if self.existing_loan:

            # 🚫 Case 1: ACTIVE loan with balance → redirect to options (top-up/emergency)
            if (
                    self.existing_loan.status == Loan.LoanStatus.ACTIVE
                    and self.existing_loan.balance > 0
            ):
                messages.warning(
                    request,
                    "Active loan detected. You can request a top-up or emergency loan instead."
                )
                return redirect(
                    'transact2_loans:loan_action',
                    account_id=self.account.id
                )

            # 🚫 Case 2: PENDING loan → block completely
            if self.existing_loan.status == Loan.LoanStatus.PENDING:
                messages.error(
                    request,
                    "You already have a pending regular loan. Please wait for approval."
                )
                return redirect('transact2_loans:loan_list')

            # ✅ Case 3: ACTIVE but fully paid → allow new request
            # (no action needed, just continue)

        # 5️⃣ Proceed normally
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, account_id):
        form = LoanRequestForm(
            user=request.user,
            account=self.account
        )
        return render(
            request,
            self.template_name,
            {'form': form, 'account': self.account}
        )

    def post(self, request, account_id):
        form = LoanRequestForm(
            request.POST,
            user=request.user,
            account=self.account
        )

        if form.is_valid():
            loan = form.save(commit=False)
            loan.account = self.account
            #loan.officer = request.user
            loan.status = Loan.LoanStatus.PENDING
            loan.save()

            messages.success(
                request,
                "Loan request submitted successfully. Awaiting approval."
            )
            return redirect(
                'transact2_loans:loan_detail',
                pk=loan.pk
            )

        return render(
            request,
            self.template_name,
            {'form': form, 'account': self.account}
        )



#########################################################account>memeberprof>user
class TopUpLoanCreateView(FormView):
    template_name = 'transact2_loans/topup_request_form.html'
    form_class = TopUpLoanForm

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_any_role('officer',"itadmin"):
            messages.error(request, "Only officers can create loans.")
            return redirect("accounts:customer-dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_loan(self):
        return get_object_or_404(Loan, pk=self.kwargs['loan_id'])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        loan = self.get_loan()
        kwargs['loan'] = loan
        kwargs['user'] = self.request.user
        return kwargs

    # 🔥 REPLACE THIS METHOD
    def form_valid(self, form):
        new_loan = form.save(commit=False)

        new_loan.status = Loan.LoanStatus.PENDING
        new_loan.save()

        messages.success(self.request, "Top-up request submitted successfully.")
        return redirect('transact2_loans:loan_detail', pk=new_loan.pk)
############
class TopUpLoanCreateView1(FormView):
    template_name = 'transact2_loans/topup_request_form.html'
    form_class = TopUpLoanForm

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_any_role('officer', "itadmin"):
            messages.error(request, "Only officers can create loans.")
            return redirect("accounts:customer-dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_loan(self):
        return get_object_or_404(Loan, pk=self.kwargs['loan_id'])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        loan = self.get_loan()
        kwargs['loan'] = loan
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        original = form.original_loan

        if not original.can_be_topped_up:
            form.add_error(None, "This loan is not eligible for top-up.")
            return self.form_invalid(form)

        try:
            new_loan = Loan(
                account=original.account,
                loan_type=original.loan_type,
                amount=form.cleaned_data['amount'],
                term_months=form.cleaned_data['term_months'],
                top_up_of=original,
                status=Loan.LoanStatus.PENDING,
            )

            new_loan.save()

        except ValidationError as e:
            form.add_error(None, e)
            return self.form_invalid(form)

        messages.success(
            self.request,
            "Top-up request submitted successfully."
        )
        return redirect('transact2_loans:loan_detail', pk=new_loan.pk)

class EmergencyLoanRequestView(View):
    template_name = "transact2_loans/emergency_loan_form.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_any_role('officer', "itadmin"):
            messages.error(request, "Only officers can create loans.")
            return redirect("accounts:customer-dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, account_id):
        account = get_object_or_404(MemberAccount, pk=account_id)

        form = EmergencyLoanRequestForm(account=account)

        return render(request, self.template_name, {
            "form": form,
            "account": account
        })

    def post(self, request, account_id):
        account = get_object_or_404(MemberAccount, pk=account_id)

        form = EmergencyLoanRequestForm(request.POST, account=account)

        if form.is_valid():
            try:
                with transaction.atomic():
                    loan = form.save(commit=False)

                    loan.account = account
                    loan.loan_type = Loan.LoanType.EMERGENCY
                    loan.term_months = Loan.TermChoices.THREE_MONTHS
                    loan.status = Loan.LoanStatus.PENDING
                    loan.officer = request.user

                    loan.save()

                messages.success(request, "Emergency loan request submitted successfully.")
                return redirect("transact2_loans:loan_detail", pk=loan.pk)

            except ValidationError as e:
                form.add_error(None, e)

        return render(request, self.template_name, {
            "form": form,
            "account": account
        })


class LoanOptionsView(TemplateView):
    template_name = "transact2_loans/loan_options.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        account_id = self.kwargs.get("account_id")
        account = get_object_or_404(MemberAccount, pk=account_id)

        context["account"] = account

        # Get latest active/pending regular loan
        active_loan = (  Loan.objects.filter(
                account=account,
                loan_type=Loan.LoanType.REGULAR,
                status__in=[            Loan.LoanStatus.ACTIVE,
                    Loan.LoanStatus.PENDING        ]        )
            .order_by("-issued_on")
            .first()    )
        recent_ops = (  LoanPayment.objects
            .filter(loan__account=account)
            .select_related("loan")
            .order_by("-id")[:5] )
        context["active_loan"] = active_loan

        # ============================
        # CASE 1: Has active loan
        # ============================
        if active_loan:
            context.update({
                "show_topup": True,
                "loan": active_loan,
                "topup_form": TopUpLoanForm(
                    loan=active_loan,
                    user=self.request.user
                ),
                "paid_ratio_percent": (
                    (active_loan.total_paid / active_loan.total_payable * 100)
                    if active_loan.total_payable else 0
                ),
                "recent_ops": recent_ops,
            })

        # ============================
        # CASE 2: No active loan
        # ============================
        else:
            context.update({
                "show_topup": False,
                "regular_form": LoanRequestForm(
                    account=account,
                    user=self.request.user
                )
            })

        # ============================
        # Emergency ALWAYS available
        # ============================
        context["show_emergency"] = True

        return context

class LoanActionView(TemplateView):
    template_name = 'transact2_loans/loan_unified_Regular_topup.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        account_id = self.kwargs.get('account_id')
        member_account = get_object_or_404(MemberAccount, pk=account_id)
        #member_id = self.kwargs.get('member_id')
        #member_account = get_object_or_404(MemberAccount, member_id=member_id)

        context['member_account'] = member_account

        open_regular_loans = Loan.objects.open_loans_for_account(member_account).filter(
            loan_type=Loan.LoanType.REGULAR
        )

        # ✅ ALWAYS AVAILABLE
        recent_ops = (
            LoanPayment.objects
            .filter(loan__account=member_account)
            .select_related("loan")
            .order_by("-id")[:5]
        )

        context["recent_ops"] = recent_ops  # 🔥 MOVE HERE

        if open_regular_loans.exists():
            loan = open_regular_loans.latest('issued_on')

            context.update({
                'show_topup': True,
                'loan': loan,
                'topup_form': TopUpLoanForm(loan=loan, user=self.request.user),
                'show_regular': False,
            })

        else:
            context.update({
                'show_topup': False,
                'show_regular': True,
                'regular_form': LoanRequestForm(account=member_account, user=self.request.user),
            })

        context['show_emergency'] = True
        return context


@method_decorator(login_required, name='dispatch')
class ApproveLoanView1(View):
    """
    Approves a pending loan, disburses principal, and posts interest.
    Idempotent: repeated clicks won't double-disburse.
    """

    def post(self, request, *args, **kwargs):
        loan = Loan.objects.select_for_update().get(pk=self.kwargs['loan_id'])
        ##Do'n't approve if youare not manager
        if not request.user.has_role('manager'):
            messages.error(request, "Only managers can approve loans.")
            return redirect('transact2_loans:loan_detail', pk=loan.pk)
               # Only allow approval if loan is PENDING
        if loan.status != Loan.LoanStatus.PENDING:
            messages.warning(request, "Loan has already been approved or processed.")
            return redirect('transact2_loans:loan_detail', pk=loan.id)

        with transaction.atomic():
            # 1️⃣ Approve loan
            loan.status = Loan.LoanStatus.ACTIVE
            loan.approved_by = request.user
            loan.save(update_fields=['status', 'approved_by'])

            # 2️⃣ Disburse principal if not already done
            already_posted = AccountStatement.objects.filter(
                reference=f"Loan ID {loan.pk}",
                transaction_type=AccountStatement.TransactionType.LOAN_ISSUED
            ).exists()

            if not already_posted:
                net_disbursed = loan.amount - loan.interest_amount

                LedgerService.create_statement(
                    account=loan.account,
                    transaction_type=AccountStatement.TransactionType.LOAN_ISSUED,
                    debit=net_disbursed,
                    credit=Decimal("0.00"),
                    reference=f"Loan ID {loan.pk}", )

            # 3️⃣ Post interest to SJP2 (only once)
            system_account = SJP2_Account.get_main_account()
            if not system_account:
                raise ValidationError("Missing SJP2 system account.")

            already_sjp2 = SJP2Transaction.objects.filter(
                from_member_account=loan.account,
                to_sjp2_account=system_account,
                transaction_type=SJP2Transaction.TransactionType.Loan_Interest,
                description=f"Loan Interest {loan.pk}" ).exists()

            if not already_sjp2:
                SJP2Transaction.objects.create( from_member_account=loan.account,
                                                to_sjp2_account=system_account,
                                                transaction_type=SJP2Transaction.TransactionType.Loan_Interest,
                                                amount=loan.interest_amount,
                                                description=f"Loan Interest {loan.pk}" )

        messages.success(request, "Loan approved and funds disbursed successfully!")
        return redirect('transact2_loans:loan_detail', pk=loan.id)




class RejectLoanView(LoginRequiredMixin, View):
    """
    Reject a pending loan with a mandatory reason.
    Only managers are allowed to reject.
    """

    def post(self, request, *args, **kwargs):
        loan = get_object_or_404(Loan, pk=self.kwargs.get('loan_id'))

        # ✅ Restrict to managers only
        if not request.user.has_role('manager'):
            messages.error(request, "Only managers can reject loans.")
            return redirect('transact2_loans:loan_detail', pk=loan.pk)

        # ✅ Loan must still be pending
        if loan.status != Loan.LoanStatus.PENDING:
            messages.warning(request, "Loan cannot be rejected; it is already processed.")
            return redirect('transact2_loans:loan_detail', pk=loan.pk)

        # ✅ Get rejection reason
        reason = request.POST.get("rejection_reason", "").strip()

        if not reason:
            messages.error(request, "Rejection reason is required.")
            return redirect('transact2_loans:loan_detail', pk=loan.pk)

        # ✅ Perform rejection safely
        with transaction.atomic():
            loan.status = Loan.LoanStatus.REJECTED
            loan.rejected_reason = reason
            loan.rejected_on = timezone.now()
            loan.rejected_by = request.user  # make sure this field exists
            loan.save(update_fields=[
                "status",
                "rejected_reason",
                "rejected_on",
                "rejected_by",
            ])

        messages.success(request, "Loan rejected successfully.")
        return redirect('transact2_loans:loan_detail', pk=loan.pk)

@method_decorator(login_required, name='dispatch')
class ApproveLoanView(View):
    """
    Approves a pending loan, disburses principal, and posts interest.
    Idempotent: repeated clicks won't double-disburse.
    """

    def post(self, request, *args, **kwargs):

        with transaction.atomic():

            # LOCK row inside transaction
            loan = Loan.objects.select_for_update().get(
                pk=self.kwargs['loan_id']
            )

            # Only managers can approve
            if not request.user.has_role('manager'):
                messages.error(request, "Only managers can approve loans.")
                return redirect('transact2_loans:loan_detail', pk=loan.pk)

            # Only allow approval if loan is pending
            if loan.status != Loan.LoanStatus.PENDING:
                messages.warning(
                    request,
                    "Loan has already been approved or processed."
                )
                return redirect('transact2_loans:loan_detail', pk=loan.id)

            # 1️⃣ Approve loan
            loan.status = Loan.LoanStatus.ACTIVE
            loan.approved_by = request.user
            loan.save(update_fields=['status', 'approved_by'])

            # 2️⃣ Disburse principal if not already done
            already_posted = AccountStatement.objects.filter(
                reference=f"Loan ID {loan.pk}",
                transaction_type=AccountStatement.TransactionType.LOAN_ISSUED
            ).exists()

            if not already_posted:
                net_disbursed = loan.amount - loan.interest_amount

                LedgerService.create_statement(
                    account=loan.account,
                    transaction_type=AccountStatement.TransactionType.LOAN_ISSUED,
                    debit=net_disbursed,
                    credit=Decimal("0.00"),
                    reference=f"Loan ID {loan.pk}",
                )

            # 3️⃣ Post interest to SJP2 (only once)
            system_account = SJP2_Account.get_main_account()

            if not system_account:
                raise ValidationError("Missing SJP2 system account.")

            already_sjp2 = SJP2Transaction.objects.filter(
                from_member_account=loan.account,
                to_sjp2_account=system_account,
                transaction_type=SJP2Transaction.TransactionType.Loan_Interest,
                description=f"Loan Interest {loan.pk}"
            ).exists()

            if not already_sjp2:
                SJP2Transaction.objects.create(
                    from_member_account=loan.account,
                    to_sjp2_account=system_account,
                    transaction_type=SJP2Transaction.TransactionType.Loan_Interest,
                    amount=loan.interest_amount,
                    description=f"Loan Interest {loan.pk}")
        messages.success( request, "Loan approved and funds disbursed successfully!" )
        return redirect('transact2_loans:loan_detail', pk=loan.id)


class LoanDetailView(DetailView):
    model = Loan
    template_name = 'transact2_loans/loan_detail.html'
    context_object_name = 'loan'

    def get_queryset(self):
        user = self.request.user

        # Staff roles: full access
        if user.has_any_role('manager', 'auditor', 'officer', 'verifier', 'itadmin'):
            return Loan.objects.all()

        # Members: only own loans
        if hasattr(user, "membersprofile"):
            return Loan.objects.filter(account=user.membersprofile.account)

        return Loan.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        loan = self.object
        user = self.request.user

        # ----------------------------
        # BUSINESS CALCULATIONS
        # ----------------------------
        context['paid_ratio_percent'] = (
            (loan.total_paid / loan.total_payable * 100)
            if loan.total_payable else 0
        )

        # ----------------------------
        # LOAN RELATIONSHIP LOGIC
        # ----------------------------
        context['is_current'] = not loan.topups.exists()

        # ----------------------------
        # ROLE-BASED PERMISSIONS (IMPORTANT FIX)
        # ----------------------------
        context['can_approve'] = (
            user.has_role('manager')
            and loan.status == Loan.LoanStatus.PENDING
        )

        context['can_reject'] = (
            user.has_role('manager')
            and loan.status == Loan.LoanStatus.PENDING
        )

        context['can_topup'] = (
            loan.status == Loan.LoanStatus.ACTIVE
            and loan.balance > 0
            and user.has_any_role('officer', 'manager') )

        context['can_view_sensitive'] = user.has_any_role(
            'manager', 'officer', 'auditor', 'itadmin' )

        return context



class PendingLoanView(LoginRequiredMixin, TemplateView):
    template_name = "transact2_loans/pending_loans.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user

        # ----------------------------
        # BASE QUERY (ALL PENDING)
        # ----------------------------
        pending_loans = Loan.objects.filter(
            status=Loan.LoanStatus.PENDING
        ).select_related(
            "account",
            "account__member",
            "account__member__user"
        ).order_by("-issued_on")

        # ----------------------------
        # ROLE FILTER (IMPORTANT)
        # ----------------------------
        if not user.has_any_role("manager", "officer", "auditor", "itadmin"):
            # members should NOT see all pending loans
            pending_loans = pending_loans.filter(account=user.membersprofile.account)

        # ----------------------------
        # GROUPING
        # ----------------------------
        context["pending_regular_loans"] = pending_loans.filter(
            loan_type=Loan.LoanType.REGULAR,
            top_up_of__isnull=True
        )

        context["pending_topups"] = pending_loans.filter(
            top_up_of__isnull=False
        )

        context["pending_emergency_loans"] = pending_loans.filter(
            loan_type=Loan.LoanType.EMERGENCY
        )

        # ----------------------------
        # TOTAL COUNTS (UI STATS)
        # ----------------------------
        context["total_pending"] = pending_loans.count()
        context["total_regular"] = context["pending_regular_loans"].count()
        context["total_topups"] = context["pending_topups"].count()
        context["total_emergency"] = context["pending_emergency_loans"].count()

        return context

class LoanListView(ListView):
    model = Loan
    template_name = 'transact2_loans/loan_list.html'
    context_object_name = 'loans'
    paginate_by = 10  # Show 10 loans per page

    def get_queryset(self):
        user = self.request.user
        if user.has_any_role('manager', 'auditor', 'officer', 'verifier', 'itadmin'):
            return Loan.objects.all()  # Allow access to all loans
        return Loan.objects.filter(account=user.account)  # Customers see their own


@method_decorator(csrf_exempt, name='dispatch')
class CheckPeerLoansView(View):
    """AJAX endpoint to check unpaid peer-to-peer loans for a borrower"""

    def post(self, request, *args, **kwargs):
        loan = get_object_or_404(Loan, pk=self.kwargs['loan_id'])

        unpaid_peer_loans = PeerToPeerLoan.objects.filter(
            borrower=loan.account,
            is_fully_paid=False
        )

        if unpaid_peer_loans.exists():
            loans_data = [
                {
                    "id": l.id,
                    "lender_name": l.lender.member.user.get_full_name(),
                    "amount": f"{l.amount:.2f}",
                }
                for l in unpaid_peer_loans
            ]

            return JsonResponse({
                "requires_confirmation": True,
                "loans": loans_data
            })

        return JsonResponse({"requires_confirmation": False})




class AccountLookupView(ListView):
    model = MemberAccount
    template_name = 'transact2_loans/account_lookup.html'
    context_object_name = 'accounts'
    paginate_by = 5  # Show 5 accounts per page

    def get_queryset(self):
        queryset = super().get_queryset().order_by('account_number')  # or '-opened_on' etc.
        form = AccountLookupForm(self.request.GET)

        if form.is_valid():
            account_number = form.cleaned_data.get('account_number')
            account_name = form.cleaned_data.get('account_name')

            if account_number or account_name:
                queryset = queryset.filter(
                    Q(account_number__icontains=account_number) |
                    Q(member__user__first_name__icontains=account_name) |
                    Q(member__user__last_name__icontains=account_name)
                ).distinct()

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = AccountLookupForm(self.request.GET)
        context['form'] = form

        # Keep existing GET parameters for pagination
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            query_params.pop('page')
        context['querystring'] = query_params.urlencode()

        return context


class LoanSummaryView(LoginRequiredMixin, DetailView):
    model = Loan
    template_name = 'transact2_loans/loan_summary.html'
    context_object_name = 'loan'


class MemberLoanListView(ListView):
    model = Loan
    template_name = 'transact2_loans/Loan_repport.html'
    context_object_name = 'loans'
    paginate_by = 5

    def get_queryset(self):
        loans = Loan.objects.all()
        # ✅ Add percent_paid for progress bar
        for loan in loans:
            if loan.total_payable > 0:
                loan.percent_paid = (loan.total_paid / loan.total_payable) * 100
            else:
                loan.percent_paid = 0
        return loans

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # ✅ Keep your total_loans info
        context['total_loans'] = Loan.objects.count()
        context['user_roles'] = ['manager', 'officer', 'itadmin']  # Pass the roles as a list
        return context


class LoanPaymentSearchView(LoginRequiredMixin, TemplateView):
    template_name = 'transact2_loans/loan_payment_search.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        query = self.request.GET.get('q')
        accounts = MemberAccount.objects.none()

        if query:
            accounts = MemberAccount.objects.filter(
                Q(account_number__icontains=query) |
                Q(member__user__first_name__icontains=query) |
                Q(member__user__last_name__icontains=query)
            ).select_related('member', 'member__user')

        context['accounts'] = accounts
        context['query'] = query
        return context


class LoanTypeSummaryView(LoginRequiredMixin, TemplateView):
    template_name = "transact2_loans/loan_type_summary.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        account = self.request.user.account

        regular_loans = Loan.objects.filter(
            account=account,
            loan_type=Loan.LoanType.REGULAR
        )

        emergency_loans = Loan.objects.filter(
            account=account,
            loan_type=Loan.LoanType.EMERGENCY
        )

        def summarize(loans):
            total_amount = loans.aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00')

            total_paid = sum(
                loan.total_paid for loan in loans
            ) or Decimal('0.00')

            total_unpaid = total_amount - total_paid

            return {
                "total_amount": total_amount,
                "total_paid": total_paid,
                "total_unpaid": max(total_unpaid, Decimal('0.00')),
            }

        regular_summary = summarize(regular_loans)
        emergency_summary = summarize(emergency_loans)

        context.update({
            "regular_loans": regular_loans,
            "emergency_loans": emergency_loans,

            "regular": regular_summary,
            "emergency": emergency_summary,

            "overall": {
                "total_amount": regular_summary["total_amount"] + emergency_summary["total_amount"],
                "total_paid": regular_summary["total_paid"] + emergency_summary["total_paid"],
                "total_unpaid": regular_summary["total_unpaid"] + emergency_summary["total_unpaid"],
            }
        })

        return context


class LoanPaymentListView(LoginRequiredMixin, ListView):
    model = LoanPayment
    template_name = "transact2_loans/loan_payment_list.html"
    context_object_name = "payments"
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user

        queryset = LoanPayment.objects.select_related(
            "loan",
            "loan__account",
            "loan__account__member",
            "loan__account__member__user"
        ).order_by("-paid_on")

        # 🔐 Role-based filtering
        if not user.has_any_role("manager", "auditor", "officer", "itadmin"):
            queryset = queryset.filter(
                loan__account=user.account
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["total_payments"] = LoanPayment.objects.count()
        context["loan_counts"] = ( LoanPayment.objects .values("loan")
            .annotate(total=Count("id"))  )

        return context


##Key Features
########################################################################################
#1Gets member account from member_account URL or POST data.

#2Finds main loan automatically — most recent approved or active.

##3Checks and repays peer loans first before main loan.

##4Validates amounts — no overpayment.

##5Uses atomic transaction — all payments saved together.

##6Updates statuses for peer loans and main loan

from transact3_lending.forms import PeerLoanRepaymentForm



####see my mental rule: I have an account with 2000 balance. To reuest loan in our cooperative, you borrow money from peers in your coperative
# eVEN IF IT IS YOUR MONEY,(your request loan, and they cooperative give your money as loan), Because i need 5000.
# I borrow 1000 peter, 1500 mary, and 500 Bob.The total amount is 5000. In our business rule, You have to rquest mail loan less or equal than5000.
# Asumme you pay 1st 800, it will be to peter (Main loan becomes  4200).
# Second you pay 1800, then 200 goes to peter, and 1500 goes to mary, and 100 to Bob (main loan ibecomes 2400.
# 3rd time, you pay 1600, 400goes to bob and 1200  comes to your balance, thru legder and Main loan becomes 800).Finally if you pay 800.Main loanbecomes 0, balance added 800 .
##this can be applied later, automation
class LoanPaymentView(FormView):
    model = LoanPayment
    template_name = 'transact2_loans/loan_payment_form1.html'
    form_class = LoanPaymentForm  #PeerLoanRepaymentForm is called in context
    success_url = reverse_lazy('transact2_loans:transaction-success')

    # -------------------------
    # Helpers
    # -------------------------
    def get_member_account(self):
        member_id = self.kwargs.get('member_account') or self.request.POST.get('member_account')
        return get_object_or_404(MemberAccount, pk=member_id)

    def get_main_loan(self, member_account):
        return Loan.objects.filter(
            account=member_account,
            status__in=[Loan.LoanStatus.APPROVED, Loan.LoanStatus.ACTIVE]
        ).order_by('-issued_on').first()

    def get_peer_loans(self, member_account):
        return (
            PeerToPeerLoan.objects
            .select_for_update()   # 🔐 Prevent race conditions
            .filter(
                borrower=member_account,
                is_fully_paid=False
            )
            .select_related("lender")
        )

    # -------------------------
    # Context (GET)
    # -------------------------
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        member_account = self.get_member_account()
        main_loan = self.get_main_loan(member_account)
        peer_loans = self.get_peer_loans(member_account)

        peer_forms = [ ( loan,
                PeerLoanRepaymentForm(
                    peer_loan=loan,
                    user=self.request.user,
                    prefix=f"peer_{loan.id}"  ) )
            for loan in peer_loans   ]

        context.update({
            'member_account': member_account,
            'main_loan': main_loan,
            'peer_forms': peer_forms,
        })

        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['member_account'] = self.get_member_account()
        return kwargs

    # -------------------------
    # POST
    # -------------------------
    def post(self, request, *args, **kwargs):
        member_account = self.get_member_account()
        main_loan = self.get_main_loan(member_account)

        if not main_loan:
            messages.error(request, "No approved or active main loan found for this member.")
            return redirect(request.path)

        loan_form = self.get_form()
        loan_form.instance.loan = main_loan
        loan_form.instance.received_by = request.user

        peer_loans = self.get_peer_loans(member_account)

        peer_forms = [
            PeerLoanRepaymentForm(
                request.POST,
                peer_loan=loan,
                user=request.user,
                prefix=f"peer_{loan.id}"
            )
            for loan in peer_loans]

        # Validate everything first
        #forms_valid = loan_form.is_valid() and all(f.is_valid() for f in peer_forms)  #we have many interface, if any of them is empty return None
        loan_valid = loan_form.is_valid()

        peer_valid = True
        for form in peer_forms:
            if form.data.get(form.add_prefix('amount')):
                if not form.is_valid():
                    peer_valid = False

        forms_valid = loan_valid and peer_valid
        if not forms_valid:
            context = self.get_context_data(form=loan_form)
            context['peer_forms'] = list(zip(peer_loans, peer_forms))
            return self.render_to_response(context)

        # -------------------------
        # Validate peer repayment total
        # -------------------------
              # Validate peer repayment total
        # -------------------------
        peer_total = sum(
            Decimal(form.cleaned_data['amount'])
            for form in peer_forms
            if hasattr(form, "cleaned_data") and form.cleaned_data.get('amount')        )
        loan_amount = loan_form.cleaned_data['amount']

        if peer_total > loan_amount:
            loan_form.add_error(
                'amount',
                "Total peer repayments cannot exceed the loan payment amount." )

            context = self.get_context_data(form=loan_form)
            context['peer_forms'] = list(zip(peer_loans, peer_forms))
            return self.render_to_response(context)
        # Atomic Transaction
        # -------------------------
        with transaction.atomic():

            # 1️⃣ Activate loan if needed
            if main_loan.status == Loan.LoanStatus.APPROVED:
                main_loan.status = Loan.LoanStatus.ACTIVE
                main_loan.save(update_fields=['status'])

            # 2️⃣ Save main loan payment (money enters borrower account)
            loan_payment = loan_form.save()

            if loan_payment.delay_time > 0:
                loan_payment.apply_penalty()

            # 3️⃣ Now repay peer loans
            for form in peer_forms:
                if not hasattr(form, "cleaned_data"):
                    continue

                amount = form.cleaned_data.get('amount')

                if amount:
                    repayment = form.save(commit=False)
                    repayment.date = timezone.now().date()
                    repayment.save()

            # 4️⃣ Update loan status
            main_loan.refresh_from_db()

            if main_loan.balance <= 0:
                main_loan.status = Loan.LoanStatus.PAID
                main_loan.save(update_fields=['status'])

        messages.success(request, "Payments successfully recorded (Peer loans first).")
        return redirect(self.success_url)



# =====================================================
# CUSTOMER + STAFF TRACKING VIEW
# =====================================================

class LoanWorkflowDetailView(LoginRequiredMixin, TemplateView):

    template_name = "transact2_loans/workflow_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        loan = get_object_or_404(Loan.objects.select_related("account"),  pk=self.kwargs["loan_id"]  )
        workflow = (  LoanWorkflow.objects.filter(loan=loan).order_by("-moved_at").first())
        history = workflow.history.all() if workflow else []
        context.update({
            "loan": loan,
            "workflow": workflow,
            "history": history,
        })
        return context


# =====================================================
# MOVE WORKFLOW STAGE
# =====================================================




# =====================================================
# STAFF DASHBOARD
# =====================================================

class LoanWorkflowDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "transact2_loans/workflow_dashboard.html"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["submitted_count"] = LoanWorkflow.objects.filter(
            stage=LoanWorkflow.Stage.SUBMITTED).count()
        context["officer_review_count"] = LoanWorkflow.objects.filter(
            stage=LoanWorkflow.Stage.OFFICER_REVIEW
        ).count()
        context["manager_review_count"] = LoanWorkflow.objects.filter(
            stage=LoanWorkflow.Stage.MANAGER_REVIEW
        ).count()
        context["disbursed_count"] = LoanWorkflow.objects.filter(
            stage=LoanWorkflow.Stage.DISBURSED
        ).count()
        context["closed_count"] = LoanWorkflow.objects.filter(
            stage=LoanWorkflow.Stage.CLOSED
        ).count()
        context["pending_workflows"] = LoanWorkflow.objects.select_related("loan",     "handler"  ).order_by("-moved_at")
        return context




class MoveLoanStageView(LoginRequiredMixin, FormView):
    template_name = "transact2_loans/move_stage.html"
    form_class = MoveStageForm

    def dispatch(self, request, *args, **kwargs):
        self.workflow = get_object_or_404(
            LoanWorkflow,
            pk=kwargs["workflow_id"]
        )

        allowed_roles = ["OFFICER", "MANAGER", "itadmin"]

        if not has_active_role(request, *allowed_roles):
            raise PermissionDenied(
                "You are not allowed to process this loan"
            )

        return super().dispatch(request, *args, **kwargs)