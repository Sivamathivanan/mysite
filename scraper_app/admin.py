# from django.contrib import admin
# from .models import ScrapeSession, Product, Alert
# from django_celery_beat.models import IntervalSchedule, PeriodicTask

# # Your existing model registrations
# @admin.register(ScrapeSession)
# class ScrapeSessionAdmin(admin.ModelAdmin):
#     list_display = ('keyword', 'pincode', 'timestamp', 'availability_rate')
#     list_filter = ('timestamp', 'keyword')

# @admin.register(Product)
# class ProductAdmin(admin.ModelAdmin):
#     list_display = ('name', 'session', 'url')
#     list_filter = ('session',)

# @admin.register(Alert)
# class AlertAdmin(admin.ModelAdmin):
#     list_display = ('product_name', 'days_out_of_stock', 'severity', 'timestamp')
#     list_filter = ('severity', 'alert_type')

# # Register django-celery-beat models
# admin.site.register(IntervalSchedule)
# admin.site.register(PeriodicTask)

from django.contrib import admin
from .models import ScrapeSession, Product, Alert

@admin.register(ScrapeSession)
class ScrapeSessionAdmin(admin.ModelAdmin):
    list_display = ('keyword', 'pincode', 'timestamp', 'availability_rate')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'session', 'url')

@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ('product_name', 'days_out_of_stock', 'severity', 'timestamp')
