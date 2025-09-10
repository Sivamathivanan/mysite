from celery import shared_task
from .models import ScrapeSession, Product, Alert
from scraper.blinkit_scraper import scrape_blinkit
from .utils import send_stock_alert_email

@shared_task
def scheduled_scrape(keyword, pincode):
    results = scrape_blinkit(keyword, pincode)

    total = len(results)
    out_of_stock = sum(1 for r in results if r['out_of_stock_variants'])
    availability = round((total - out_of_stock) / total * 100, 2) if total else 0

    session = ScrapeSession.objects.create(
        keyword=keyword,
        pincode=pincode,
        total_products=total,
        out_of_stock_count=out_of_stock,
        availability_rate=availability
    )

    for r in results:
        Product.objects.create(
            session=session,
            name=r['product_name'],
            available_variants="; ".join(r['available_variants']),
            out_of_stock_variants="; ".join(r['out_of_stock_variants']),
            url=r['url']
        )

    if out_of_stock:
        alert = Alert.objects.create(
            session=session,
            product_name=results[0]['product_name'],
            days_out_of_stock=1,
            alert_type='Scheduled Stock Alert',
            severity='MEDIUM'
        )
        send_stock_alert_email(session, alert)
