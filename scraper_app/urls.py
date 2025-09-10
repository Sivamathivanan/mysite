# from django.urls import path
# from . import views

# urlpatterns = [
#     path('run/', views.run_scrape, name='run_scrape'),
#     path('dashboard/<int:session_id>/', views.dashboard, name='dashboard'),
#     path('historical/', views.historical_data, name='historical_data'),
#     path('compare/', views.compare_sessions, name='compare_sessions'),
#     path('api/chart-data/', views.chart_data, name='chart_data'),
    
#     path('export/session/<int:session_id>/excel/', views.export_session_excel, name='export_session_excel'),
#     path('export/session/<int:session_id>/csv/', views.export_session_csv, name='export_session_csv'),
#     path('export/all/excel/', views.export_all_excel, name='export_all_excel'),
# ]

# # from django.urls import path
# # from scraper_app import views

# # urlpatterns = [
# #     path('run/', views.run_scrape, name='run_scrape'),
# #     path('dashboard/<int:session_id>/', views.dashboard, name='dashboard'),
# #     path('historical/', views.historical_data, name='historical_data'),
# #     path('compare/', views.compare_sessions, name='compare_sessions'),
# #     path('api/chart-data/', views.chart_data, name='chart_data'),
# #     path('sessions/', views.sessions_list, name='sessions_list'),
# #     path('sessions/<int:session_id>/products/', views.products_list, name='products_list'),
# #     # export URLs...
# #     path('export/session/<int:session_id>/excel/', views.export_session_excel, name='export_session_excel'),
# #     path('export/session/<int:session_id>/csv/', views.export_session_csv, name='export_session_csv'),
# #     path('export/all/excel/', views.export_all_excel, name='export_all_excel'),
# # ]

# from django.urls import path
# from . import views    # Import the views module here

# urlpatterns = [
#     path('run/', views.run_scrape, name='run_scrape'),
#     path('dashboard/<int:session_id>/', views.dashboard, name='dashboard'),
#     path('historical/', views.historical_data, name='historical_data'),
#     path('compare/', views.compare_sessions, name='compare_sessions'),
#     path('api/chart-data/', views.chart_data, name='chart_data'),
#     path('sessions/', views.sessions_list, name='sessions_list'),
#     path('sessions/<int:session_id>/products/', views.products_list, name='products_list'),
#     path('export/session/<int:session_id>/excel/', views.export_session_excel, name='export_session_excel'),
#     path('export/session/<int:session_id>/csv/', views.export_session_csv, name='export_session_csv'),
#     path('export/all/excel/', views.export_all_excel, name='export_all_excel'),
#     path('alerts/', views.alerts_dashboard, name='alerts_dashboard'),
#     path('alerts/resolve/<int:alert_id>/', views.resolve_alert, name='resolve_alert'),
# ]

# from django.urls import path
# from . import views

from django.urls import path, include
from django.contrib import admin
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),
    path('api/forecast/', views.forecast_api, name='forecast_api'),
    path('api/correlation/', views.correlation_analysis_api, name='correlation_api'),
    path('api/clustering/', views.pincode_clustering_api, name='clustering_api'),

    path('', views.landing_dashboard, name='home'),  # Landing page
    path('run/', views.run_scrape, name='run_scrape'),
    path('dashboard/<int:session_id>/', views.dashboard, name='dashboard'),
    path('historical/', views.historical_data, name='historical_data'),
    path('sessions/', views.sessions_list, name='sessions_list'),
    path('compare/', views.compare_sessions, name='compare_sessions'),
    path('alerts/', views.alerts_dashboard, name='alerts_dashboard'),
    
    path('api/chart-data/', views.chart_data, name='chart_data'),
    path('sessions/<int:session_id>/products/', views.products_list, name='products_list'),
    path('export/session/<int:session_id>/excel/', views.export_session_excel, name='export_session_excel'),
    path('export/session/<int:session_id>/csv/', views.export_session_csv, name='export_session_csv'),
    path('export/all/excel/', views.export_all_excel, name='export_all_excel'),
    path('alerts/resolve/<int:alert_id>/', views.resolve_alert, name='resolve_alert'),
    path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),
    path('api/product-forecasts/', views.product_forecasts_api, name='product_forecasts_api'),
    # path('upcoming-out-of-stock/', views.upcoming_out_of_stock, name='upcoming_out_of_stock'),

    # path('admin/', admin.site.urls),

    # # User authentication
    # path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    # path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    # # Optional: custom signup
    # path('signup/', views.signup, name='signup'),
]
