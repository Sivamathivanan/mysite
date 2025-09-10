import django_filters
from .models import ScrapeSession
from .models import Product

class SessionFilter(django_filters.FilterSet):
    keyword = django_filters.CharFilter(field_name='keyword', lookup_expr='icontains', label='Keyword')
    pincode = django_filters.CharFilter(field_name='pincode', lookup_expr='icontains', label='Pincode')
    timestamp = django_filters.DateFromToRangeFilter(field_name='timestamp', label='Date Range')

    class Meta:
        model = ScrapeSession
        fields = ['keyword', 'pincode', 'timestamp', 'availability_rate']


class ProductFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(field_name='name', lookup_expr='icontains', label='Product Name')
    stock_status = django_filters.ChoiceFilter(
        field_name='out_of_stock_variants',
        lookup_expr='exact',
        choices=[('', 'All'), ('', 'In Stock'), ('__len__gt', 'Has Issues')],
        label='Stock Status'
    )

    class Meta:
        model = Product
        fields = ['name']
