from django.contrib import admin
from django_celery_beat.models import IntervalSchedule, PeriodicTask, CrontabSchedule, SolarSchedule

# Register celery-beat models
admin.site.register(IntervalSchedule)
admin.site.register(PeriodicTask)
admin.site.register(CrontabSchedule)
admin.site.register(SolarSchedule)
