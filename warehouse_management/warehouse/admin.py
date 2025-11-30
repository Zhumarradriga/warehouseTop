from django.contrib import admin
from .models import Category, Product, Rack, Batch, Placement, WarehouseJournal
from django.utils.html import format_html
from django.db.models import Sum


class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description_short')
    search_fields = ('name',)
    prepopulated_fields = {'description': ('name',)}

    def description_short(self, obj):
        return obj.description[:50] + '...' if obj.description and len(obj.description) > 50 else obj.description
    description_short.short_description = 'Описание'


class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'sku', 'dimensions', 'weight')
    list_filter = ('category',)
    search_fields = ('name', 'sku', 'category__name')
    raw_id_fields = ('category',)

    def dimensions(self, obj):
        return f"{obj.length}×{obj.width}×{obj.height} см"
    dimensions.short_description = 'Габариты'


@admin.register(Rack)
class RackAdmin(admin.ModelAdmin):
    list_display = ('name', 'dimensions', 'max_load',
                    'is_active', 'utilization_percent')
    list_filter = ('is_active',)
    search_fields = ('name',)
    list_editable = ('is_active',)

    def dimensions(self, obj):
        return f"{obj.length}×{obj.width}×{obj.height} см"
    dimensions.short_description = 'Габариты'

    def utilization_percent(self, obj):
        percent = obj.get_utilization_percent()
        color = 'green' if percent < 70 else 'orange' if percent < 85 else 'red'
        return format_html(
            '<div style="background-color: {}; color: white; padding: 2px 8px; border-radius: 4px;">{}%</div>',
            color, percent
        )
    utilization_percent.short_description = 'Загрузка'


class PlacementInline(admin.TabularInline):
    model = Placement
    extra = 0
    readonly_fields = ('date_placed', 'is_active')
    fields = ('rack', 'quantity', 'is_active', 'date_placed')
    raw_id_fields = ('rack',)


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'product', 'quantity', 'arrival_date',
                    'supplier_short', 'placed_quantity', 'remaining_quantity')
    list_filter = ('arrival_date', 'product__category')
    search_fields = ('product__name', 'supplier', 'product__sku')
    raw_id_fields = ('product',)
    inlines = [PlacementInline]
    date_hierarchy = 'arrival_date'

    def supplier_short(self, obj):
        return obj.supplier[:30] + '...' if len(obj.supplier) > 30 else obj.supplier
    supplier_short.short_description = 'Поставщик'

    def placed_quantity(self, obj):
        placed = obj.placement_set.aggregate(
            total=Sum('quantity'))['total'] or 0
        return placed
    placed_quantity.short_description = 'Размещено'

    def remaining_quantity(self, obj):
        placed = obj.placement_set.aggregate(
            total=Sum('quantity'))['total'] or 0
        return max(0, obj.quantity - placed)
    remaining_quantity.short_description = 'Осталось'


@admin.register(Placement)
class PlacementAdmin(admin.ModelAdmin):
    list_display = ('product_name', 'rack_name', 'quantity',
                    'batch_info', 'date_placed', 'is_active')
    list_filter = ('is_active', 'rack', 'date_placed')
    search_fields = ('product__name', 'rack__name', 'batch__id')
    raw_id_fields = ('rack', 'product', 'batch')
    date_hierarchy = 'date_placed'
    list_editable = ('is_active',)

    def product_name(self, obj):
        return obj.product.name
    product_name.short_description = 'Товар'

    def rack_name(self, obj):
        return obj.rack.name
    rack_name.short_description = 'Стеллаж'

    def batch_info(self, obj):
        if obj.batch:
            return f"№{obj.batch.id} от {obj.batch.arrival_date.date()}"
        return "-"
    batch_info.short_description = 'Партия'


@admin.register(WarehouseJournal)
class WarehouseJournalAdmin(admin.ModelAdmin):
    list_display = ('operation_type_badge', 'product_name', 'quantity',
                    'rack_name', 'batch_info', 'operation_date', 'operator')
    list_filter = ('operation_type', 'operation_date',
                   'operator', 'product__category')
    search_fields = ('product__name', 'operator',
                     'notes', 'rack__name', 'batch__id')
    raw_id_fields = ('product', 'rack', 'batch')
    date_hierarchy = 'operation_date'
    readonly_fields = ('operation_date',)

    def operation_type_badge(self, obj):
        color = 'success' if obj.operation_type == 'IN' else 'danger'
        icon = 'arrow-down-circle' if obj.operation_type == 'IN' else 'arrow-up-circle'
        return format_html(
            '<span class="badge bg-{}"><i class="bi bi-{}"></i> {}</span>',
            color, icon, dict(WarehouseJournal.OPERATION_CHOICES)[
                obj.operation_type]
        )
    operation_type_badge.short_description = 'Тип операции'

    def product_name(self, obj):
        return obj.product.name
    product_name.short_description = 'Товар'

    def rack_name(self, obj):
        return obj.rack.name if obj.rack else "-"
    rack_name.short_description = 'Стеллаж'

    def batch_info(self, obj):
        if obj.batch:
            return f"№{obj.batch.id} от {obj.batch.arrival_date.date()}"
        return "-"
    batch_info.short_description = 'Партия'


# Регистрация Category с использованием декоратора
admin.site.register(Category, CategoryAdmin)
# Registration of Product with decorator
admin.site.register(Product, ProductAdmin)

# Настройка заголовков админ-панели
admin.site.site_header = "Система управления складом"
admin.site.site_title = "Админ-панель склада"
admin.site.index_title = "Управление складскими операциями"
