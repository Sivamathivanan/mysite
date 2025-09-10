from django.utils import timezone
from datetime import datetime, timedelta
from .models import ProductTracker, StockAlert, DailyStockSummary
from .utils import send_consolidated_stock_alert_email
from django.db.models import Count

class SmartAlertEngine:

    def __init__(self):
        self.today = timezone.now().date()
        self.now = timezone.now()

    def process_session_alerts(self, session):
        self._track_products(session)
        
        # Get all out-of-stock products from this session
        oos_alerts = []
        oos_alerts.extend(self._generate_daily_alerts(session))
        oos_alerts.extend(self._generate_consecutive_day_alerts(session))
        oos_alerts.extend(self._generate_frequent_outage_alerts(session))
        
        # Send single consolidated email if there are any alerts
        if oos_alerts:
            try:
                send_consolidated_stock_alert_email(session, oos_alerts)
                print(f"✅ Consolidated alert email sent with {len(oos_alerts)} out-of-stock products")
            except Exception as e:
                print(f"❌ Failed to send consolidated email: {e}")
        
        self._update_daily_summary()

    def _track_products(self, session):
        """Only track products that have actual out-of-stock variants"""
        for product in session.products.all():
            available = product.available_variants.split(';') if product.available_variants else []
            out_of_stock = product.out_of_stock_variants.split(';') if product.out_of_stock_variants else []
            
            # Clean and filter variants
            available = [v.strip() for v in available if v.strip()]
            out_of_stock = [v.strip() for v in out_of_stock if v.strip() and v.strip() not in ['Error', 'No data', 'Scraper Error']]
            
            # Only track if there are genuine out-of-stock variants
            if out_of_stock:
                # Track available variants
                for variant in available:
                    ProductTracker.objects.create(
                        product_name=product.name,
                        variant=variant,
                        keyword=session.keyword,
                        pincode=session.pincode,
                        is_available=True,
                        session=session
                    )
                
                # Track out-of-stock variants
                for variant in out_of_stock:
                    ProductTracker.objects.create(
                        product_name=product.name,
                        variant=variant,
                        keyword=session.keyword,
                        pincode=session.pincode,
                        is_available=False,
                        session=session
                    )

    def _generate_daily_alerts(self, session):
        """Generate alerts only for genuinely out-of-stock products"""
        alerts = []
        start = datetime.combine(self.today, datetime.min.time())
        end = datetime.combine(self.today, datetime.max.time())
        
        # Get today's out-of-stock tracks only
        oos_tracks = ProductTracker.objects.filter(
            keyword=session.keyword,
            pincode=session.pincode,
            checked_at__range=(start, end),
            is_available=False
        )
        
        # Group by product+variant and count outages
        stats = {}
        for track in oos_tracks:
            key = (track.product_name, track.variant)
            if key not in stats:
                stats[key] = {'total': 0, 'outages': 0, 'product_name': track.product_name, 'variant': track.variant}
            stats[key]['total'] += 1
            stats[key]['outages'] += 1

        # Generate alerts for out-of-stock products
        for key, s in stats.items():
            if s['outages'] >= 1:  # Any out-of-stock occurrence
                alert = self._create_or_update_alert(
                    product_name=s['product_name'],
                    variant=s['variant'],
                    keyword=session.keyword,
                    pincode=session.pincode,
                    alert_type='DAILY_OUTAGE',
                    severity='MEDIUM',
                    outage_count=s['outages'],
                    total_checks=s['total']
                )
                if alert:
                    alerts.append(alert)
        
        return alerts

    def _generate_consecutive_day_alerts(self, session):
        """Generate alerts for products out of stock for consecutive days"""
        alerts = []
        week_ago = self.today - timedelta(days=7)
        
        tracks = ProductTracker.objects.filter(
            keyword=session.keyword,
            pincode=session.pincode,
            checked_at__date__range=(week_ago, self.today),
            is_available=False
        ).order_by('product_name', 'variant', 'checked_at')

        days = {}
        for t in tracks:
            key = (t.product_name, t.variant)
            day = t.checked_at.date()
            if key not in days:
                days[key] = {}
            if day not in days[key]:
                days[key][day] = []
            days[key][day].append(False)  # All these are out-of-stock

        for (name, variant), d in days.items():
            consecutive_days = len(d)  # Number of days with outages
            if consecutive_days >= 2:  # 2+ days of outages
                severity = 'CRITICAL' if consecutive_days >= 3 else 'HIGH'
                alert = self._create_or_update_alert(
                    product_name=name,
                    variant=variant,
                    keyword=session.keyword,
                    pincode=session.pincode,
                    alert_type='CONSECUTIVE_DAYS',
                    severity=severity,
                    consecutive_days=consecutive_days
                )
                if alert:
                    alerts.append(alert)
        
        return alerts

    def _generate_frequent_outage_alerts(self, session):
        """Generate alerts for products with frequent outages"""
        alerts = []
        week_ago = self.now - timedelta(days=7)
        
        items = ProductTracker.objects.filter(
            keyword=session.keyword,
            pincode=session.pincode,
            checked_at__gte=week_ago,
            is_available=False
        ).values('product_name', 'variant').annotate(
            cnt=Count('id')
        ).filter(cnt__gte=3)  # 3+ outages in a week

        for item in items:
            alert = self._create_or_update_alert(
                product_name=item['product_name'],
                variant=item['variant'],
                keyword=session.keyword,
                pincode=session.pincode,
                alert_type='FREQUENT_OUTAGE',
                severity='HIGH',
                weekly_outages=item['cnt']
            )
            if alert:
                alerts.append(alert)
        
        return alerts

    def _create_or_update_alert(self, product_name, variant, keyword, pincode, alert_type, severity, **kw):
        """Create or update alert - return alert object if created/updated"""
        alert, created = StockAlert.objects.get_or_create(
            product_name=product_name,
            variant=variant,
            keyword=keyword,
            pincode=pincode,
            alert_type=alert_type,
            defaults={'severity': severity, 'is_resolved': False}
        )
        
        updated = False

        if alert_type == 'DAILY_OUTAGE':
            new_count = kw.get('outage_count', 0)
            new_total = kw.get('total_checks', 0)
            if alert.outage_count_today != new_count or alert.total_checks_today != new_total:
                alert.outage_count_today = new_count
                alert.total_checks_today = new_total
                alert.message = f"⚠️ '{product_name} {variant}' out of stock {new_count} times today"
                updated = True

        elif alert_type == 'CONSECUTIVE_DAYS':
            new_days = kw.get('consecutive_days', 0)
            if alert.consecutive_days != new_days:
                alert.consecutive_days = new_days
                alert.severity = 'CRITICAL' if new_days >= 3 else 'HIGH'
                alert.message = f"🚨 '{product_name} {variant}' out of stock for {new_days} consecutive days"
                updated = True

        elif alert_type == 'FREQUENT_OUTAGE':
            new_weekly = kw.get('weekly_outages', 0)
            if not hasattr(alert, 'weekly_outages') or alert.weekly_outages != new_weekly:
                alert.weekly_outages = new_weekly
                alert.message = f"📊 '{product_name} {variant}' had {new_weekly} outages this week"
                updated = True

        if created or updated:
            alert.severity = severity
            alert.is_resolved = False
            alert.save()
            return alert
        
        return None

    def _update_daily_summary(self):
        tracks = ProductTracker.objects.filter(checked_at__date=self.today)
        if not tracks.exists():
            return

        total = tracks.count()
        outages = tracks.filter(is_available=False).count()
        rate = (total - outages) / total * 100 if total else 0

        top = tracks.filter(is_available=False).values('product_name', 'variant') \
            .annotate(cnt=Count('id')).order_by('-cnt')[:5]
        worst = [f"{i['product_name']} {i['variant']}: {i['cnt']} outages" for i in top]

        summary, created = DailyStockSummary.objects.get_or_create(
            date=self.today,
            defaults={
                'total_products_checked': total,
                'total_out_of_stock': outages,
                'availability_rate': round(rate, 2),
                'most_problematic_products': worst
            }
        )
        if not created:
            summary.total_products_checked = total
            summary.total_out_of_stock = outages
            summary.availability_rate = round(rate, 2)
            summary.most_problematic_products = worst
            summary.save()


def process_session_alerts(session):
    engine = SmartAlertEngine()
    engine.process_session_alerts(session)
