from django.urls import path

from . import views

app_name = 'credit'

urlpatterns = [
    # Customer-facing
    path('credit/', views.DashboardView.as_view(), name='dashboard'),
    path('credit/sales/<int:pk>/', views.SaleDetailView.as_view(), name='sale_detail'),
    path('credit/payments/', views.PaymentsView.as_view(), name='payments'),
    path('credit/ledger/', views.RunningLedgerView.as_view(), name='running_ledger'),

    # Staff-facing
    path('credit/staff/sales/', views.StaffSalesListView.as_view(), name='staff_sales'),
    path('credit/staff/sales/new/', views.StaffCreateSaleView.as_view(), name='staff_create_sale'),
    path('credit/staff/sales/<int:pk>/', views.StaffSaleDetailView.as_view(), name='staff_sale_detail'),
    path('credit/staff/sales/<int:pk>/payment/', views.StaffRecordPaymentView.as_view(), name='staff_record_payment'),
    path('credit/staff/customers/', views.StaffCustomerSummaryView.as_view(), name='staff_customer_summary'),
    path('credit/staff/customers/<int:pk>/', views.StaffCustomerDetailView.as_view(), name='staff_customer_detail'),
    path('credit/staff/transactions/', views.StaffTransactionsView.as_view(), name='staff_transactions'),
    path('credit/staff/export/sales.csv', views.staff_export_sales_csv, name='staff_export_sales_csv'),
    path('credit/staff/export/payments.csv', views.staff_export_payments_csv, name='staff_export_payments_csv'),
]
