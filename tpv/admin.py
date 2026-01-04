from django.contrib import admin
from .models import Sale, SaleItem, CashRegister


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 1
    readonly_fields = ('subtotal',)
    fields = ('article', 'quantity', 'unit_price', 'discount', 'subtotal')
    autocomplete_fields = ('article',)


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('code', 'created_at', 'customer', 'total', 'status', 'payment_method')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('code', 'customer__name', 'customer__last_name')
    readonly_fields = ('code', 'subtotal', 'tax_amount', 'total', 'created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('code', 'status', 'customer', 'seller')
        }),
        ('Pago', {
            'fields': ('payment_method', 'subtotal', 'discount', 'tax_amount', 'total')
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at', 'notes'),
            'classes': ('collapse',)
        }),
    )
    inlines = [SaleItemInline]
    actions = ['mark_as_completed', 'mark_as_cancelled']

    def mark_as_completed(self, request, queryset):
        updated = 0
        for sale in queryset:
            try:
                sale.complete_sale()
                updated += 1
            except Exception as e:
                self.message_user(request, f"Error al completar venta {sale.code}: {str(e)}", level='error')
        self.message_user(request, f"{updated} ventas marcadas como completadas.")
    mark_as_completed.short_description = "Marcar como completadas"

    def mark_as_cancelled(self, request, queryset):
        updated = queryset.update(status='cancelled')
        self.message_user(request, f"{updated} ventas canceladas.")
    mark_as_cancelled.short_description = "Cancelar ventas seleccionadas"


@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ('sale', 'article', 'quantity', 'unit_price', 'subtotal')
    list_filter = ('sale__status',)
    search_fields = ('article__description', 'sale__code')
    readonly_fields = ('subtotal', 'created_at')
    autocomplete_fields = ('article',)


@admin.register(CashRegister)
class CashRegisterAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'opening_time', 'closing_time', 'opening_balance', 'closing_balance', 'status')
    list_filter = ('status', 'opening_time')
    search_fields = ('user__username', 'notes')
    readonly_fields = ('opening_time', 'closing_time', 'status')
    fieldsets = (
        (None, {
            'fields': ('user', 'status', 'opening_balance', 'closing_balance')
        }),
        ('Horarios', {
            'fields': ('opening_time', 'closing_time'),
            'classes': ('collapse',)
        }),
        ('Notas', {
            'fields': ('notes',)
        }),
    )
    actions = ['close_register']

    def close_register(self, request, queryset):
        for register in queryset.filter(status='open'):
            register.close_register(request.user)
        self.message_user(request, f"{queryset.count()} cajas cerradas correctamente.")
    close_register.short_description = "Cerrar cajas seleccionadas"
