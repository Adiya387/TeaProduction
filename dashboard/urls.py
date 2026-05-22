from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.custom_login, name='login'),
    path('logout/', views.custom_logout, name='logout'),
    
    # Dashboard API
    path('api/dashboard_data/', views.api_dashboard_data, name='api_dashboard_data'),
    path('api/inventory_lists/', views.api_inventory_lists, name='api_inventory_lists'),
    path('api/check_ingredients/<int:product_id>/', views.api_check_ingredients, name='api_check_ingredients'),
    
    # CRUD Pages
    path('raw-materials/', views.raw_materials_list, name='raw_materials_list'),
    path('products/', views.products_list, name='products_list'),
    path('units/', views.units_list, name='units_list'),
    path('employees/', views.employees_list, name='employees_list'),
    path('recipes/', views.recipes_list, name='recipes_list'),
    path('positions/', views.positions_list, name='positions_list'),
    
    # New Directories
    path('budget/', views.budget_list, name='budget_list'),
    path('salaries/', views.salaries_list, name='salaries_list'),
    path('credits/', views.credits_list, name='credits_list'),
    path('purchases/', views.purchases_list, name='purchases_list'),
    path('production/', views.production_list, name='production_list'),
    path('sales/', views.sales_list, name='sales_list'),
    
    # Reports Page
    path('reports/', views.reports_page, name='reports_page'),
    path('api/reports_data/', views.api_reports_data, name='api_reports_data'),
    path('api/get_purchases/', views.api_get_purchases, name='api_get_purchases'),
    path('api/get_sales/', views.api_get_sales, name='api_get_sales'),
    path('api/get_production/', views.api_get_production, name='api_get_production'),
    
    # Actions (Procedures)
    path('api/purchase/', views.api_purchase, name='api_purchase'),
    path('api/production/', views.api_production, name='api_production'),
    path('api/sale/', views.api_sale, name='api_sale'),
    path('api/credit/', views.api_credit, name='api_credit'),
    path('api/salary/', views.api_salary, name='api_salary'),
    path('api/employee_salary_info/<int:emp_id>/', views.api_employee_salary_info, name='api_employee_salary_info'),
    path('api/get_salaries/', views.api_get_salaries, name='api_get_salaries'),
    path('api/repay_credit/', views.api_repay_credit, name='api_repay_credit'),

    # Production Requests (Supervisor only)
    path('production-requests/', views.production_requests_page, name='production_requests_page'),
    path('erp-log/', views.erp_log_page, name='erp_log_page'),
    path('api/production_requests/', views.api_production_requests_list, name='api_production_requests_list'),
    path('api/production_request/create/', views.api_production_request_create, name='api_production_request_create'),
    path('api/production_request/<int:request_id>/status/', views.api_production_request_status, name='api_production_request_status'),
    path('api/production_request/preview/', views.api_production_request_preview, name='api_production_request_preview'),
    path('api/get_erp_log/', views.api_get_erp_log, name='api_get_erp_log'),
    path('analytics/', views.analytics_page, name='analytics_page'),
    path('api/analytics_data/', views.api_analytics_data, name='api_analytics_data'),
]
