from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm


from django.http import JsonResponse
from .analytics import StockAnalytics
import json

from django.shortcuts import render
from django.db.models import Q, Sum
from .models import ScrapeSession, StockAlert

from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Avg
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.utils import timezone

import pandas as pd
from io import BytesIO
import openpyxl.styles

from .models import ScrapeSession, Product, Alert, StockAlert
from .filters import SessionFilter, ProductFilter
from .utils import send_stock_alert_email
from .alert_engine import process_session_alerts
from scraper.blinkit_scraper import scrape_blinkit


def run_scrape(request):
    if request.method == 'POST':
        keyword = request.POST['keyword']
        pincode = request.POST['pincode']

        # Run scraper
        try:
            results = scrape_blinkit(keyword, pincode) or []
        except Exception as e:
            print(f"❌ Scraper error: {e}")
            results = [{
                'product_name': f'Error scraping {keyword}',
                'available_variants': [],
                'out_of_stock_variants': ['Error'],
                'url': 'https://blinkit.com'
            }]

        # Session summary
        total_products = len(results)
        out_of_stock_count = sum(bool(r['out_of_stock_variants']) for r in results)
        availability_rate = round((total_products - out_of_stock_count) / total_products * 100, 2) if total_products else 0

        session = ScrapeSession.objects.create(
            keyword=keyword,
            pincode=pincode,
            total_products=total_products,
            out_of_stock_count=out_of_stock_count,
            availability_rate=availability_rate
        )

        # Save products
        for r in results:
            Product.objects.create(
                session=session,
                name=r['product_name'],
                available_variants="; ".join(r['available_variants']),
                out_of_stock_variants="; ".join(r['out_of_stock_variants']),
                url=r['url']
            )

        # Smart alerts
        try:
            process_session_alerts(session)
        except Exception as e:
            print(f"⚠️ Alert processing failed: {e}")

        return redirect('dashboard', session_id=session.id)

    return render(request, 'scraper_app/rs_index.html')


def dashboard(request, session_id):
    session = get_object_or_404(ScrapeSession, id=session_id)
    products = session.products.all()
    alerts = session.alerts.all()
    return render(request, 'scraper_app/d_index.html', {
        'session': session,
        'products': products,
        'alerts': alerts,
    })


def historical_data(request):
    sessions = ScrapeSession.objects.all().order_by('-timestamp')[:10]
    return render(request, 'scraper_app/h_index.html', {'sessions': sessions})


def chart_data(request):
    sessions = ScrapeSession.objects.all().order_by('-timestamp')[:10]
    data = {
        'labels': [s.timestamp.strftime('%m/%d %H:%M') for s in sessions],
        'availability_rates': [float(s.availability_rate) for s in sessions],
        'total_products': [s.total_products for s in sessions],
        'out_of_stock_counts': [s.out_of_stock_count for s in sessions],
    }
    return JsonResponse(data)


def compare_sessions(request):
    sessions = ScrapeSession.objects.all().order_by('-timestamp')[:5]
    avg_availability = sessions.aggregate(Avg('availability_rate'))['availability_rate__avg'] or 0
    avg_products = sessions.aggregate(Avg('total_products'))['total_products__avg'] or 0
    return render(request, 'scraper_app/c_index.html', {
        'sessions': sessions,
        'avg_availability': round(avg_availability, 2),
        'avg_products': round(avg_products, 2),
    })


def export_session_excel(request, session_id):
    session = get_object_or_404(ScrapeSession, id=session_id)
    products = session.products.all()
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Session summary sheet
        summary_df = pd.DataFrame({
            'Metric': ['Session ID', 'Keyword', 'Pincode', 'Date & Time', 'Total Products', 'Out of Stock', 'Availability Rate'],
            'Value': [
                session.id, session.keyword, session.pincode,
                session.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                session.total_products, session.out_of_stock_count, f"{session.availability_rate}%"
            ]
        })
        summary_df.to_excel(writer, sheet_name='Session_Summary', index=False)

        # Products sheet
        products_df = pd.DataFrame([{
            'Product Name': p.name,
            'Available Variants': p.available_variants,
            'Out of Stock Variants': p.out_of_stock_variants,
            'Stock Status': 'In Stock' if not p.out_of_stock_variants else 'Has Stock Issues',
            'URL': p.url
        } for p in products])
        products_df.to_excel(writer, sheet_name='Products', index=False)

        # Style headers
        for sheet in ['Session_Summary', 'Products']:
            ws = writer.sheets[sheet]
            for cell in ws[1]:
                cell.font = openpyxl.styles.Font(bold=True)
                cell.fill = openpyxl.styles.PatternFill(start_color="366092", end_color="366092", fill_type="solid")

    output.seek(0)
    response = HttpResponse(output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="session_{session.id}.xlsx"'
    return response


def export_all_excel(request):
    sessions = ScrapeSession.objects.all().order_by('-timestamp')
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # All sessions
        sessions_df = pd.DataFrame([{
            'Session ID': s.id, 'Keyword': s.keyword, 'Pincode': s.pincode,
            'Date': s.timestamp.strftime('%Y-%m-%d'), 'Time': s.timestamp.strftime('%H:%M:%S'),
            'Total Products': s.total_products, 'Out of Stock': s.out_of_stock_count,
            'In Stock': s.total_products - s.out_of_stock_count, 'Availability Rate': s.availability_rate
        } for s in sessions])
        sessions_df.to_excel(writer, sheet_name='All_Sessions', index=False)

        # All products
        all_products = []
        for s in sessions:
            for p in s.products.all():
                all_products.append({
                    'Session ID': s.id,
                    'Session Date': s.timestamp.strftime('%Y-%m-%d'),
                    'Keyword': s.keyword,
                    'Pincode': s.pincode,
                    'Product Name': p.name,
                    'Available Variants': p.available_variants,
                    'Out of Stock Variants': p.out_of_stock_variants,
                    'Stock Status': 'In Stock' if not p.out_of_stock_variants else 'Has Issues',
                    'URL': p.url
                })
        pd.DataFrame(all_products).to_excel(writer, sheet_name='All_Products', index=False)

        # Alerts
        all_alerts = []
        for s in sessions:
            for a in s.alerts.all():
                all_alerts.append({
                    'Session ID': s.id,
                    'Date': s.timestamp.strftime('%Y-%m-%d'),
                    'Product Name': a.product_name,
                    'Alert Type': a.alert_type,
                    'Severity': a.severity,
                    'Days Out of Stock': a.days_out_of_stock
                })
        if all_alerts:
            pd.DataFrame(all_alerts).to_excel(writer, sheet_name='Alerts', index=False)

    output.seek(0)
    resp = HttpResponse(output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resp['Content-Disposition'] = f'attachment; filename="all_data.xlsx"'
    return resp


def export_session_csv(request, session_id):
    session = get_object_or_404(ScrapeSession, id=session_id)
    products = session.products.all()
    df = pd.DataFrame([{
        'Session_ID': session.id,
        'Keyword': session.keyword,
        'Pincode': session.pincode,
        'Date': session.timestamp.strftime('%Y-%m-%d'),
        'Product_Name': p.name,
        'Available_Variants': p.available_variants,
        'Out_of_Stock_Variants': p.out_of_stock_variants,
        'Stock_Status': 'In_Stock' if not p.out_of_stock_variants else 'Has_Issues',
        'URL': p.url
    } for p in products])
    resp = HttpResponse(content_type='text/csv')
    resp['Content-Disposition'] = f'attachment; filename="session_{session.id}.csv"'
    df.to_csv(resp, index=False)
    return resp


def sessions_list(request):
    qs = ScrapeSession.objects.all().order_by('-timestamp')
    session_filter = SessionFilter(request.GET, queryset=qs)
    paginator = Paginator(session_filter.qs, 10)
    page = request.GET.get('page')
    sessions = paginator.get_page(page)
    return render(request, 'scraper_app/sl_index.html', {
        'filter': session_filter,
        'sessions': sessions
    })


def products_list(request, session_id):
    session = get_object_or_404(ScrapeSession, id=session_id)
    qs = session.products.all()
    product_filter = ProductFilter(request.GET, queryset=qs)
    paginator = Paginator(product_filter.qs, 10)
    page = request.GET.get('page')
    products = paginator.get_page(page)
    return render(request, 'scraper_app/pl_index.html', {
        'session': session,
        'filter': product_filter,
        'products': products
    })


def alerts_dashboard(request):
    active_alerts = StockAlert.objects.filter(is_resolved=False).order_by('-created_at')
    resolved_alerts = StockAlert.objects.filter(is_resolved=True).order_by('-resolved_at')[:20]
    alert_stats = {
        'total_active': active_alerts.count(),
        'critical': active_alerts.filter(severity='CRITICAL').count(),
        'high': active_alerts.filter(severity='HIGH').count(),
        'medium': active_alerts.filter(severity='MEDIUM').count(),
        'daily_outages': active_alerts.filter(alert_type='DAILY_OUTAGE').count(),
        'consecutive_days': active_alerts.filter(alert_type='CONSECUTIVE_DAYS').count(),
    }
    return render(request, 'scraper_app/ad_index.html', {
        'active_alerts': active_alerts,
        'resolved_alerts': resolved_alerts,
        'alert_stats': alert_stats,
    })


def resolve_alert(request, alert_id):
    alert = get_object_or_404(StockAlert, id=alert_id)
    alert.is_resolved = True
    alert.resolved_at = timezone.now()
    alert.save()
    return redirect('ad_index')


def dashboard(request, session_id):
    session = get_object_or_404(ScrapeSession, id=session_id)
    products = session.products.all()

    alerts = StockAlert.objects.filter(
        keyword=session.keyword,
        pincode=session.pincode,
        is_resolved=False
    ).filter(
        Q(
            # DAILY_OUTAGE with significant outage count (e.g., 3 or more)
            alert_type='DAILY_OUTAGE',
            outage_count_today__gte=3
        ) |
        Q(
            # CONSECUTIVE_DAYS with 3 or more days
            alert_type='CONSECUTIVE_DAYS',
            consecutive_days__gte=3
        )
    ).order_by('-created_at')

    return render(request, 'scraper_app/d_index.html', {
        'session': session,
        'products': products,
        'stock_alerts': alerts,
    })

def landing_dashboard(request):
    """Main landing dashboard showing overview"""
    # Get recent sessions
    recent_sessions = ScrapeSession.objects.all().order_by('-timestamp')[:5]
    
    # Get statistics
    total_sessions = ScrapeSession.objects.count()
    total_products_scanned = sum(s.total_products for s in ScrapeSession.objects.all())
    
    # Get active alerts
    active_alerts = StockAlert.objects.filter(is_resolved=False).count()
    
    # Latest session for quick stats
    latest_session = ScrapeSession.objects.first() if ScrapeSession.objects.exists() else None
    
    context = {
        'recent_sessions': recent_sessions,
        'total_sessions': total_sessions,
        'total_products_scanned': total_products_scanned,
        'active_alerts': active_alerts,
        'latest_session': latest_session,
    }
    
    return render(request, 'scraper_app/ld_index.html', context)


def landing_dashboard(request):
    recent_sessions = ScrapeSession.objects.all().order_by('-timestamp')[:5]
    total_sessions = ScrapeSession.objects.count()
    total_products_scanned = ScrapeSession.objects.aggregate(total=Sum('total_products'))['total'] or 0
    active_alerts = StockAlert.objects.filter(is_resolved=False).count()
    latest_session = ScrapeSession.objects.order_by('-timestamp').first()
    significant_alerts = StockAlert.objects.filter(
        is_resolved=False
    ).filter(
        Q(alert_type='DAILY_OUTAGE', outage_count_today__gte=3) |
        Q(alert_type='CONSECUTIVE_DAYS', consecutive_days__gte=3)
    ).order_by('-created_at')[:3]
    context = {
        'recent_sessions': recent_sessions,
        'total_sessions': total_sessions,
        'total_products_scanned': total_products_scanned,
        'active_alerts': active_alerts,
        'latest_session': latest_session,
        'significant_alerts': significant_alerts,
    }
    return render(request, 'scraper_app/ld_index.html', context)


def analytics_dashboard(request):
    """Advanced analytics dashboard"""
    analytics = StockAnalytics()
    
    # Get advanced metrics
    metrics = analytics.get_advanced_metrics()
    
    context = {
        'metrics': metrics,
        'page_title': 'Advanced Analytics'
    }
    return render(request, 'scraper_app/ad_index.html', context)

def forecast_api(request):
    """API endpoint for stock forecasting"""
    keyword = request.GET.get('keyword')
    pincode = request.GET.get('pincode')
    days = int(request.GET.get('days', 7))
    
    analytics = StockAnalytics()
    forecast = analytics.generate_stock_forecast(keyword, pincode, days)
    
    return JsonResponse(forecast)

def correlation_analysis_api(request):
    """API endpoint for correlation analysis"""
    analytics = StockAnalytics()
    analysis = analytics.generate_correlation_heatmap()
    
    return JsonResponse(analysis)

def pincode_clustering_api(request):
    """API endpoint for pincode clustering"""
    analytics = StockAnalytics()
    clusters = analytics.analyze_pincode_patterns()
    
    return JsonResponse(clusters)

def signup(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'registration/s_index.html', {'form': form})

# @login_required
# def dashboard(request):
#     # view code...

# def upcoming_out_of_stock(request):
#     pincode = request.GET.get('pincode')
#     days_ahead = int(request.GET.get('days', 7))
#     analytics = StockAnalytics()
#     products_at_risk = analytics.forecast_out_of_stock_products(pincode=pincode, days_ahead=days_ahead)
#     return render(request, 'scraper_app/upcoming_out_of_stock.html', {'products_at_risk': products_at_risk})


def analytics_dashboard(request):
    analytics = StockAnalytics()
    pincode = request.GET.get('pincode')
    days_ahead = int(request.GET.get('days', 7))
    
    # Get all analytics data including product forecasts
    data = analytics.get_analytics_with_products(
        pincode=pincode, 
        days_ahead=days_ahead
    )
    
    return render(request, 'scraper_app/ad_index.html', data)



def product_forecasts_api(request):
    analytics = StockAnalytics()
    pincode = request.GET.get('pincode')
    days_ahead = int(request.GET.get('days', 7))
    keyword = request.GET.get('keyword')  # Optional for future use
    
    products_at_risk = analytics.forecast_out_of_stock_products(
        pincode=pincode, 
        days_ahead=days_ahead
    )
    
    # Convert dates to strings for JSON serialization
    for product in products_at_risk:
        product['date'] = product['date'].strftime('%Y-%m-%d')
    
    return JsonResponse(products_at_risk, safe=False)

