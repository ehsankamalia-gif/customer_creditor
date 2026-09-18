from django.urls import path

from . import views

app_name = 'spares'

urlpatterns = [
    path('spares/transactions/', views.TransactionsView.as_view(), name='transactions'),
    path('spares/transactions/new/', views.AddTransactionView.as_view(), name='add_transaction'),
    path('spares/monthly-report/', views.MonthlyReportView.as_view(), name='monthly_report'),
    path('spares/monthly-summary/', views.MonthlySummaryView.as_view(), name='monthly_summary'),
    path('spares/monthly-summary/close/', views.CloseMonthView.as_view(), name='close_month'),
]
