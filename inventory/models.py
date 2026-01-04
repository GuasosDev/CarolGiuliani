from django.db import models
from django.utils import timezone

class Article(models.Model):
    code = models.CharField('Código', max_length=50, unique=True)
    barcode = models.CharField('Código de barras', max_length=100, unique=True, blank=True, null=True)
    description = models.CharField('Descripción', max_length=255)
    price = models.DecimalField('Precio', max_digits=12, decimal_places=2, default=0)
    cost = models.DecimalField('Costo', max_digits=12, decimal_places=2, default=0)
    stock = models.DecimalField('Stock', max_digits=12, decimal_places=3, default=0)
    min_stock = models.DecimalField('Stock mínimo', max_digits=12, decimal_places=3, default=0)
    created_at = models.DateTimeField('Fecha de creación', auto_now_add=True)
    updated_at = models.DateTimeField('Última actualización', auto_now=True)
    is_active = models.BooleanField('Activo', default=True)

    class Meta:
        verbose_name = 'Artículo'
        verbose_name_plural = 'Artículos'
        ordering = ['description']

    def __str__(self):
        return f"[{self.code}] {self.description}"

    def update_stock(self, quantity, movement_type, description=''):
        """Actualiza el stock y registra el movimiento"""
        if movement_type in ['IN', 'RETURN', 'PURCHASE']:
            self.stock += quantity
        elif movement_type in ['OUT', 'SALE']:
            self.stock -= quantity
        self.save()
        
        # Registrar el movimiento
        StockMovement.objects.create(
            article=self,
            quantity=quantity,
            movement_type=movement_type,
            description=description
        )
        return self.stock


class StockMovement(models.Model):
    MOVEMENT_TYPES = [
        ('IN', 'Entrada'),
        ('OUT', 'Salida'),
        ('ADJ', 'Ajuste'),
        ('SALE', 'Venta'),
        ('PURCHASE', 'Compra'),
        ('RETURN', 'Devolución'),
    ]

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='movements')
    quantity = models.DecimalField('Cantidad', max_digits=12, decimal_places=3)
    movement_type = models.CharField('Tipo de movimiento', max_length=10, choices=MOVEMENT_TYPES)
    reference = models.CharField('Referencia', max_length=100, blank=True, null=True)
    description = models.TextField('Descripción', blank=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField('Fecha', auto_now_add=True)
    updated_at = models.DateTimeField('Actualizado', auto_now=True)

    class Meta:
        verbose_name = 'Movimiento de stock'
        verbose_name_plural = 'Movimientos de stock'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['article']),
            models.Index(fields=['movement_type']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.get_movement_type_display()} - {self.article} ({self.quantity})"

    def save(self, *args, **kwargs):
        if not self.pk:  # Solo para nuevos registros
            if self.movement_type in ['OUT', 'SALE'] and self.article.stock < self.quantity:
                raise ValueError(f'Stock insuficiente para {self.article}. Stock actual: {self.article.stock}')
        super().save(*args, **kwargs)
