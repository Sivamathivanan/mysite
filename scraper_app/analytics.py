import pandas as pd
import numpy as np
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Avg, Q
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression

# Monkey-patch numpy for Prophet compatibility under NumPy 2.x
if not hasattr(np, 'float_'):
    np.float_ = np.float64
    np.int_ = np.int64

try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False

from .models import ProductTracker, ScrapeSession, StockAlert


class StockAnalytics:

    def __init__(self):
        self.now = timezone.now()
        self.days_back = 30  # Analyze last 30 days

    def prepare_forecast_data(self, keyword=None, pincode=None):
        end_date = self.now.date()
        start_date = end_date - timedelta(days=self.days_back)

        query = ProductTracker.objects.filter(
            checked_at__date__range=[start_date, end_date]
        )
        if keyword:
            query = query.filter(keyword=keyword)
        if pincode:
            query = query.filter(pincode=pincode)

        daily_data = query.extra(
            select={'date': "DATE(checked_at)"}
        ).values('date').annotate(
            total_checks=Count('id'),
            outages=Count('id', filter=Q(is_available=False)),
            availability_rate=Avg('is_available')
        ).order_by('date')

        df = pd.DataFrame(daily_data)
        if df.empty:
            return df

        df['date'] = pd.to_datetime(df['date'])
        df['outage_rate'] = df['outages'] / df['total_checks']
        df['ds'] = df['date']
        df['y'] = df['outage_rate']

        return df[['ds', 'y', 'total_checks', 'outages', 'availability_rate']]

    def generate_stock_forecast(self, keyword=None, pincode=None, days_ahead=7):
        if not PROPHET_AVAILABLE:
            return {"error": "Prophet not available. Install with: pip install prophet"}

        df = self.prepare_forecast_data(keyword, pincode)
        if len(df) < 5:
            return {"error": "Insufficient data for forecasting (need at least 5 days)"}

        try:
            model = Prophet(
                daily_seasonality=True,
                weekly_seasonality=True,
                yearly_seasonality=False,
                changepoint_prior_scale=0.05,
                seasonality_prior_scale=10
            )
            model.fit(df[['ds', 'y']])
            future = model.make_future_dataframe(periods=days_ahead)
            forecast = model.predict(future)

            forecast_data = {
                'dates': forecast['ds'].dt.strftime('%Y-%m-%d').tolist(),
                'actual': df['y'].tolist() + [None] * days_ahead,
                'predicted': forecast['yhat'].tolist(),
                'lower_bound': forecast['yhat_lower'].tolist(),
                'upper_bound': forecast['yhat_upper'].tolist(),
                'trend': forecast['trend'].tolist(),
                'historical_dates': df['ds'].dt.strftime('%Y-%m-%d').tolist(),
                'historical_values': df['y'].tolist()
            }

            recent_forecast = forecast.tail(days_ahead)
            avg_prediction = recent_forecast['yhat'].mean()
            confidence = 1 - recent_forecast['yhat'].std()

            return {
                'forecast_data': forecast_data,
                'avg_outage_probability': round(avg_prediction * 100, 2),
                'confidence_score': round(confidence * 100, 2),
                'days_forecasted': days_ahead,
                'data_points_used': len(df)
            }
        except Exception as e:
            return {"error": f"Forecasting failed: {str(e)}"}

    def analyze_pincode_patterns(self):
        end_date = self.now.date()
        start_date = end_date - timedelta(days=self.days_back)

        pincode_data = ProductTracker.objects.filter(
            checked_at__date__range=[start_date, end_date]
        ).values('pincode').annotate(
            total_checks=Count('id'),
            outages=Count('id', filter=Q(is_available=False)),
            unique_products=Count('product_name', distinct=True),
            avg_availability=Avg('is_available')
        ).order_by('-total_checks')

        df = pd.DataFrame(pincode_data)
        if len(df) < 3:
            return {"error": "Insufficient pincode data for analysis"}

        df['outage_rate'] = df['outages'] / df['total_checks']
        df['checks_per_product'] = df['total_checks'] / df['unique_products']

        features = ['outage_rate', 'checks_per_product', 'unique_products']
        X = df[features].fillna(0)
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        n_clusters = min(4, len(df))
        kmeans = KMeans(n_clusters=n_clusters, random_state=42)
        df['cluster'] = kmeans.fit_predict(X_scaled)

        cluster_info = []
        for cid in range(n_clusters):
            cluster_data = df[df['cluster'] == cid]
            cluster_info.append({
                'cluster_id': cid,
                'pincodes': cluster_data['pincode'].tolist(),
                'avg_outage_rate': round(cluster_data['outage_rate'].mean() * 100, 2),
                'avg_products': round(cluster_data['unique_products'].mean(), 1),
                'description': self._describe_cluster(cluster_data)
            })

        return {
            'clusters': cluster_info,
            'pincode_data': df.to_dict('records'),
            'analysis_period': f"{start_date} to {end_date}"
        }

    def _describe_cluster(self, cluster_data):
        avg_outage = cluster_data['outage_rate'].mean()
        avg_products = cluster_data['unique_products'].mean()

        stability = "High-Risk" if avg_outage > 0.3 else "Medium-Risk" if avg_outage > 0.15 else "Stable"
        volume = "High-Volume" if avg_products > 50 else "Medium-Volume" if avg_products > 20 else "Low-Volume"

        return f"{stability}, {volume} Region"

    def generate_correlation_heatmap(self):
        end_date = self.now.date()
        start_date = end_date - timedelta(days=self.days_back)

        # Note double percent signs for strftime inside Django .extra()
        data = ProductTracker.objects.filter(
            checked_at__date__range=[start_date, end_date]
        ).extra(
            select={
                'hour': "CAST(strftime('%%H', checked_at) AS INTEGER)",
                'day_of_week': "CAST(strftime('%%w', checked_at) AS INTEGER)",
                'day_of_month': "CAST(strftime('%%d', checked_at) AS INTEGER)"
            }
        ).values('pincode', 'hour', 'day_of_week', 'day_of_month', 'is_available')

        df = pd.DataFrame(data)
        if df.empty:
            return {
                "error": "No data available for correlation analysis",
                'correlation_matrix': {
                    'labels': ['Pincode', 'Hour', 'Day of Week', 'Day of Month', 'Availability'],
                    'values': [[0] * 5 for _ in range(5)],
                    'text': [['0'] * 5 for _ in range(5)],
                },
                'time_patterns': {
                    'hourly_availability': {'hours': list(range(24)), 'availability': [0] * 24},
                    'daily_availability': {
                        'days': ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'],
                        'availability': [0] * 7,
                    },
                },
                'insights': []
            }

        df['pincode_numeric'] = pd.Categorical(df['pincode']).codes
        df['availability_numeric'] = df['is_available'].astype(int)

        features = ['pincode_numeric', 'hour', 'day_of_week', 'day_of_month', 'availability_numeric']
        corr_matrix = df[features].corr()

        heatmap_data = {
            'labels': ['Pincode', 'Hour', 'Day of Week', 'Day of Month', 'Availability'],
            'values': corr_matrix.values.tolist(),
            'text': [[f"{val:.3f}" for val in row] for row in corr_matrix.values]
        }

        hourly_avg = df.groupby('hour')['availability_numeric'].mean()
        daily_avg = df.groupby('day_of_week')['availability_numeric'].mean()

        time_patterns = {
            'hourly_availability': {
                'hours': list(range(24)),
                'availability': [hourly_avg.get(h, 0) * 100 for h in range(24)]
            },
            'daily_availability': {
                'days': ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'],
                'availability': [daily_avg.get(d, 0) * 100 for d in range(7)]
            }
        }

        return {
            'correlation_matrix': heatmap_data,
            'time_patterns': time_patterns,
            'insights': self._generate_correlation_insights(corr_matrix, hourly_avg, daily_avg)
        }

    def _generate_correlation_insights(self, corr_matrix, hourly_avg, daily_avg):
        insights = []

        if not hourly_avg.empty:
            peak_hours = hourly_avg.nlargest(3).index.tolist()
            low_hours = hourly_avg.nsmallest(3).index.tolist()
            insights.append(f"Best availability hours: {', '.join(map(str, peak_hours))}")
            insights.append(f"Lowest availability hours: {', '.join(map(str, low_hours))}")

        if not daily_avg.empty:
            weekdays = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
            peak_day = weekdays[daily_avg.idxmax()]
            low_day = weekdays[daily_avg.idxmin()]
            insights.append(f"Best availability day: {peak_day}")
            insights.append(f"Lowest availability day: {low_day}")

        return insights

    def get_advanced_metrics(self):
        end_date = self.now.date()
        start_date = end_date - timedelta(days=7)

        weekly_data = ProductTracker.objects.filter(
            checked_at__date__range=[start_date, end_date]
        ).extra(
            select={'date': "DATE(checked_at)"}
        ).values('date').annotate(
            availability_rate=Avg('is_available')
        ).order_by('date')

        df = pd.DataFrame(weekly_data)

        trend, icon = "Insufficient Data", "❓"
        slope = 0

        if len(df) >= 2:
            X = np.arange(len(df)).reshape(-1, 1)
            y = df['availability_rate'].values
            model = LinearRegression().fit(X, y)
            slope = model.coef_[0]

            if slope > 0.01:
                trend, icon = "Improving", "📈"
            elif slope < -0.01:
                trend, icon = "Declining", "📉"
            else:
                trend, icon = "Stable", "➡️"

        recent_alerts = StockAlert.objects.filter(
            created_at__date__gte=start_date,
            is_resolved=False
        ).count()

        if recent_alerts > 10:
            level, color = "HIGH", "danger"
        elif recent_alerts > 5:
            level, color = "MEDIUM", "warning"
        else:
            level, color = "LOW", "success"

        return {
            'trend': {'direction': trend, 'icon': icon, 'slope': round(slope * 100, 2)},
            'risk_assessment': {'level': level, 'color': color, 'active_alerts': recent_alerts},
            'data_quality': {
                'days_analyzed': len(df),
                'total_data_points': ProductTracker.objects.filter(
                    checked_at__date__range=[start_date, end_date]
                ).count()
            }
        }
        
    def forecast_out_of_stock_products(self, pincode=None, days_ahead=7, threshold=0.7):
        """
        Real-time OOS probability forecasting starting from today+1
        """
        if not PROPHET_AVAILABLE:
            return []
        
        today = timezone.now().date()
        end_date = today
        start_date = end_date - timedelta(days=self.days_back)
        
        products = ProductTracker.objects.filter(
            checked_at__date__range=[start_date, end_date]
        )
        if pincode:
            products = products.filter(pincode=pincode)
        
        product_names = list(products.values_list('product_name', flat=True).distinct())
        predictions = []

        for product in product_names:
            try:
                # Get historical data for this product
                qs = products.filter(product_name=product)
                daily_data = qs.extra(
                    select={'date': "DATE(checked_at)"}
                ).values('date').annotate(
                    total_checks=Count('id'),
                    outages=Count('id', filter=Q(is_available=False)),
                    availability_rate=Avg('is_available')
                ).order_by('date')
                
                df = pd.DataFrame(daily_data)
                if len(df) < 5:
                    continue
                    
                df['date'] = pd.to_datetime(df['date'])
                df['outage_rate'] = df['outages'] / df['total_checks']
                df['ds'] = df['date']
                df['y'] = df['outage_rate']

                # Train Prophet model
                model = Prophet(
                    daily_seasonality=False,
                    weekly_seasonality=True,
                    yearly_seasonality=False,
                    changepoint_prior_scale=0.05
                )
                model.fit(df[['ds', 'y']])
                
                # Forecast future dates (tomorrow onwards)
                future_dates = []
                for i in range(1, days_ahead + 1):
                    future_dates.append(today + timedelta(days=i))
                
                future_df = pd.DataFrame({'ds': pd.to_datetime(future_dates)})
                forecast = model.predict(future_df)
                
                # Find first high-risk date
                for idx, row in forecast.iterrows():
                    if row['yhat'] >= threshold:
                        probability = min(round(row['yhat'] * 100, 2), 100.0)
                        predictions.append({
                            'product_name': product,
                            'date': row['ds'].date(),
                            'predicted_outage_probability': probability,
                        })
                        break
                        
            except Exception as e:
                print(f"Error forecasting {product}: {e}")
                continue
        
        # Return unique products sorted by risk
        return sorted(predictions, key=lambda x: x['predicted_outage_probability'], reverse=True)


    def get_analytics_with_products(self, pincode=None, days_ahead=7, threshold=0.7):
        """
        Get both general analytics and product-specific out-of-stock predictions
        """
        # Get your existing analytics data
        analytics_data = {
            'correlation_heatmap': self.generate_correlation_heatmap(),
            'pincode_clustering': self.analyze_pincode_patterns(),
            'advanced_metrics': self.get_advanced_metrics(),
        }
        
        # Add product-specific forecasts
        products_at_risk = self.forecast_out_of_stock_products(
            pincode=pincode, 
            days_ahead=days_ahead, 
            threshold=threshold
        )
        
        analytics_data['products_at_risk'] = products_at_risk
        return analytics_data
