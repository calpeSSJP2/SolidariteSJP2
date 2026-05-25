from datetime import datetime, time
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.dateparse import parse_date
from django.views.generic import CreateView, TemplateView
from accounts.models import MemberAccount, User
from .models import ShareIncrease, ShareDecrease
from .forms import IncreaseShareForm, DecreaseShareForm

class ShareTransactionSearchView(LoginRequiredMixin, TemplateView):
    template_name = "transact4_share_mngt/account_search.html"

    action_url_name = None
    button_text = None
    button_color = None
    title = None

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
            "action_url_name": self.action_url_name,
            "button_text": self.button_text,
            "button_color": self.button_color,
            "title": self.title,
        })
        return context

    def post(self, request, *args, **kwargs):
        q = request.POST.get("q", "")
        if q:
            return redirect(f"{request.path}?q={q}")
        return self.get(request, *args, **kwargs)
# -----------------------------
class TransactionCreateMixin(LoginRequiredMixin, CreateView):
    template_name = 'transact4_share_mngt/transaction_shares_form.html'
    title = ''
    button_label = 'Submit'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': self.title,
            'button_label': self.button_label,
        })
        return context

# -----------------------------
# Increase Shares View
# -----------------------------
#####Modify your existing views to accept account_id so that you search
class ShareIncreaseView(TransactionCreateMixin):
    model = ShareIncrease
    form_class = IncreaseShareForm
    success_url = reverse_lazy('transact4_share_mngt:share_transaction-success')
    title = "Increase Shares"
    button_label = "Add Shares"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        account_id = self.kwargs.get('account_id')
        if account_id:
            account = get_object_or_404(MemberAccount, pk=account_id)
            kwargs['initial'] = {'account': account}
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        account_id = self.kwargs.get("account_id")
        account = get_object_or_404(MemberAccount, pk=account_id)

        increases = account.share_increase_transactions.all()[:5]
        decreases = account.share_decrease_transactions.all()[:5]

        ops = []

        for tx in increases:
            ops.append({
                "date": tx.timestamp,
                "type": "Increase",
                "nbr_share": tx.nbr_share,
            })

        for tx in decreases:
            ops.append({
                "date": tx.timestamp,
                "type": "Decrease",
                "nbr_share": tx.nbr_share,
            })

        ops.sort(key=lambda x: x["date"], reverse=True)

        context["recent_ops"] = ops[:5]
        return context

# -----------------------------
# Decrease Shares View
# -----------------------------


# -----------------------------
# Share Transaction History
# -----------------------------
class ShareHistoryView(LoginRequiredMixin, TemplateView):
    template_name = 'transact4_share_mngt/share_history.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = getattr(self.request.user, 'membersprofile', None)
        account = getattr(profile, 'memberaccount', None)

        if account:
            context['increases'] = account.share_increase_transactions.all()
            context['decreases'] = account.share_decrease_transactions.all()
        else:
            context['increases'] = []
            context['decreases'] = []
            messages.warning(self.request, "❌ No MemberAccount found for this user.")

        context['title'] = "Share Transaction History"
        return context
class ShareDecreaseView(TransactionCreateMixin):
    model = ShareDecrease
    form_class = DecreaseShareForm
    success_url = reverse_lazy('transact4_share_mngt:share_transaction-success')
    title = "Decrease Shares"
    button_label = "Remove Shares"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        account_id = self.kwargs.get('account_id')
        if account_id:
            account = get_object_or_404(MemberAccount, pk=account_id)
            kwargs['initial'] = {'account': account}
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        account_id = self.kwargs.get("account_id")
        account = get_object_or_404(MemberAccount, pk=account_id)

        increases = account.share_increase_transactions.all()[:5]
        decreases = account.share_decrease_transactions.all()[:5]

        ops = []

        for tx in increases:
            ops.append({
                "date": tx.timestamp,
                "type": "Increase",
                "nbr_share": tx.nbr_share,
            })

        for tx in decreases:
            ops.append({
                "date": tx.timestamp,
                "type": "Decrease",
                "nbr_share": tx.nbr_share,
            })

        ops.sort(key=lambda x: x["date"], reverse=True)

        context["recent_ops"] = ops[:5]
        return context



##Repport

class ShareTransactionReportView(LoginRequiredMixin, TemplateView):
    template_name = "transact4_share_mngt/share_report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user
        active_role = self.request.session.get("active_role")

        account_id = self.request.GET.get("account")
        start_date = self.request.GET.get("start_date")
        end_date = self.request.GET.get("end_date")
        tx_type = self.request.GET.get("type")

        # Base querysets
        increases = ShareIncrease.objects.select_related("account")
        decreases = ShareDecrease.objects.select_related("account")

        # -----------------------
        # 🔐 ROLE-BASED FILTERING (SESSION-BASED)
        # -----------------------
        if active_role in ["officer", "manager", "itadmin"]:

            if account_id:
                increases = increases.filter(account_id=account_id)
                decreases = decreases.filter(account_id=account_id)

            context["accounts"] = MemberAccount.objects.all()

        elif active_role == "ordinary_member":

            user_account = getattr(user, "account", None)

            if not user_account:
                context["transactions"] = []
                context["accounts"] = []
                return context

            increases = increases.filter(account=user_account)
            decreases = decreases.filter(account=user_account)

            context["accounts"] = [user_account]

        else:
            # Unknown or unauthorized role
            context["transactions"] = []
            context["accounts"] = []
            return context

        # -----------------------
        # 📅 DATE FILTERING
        # -----------------------
        if start_date:
            start = datetime.combine(parse_date(start_date), time.min)
            increases = increases.filter(timestamp__gte=start)
            decreases = decreases.filter(timestamp__gte=start)

        if end_date:
            end = datetime.combine(parse_date(end_date), time.max)
            increases = increases.filter(timestamp__lte=end)
            decreases = decreases.filter(timestamp__lte=end)

        # -----------------------
        # 🔄 BUILD TRANSACTION LIST
        # -----------------------
        transactions = [
            {
                "date": tx.timestamp,
                "account": tx.account,
                "type": "Increase",
                "shares": tx.nbr_share,
                "current_shares": tx.account.shares,
            }
            for tx in increases
        ] + [
            {
                "date": tx.timestamp,
                "account": tx.account,
                "type": "Decrease",
                "shares": tx.nbr_share,
                "current_shares": tx.account.shares,
            }
            for tx in decreases
        ]

        # -----------------------
        # 🔎 TYPE FILTER
        # -----------------------
        if tx_type:
            transactions = [
                t for t in transactions
                if t["type"].lower() == tx_type.lower()
            ]

        # -----------------------
        # ⬇ SORT (NEWEST FIRST)
        # -----------------------
        transactions.sort(key=lambda x: x["date"], reverse=True)

        context["transactions"] = transactions

        return context