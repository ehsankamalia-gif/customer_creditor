from django.contrib import admin

from .models import Motorcycle, ProductModel, StockLocation, Supplier


@admin.register(ProductModel)
class ProductModelAdmin(admin.ModelAdmin):
    list_display = ('model_name', 'make', 'engine_capacity', 'pct_code', 'item_code')
    search_fields = ('model_name', 'make', 'item_code')


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'phone')
    search_fields = ('name', 'contact_person', 'phone')


@admin.register(StockLocation)
class StockLocationAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(Motorcycle)
class MotorcycleAdmin(admin.ModelAdmin):
    list_display = (
        'chassis_number', 'product_model', 'color', 'year', 'status',
        'selling_price', 'location', 'purchase_date', 'is_active',
    )
    list_filter = ('status', 'product_model', 'location', 'is_active')
    search_fields = ('chassis_number', 'engine_number', 'vin')
    autocomplete_fields = ('product_model', 'purchase_supplier', 'location')
