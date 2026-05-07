from django.db.models import Q


class FilterTransactionsMixin:
    def get_filtered_transactions(self):
        queryset = self.model.objects.all()
        request = self.request

        search = request.GET.get('search')
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(account__name__icontains=search) | Q(account__number__icontains=search)
            )

        start_date = request.GET.get('start_date')
        if start_date:
            queryset = queryset.filter(date__gte=start_date)

        end_date = request.GET.get('end_date')
        if end_date:
            queryset = queryset.filter(date__lte=end_date)

        return queryset
