from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta

# 1. ScrapeSession must come FIRST (before ProductTracker references it)
class ScrapeSession(models.Model):
    keyword = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    timestamp = models.DateTimeField(auto_now_add=True)
    total_products = models.IntegerField(default=0)
    out_of_stock_count = models.IntegerField(default=0)
    availability_rate = models.FloatField(default=0.0)

    def __str__(self):
        return f"{self.keyword} - {self.pincode} ({self.timestamp.strftime('%Y-%m-%d %H:%M')})"

# 2. Product model
class Product(models.Model):
    session = models.ForeignKey(ScrapeSession, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=500)
    available_variants = models.TextField(blank=True)
    out_of_stock_variants = models.TextField(blank=True)
    url = models.URLField(max_length=1000)

    def __str__(self):
        return self.name

# 3. Alert model  
class Alert(models.Model):
    session = models.ForeignKey(ScrapeSession, on_delete=models.CASCADE, related_name='alerts')
    product_name = models.CharField(max_length=500)
    days_out_of_stock = models.IntegerField(default=1)
    timestamp = models.DateTimeField(auto_now_add=True)
    alert_type = models.CharField(max_length=100)
    severity = models.CharField(max_length=20, default='MEDIUM')

    def __str__(self):
        return f"{self.product_name} - {self.severity}"

# 4. NEW: ProductTracker (now ScrapeSession is defined above)
class ProductTracker(models.Model):
    """Track individual product availability over time"""
    product_name = models.CharField(max_length=500)
    variant = models.CharField(max_length=200, blank=True)
    keyword = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    is_available = models.BooleanField()
    checked_at = models.DateTimeField(auto_now_add=True)
    session = models.ForeignKey(ScrapeSession, on_delete=models.CASCADE, related_name='product_tracks')
    
    class Meta:
        indexes = [
            models.Index(fields=['product_name', 'checked_at']),
            models.Index(fields=['keyword', 'pincode', 'checked_at']),
        ]

    def __str__(self):
        return f"{self.product_name} {self.variant} - {self.checked_at.date()}"

# 5. NEW: StockAlert
class StockAlert(models.Model):
    """Enhanced alerts with frequency tracking"""
    ALERT_TYPES = [
        ('DAILY_OUTAGE', 'Daily Outage Alert'),
        ('CONSECUTIVE_DAYS', 'Consecutive Days Alert'), 
        ('FREQUENT_OUTAGE', 'Frequent Outage Alert'),
        ('RESTOCKING_PATTERN', 'Restocking Pattern Alert'),
    ]
    
    SEVERITY_LEVELS = [
        ('LOW', 'Low Priority'),
        ('MEDIUM', 'Medium Priority'),
        ('HIGH', 'High Priority'),
        ('CRITICAL', 'Critical Priority'),
    ]
    weekly_outages = models.IntegerField(default=0)  # Add this line
    product_name = models.CharField(max_length=500)
    variant = models.CharField(max_length=200, blank=True)
    keyword = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS)
    
    # Tracking metrics
    outage_count_today = models.IntegerField(default=0)
    consecutive_days = models.IntegerField(default=0)
    total_checks_today = models.IntegerField(default=0)
    last_available_date = models.DateField(null=True, blank=True)
    
    message = models.TextField()
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['product_name', 'variant', 'keyword', 'pincode', 'alert_type']

    def __str__(self):
        return f"{self.product_name} {self.variant} - {self.alert_type}"

# 6. NEW: DailyStockSummary
class DailyStockSummary(models.Model):
    """Daily aggregated stock data"""
    date = models.DateField(unique=True)
    total_products_checked = models.IntegerField(default=0)
    total_out_of_stock = models.IntegerField(default=0)
    availability_rate = models.FloatField(default=0.0)
    most_problematic_products = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Summary for {self.date}"



