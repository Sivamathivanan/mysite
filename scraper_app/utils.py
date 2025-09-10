from django.core.mail import send_mail
from django.conf import settings

def send_consolidated_stock_alert_email(session, alerts):
    """Send a single email with all out-of-stock products"""
    if not alerts:
        return

    subject = f"🚨 Blinkit Stock Alert - {len(alerts)} Products Out of Stock"
    
    message = f"Stock Alert Report\n"
    message += f"==================\n\n"
    message += f"Keyword: {session.keyword}\n"
    message += f"Pincode: {session.pincode}\n"
    message += f"Scan Time: {session.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
    message += f"Session ID: {session.id}\n\n"
    
    message += f"OUT OF STOCK PRODUCTS ({len(alerts)}):\n"
    message += f"{'='*50}\n\n"
    
    # Group alerts by type
    daily_alerts = [a for a in alerts if a.alert_type == 'DAILY_OUTAGE']
    consecutive_alerts = [a for a in alerts if a.alert_type == 'CONSECUTIVE_DAYS']
    frequent_alerts = [a for a in alerts if a.alert_type == 'FREQUENT_OUTAGE']
    
    if daily_alerts:
        message += "📅 TODAY'S OUT-OF-STOCK:\n"
        for alert in daily_alerts:
            message += f"   • {alert.product_name} {alert.variant} - {alert.outage_count_today} times\n"
        message += "\n"
    
    if consecutive_alerts:
        message += "⏰ CONSECUTIVE DAYS OUT-OF-STOCK:\n"
        for alert in consecutive_alerts:
            message += f"   • {alert.product_name} {alert.variant} - {alert.consecutive_days} days\n"
        message += "\n"
    
    if frequent_alerts:
        message += "🔄 FREQUENT OUTAGES (This Week):\n"
        for alert in frequent_alerts:
            weekly_count = getattr(alert, 'weekly_outages', 0)
            message += f"   • {alert.product_name} {alert.variant} - {weekly_count} outages\n"
        message += "\n"
    
    message += f"View full details: http://localhost:8000/dashboard/{session.id}/\n"
    message += f"View all alerts: http://localhost:8000/alerts/\n"
    
    recipient_list = ['sivamathivananp@gmail.com']  # Replace with your email
    
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipient_list)
    print(f"✅ Consolidated alert email sent with {len(alerts)} out-of-stock products")

# Keep the old function for compatibility if needed
def send_stock_alert_email(session, alert):
    """Legacy function - now unused"""
    pass

