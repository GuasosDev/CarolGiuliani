from django.contrib import admin
from .models import Article, StockMovement

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('code', 'description', 'price', 'stock', 'is_active')
    search_fields = ('code', 'description', 'barcode')
    list_filter = ('is_active',)

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('article', 'movement_type', 'quantity', 'created_at')
    list_filter = ('movement_type', 'created_at')
    search_fields = ('article__code', 'article__description')

