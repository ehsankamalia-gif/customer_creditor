from django.urls import path

from . import views

app_name = 'inventory'

urlpatterns = [
    path('inventory/', views.InventoryListView.as_view(), name='inventory_list'),
    path('inventory/dashboard/', views.InventoryDashboardView.as_view(), name='dashboard'),
    path('inventory/motorcycles/new/', views.AddMotorcycleView.as_view(), name='add_motorcycle'),
    path('inventory/import/', views.ImportStockView.as_view(), name='import_stock'),
    path('inventory/motorcycles/<int:pk>/', views.MotorcycleDetailView.as_view(), name='motorcycle_detail'),
    path('inventory/motorcycles/<int:pk>/edit/', views.EditMotorcycleView.as_view(), name='edit_motorcycle'),
    path('inventory/motorcycles/<int:pk>/status/', views.change_status, name='change_status'),
    path('inventory/motorcycles/<int:pk>/return-to-stock/', views.return_to_stock, name='return_to_stock'),
    path('inventory/motorcycles/<int:pk>/archive/', views.archive_motorcycle, name='archive_motorcycle'),
    path('inventory/motorcycles/<int:pk>/restore/', views.restore_motorcycle, name='restore_motorcycle'),
    path('inventory/models/new/', views.AddProductModelView.as_view(), name='add_product_model'),
    path('inventory/suppliers/new/', views.AddSupplierView.as_view(), name='add_supplier'),
    path('inventory/locations/new/', views.AddLocationView.as_view(), name='add_location'),
]
