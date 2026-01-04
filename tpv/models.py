from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Sum, F
from django.db import transaction
from inventory.models import Article, StockMovement

User = get_user_model()

class Sale(models.Model):
    """Modelo para las ventas del TPV"""
    STATUS_CHOICES = [
        ('draft', 'Borrador'),
        ('completed', 'Completada'),
        ('cancelled', 'Cancelada'),
    ]
    
    PAYMENT_METHODS = [
        ('cash', 'Efectivo'),
        ('card', 'Tarjeta'),
        ('transfer', 'Transferencia'),
        ('other', 'Otro'),
    ]
    
    code = models.CharField('Código', max_length=20, unique=True)
    customer = models.ForeignKey('clients.Client', on_delete=models.SET_NULL, 
                               null=True, blank=True, verbose_name='Cliente')
    seller = models.ForeignKey(User, on_delete=models.PROTECT, 
                             verbose_name='Vendedor')
    cash_register = models.ForeignKey('CashRegister', on_delete=models.PROTECT, 
                                    related_name='sales', verbose_name='Caja', null=True, blank=True)
    subtotal = models.DecimalField('Subtotal', max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField('Impuestos', max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField('Descuento', max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField('Total', max_digits=12, decimal_places=2, default=0)
    status = models.CharField('Estado', max_length=20, choices=STATUS_CHOICES, default='draft')
    payment_method = models.CharField('Método de pago', max_length=20, choices=PAYMENT_METHODS, default='cash')
    notes = models.TextField('Notas', blank=True)
    created_at = models.DateTimeField('Fecha de creación', auto_now_add=True)
    updated_at = models.DateTimeField('Última actualización', auto_now=True)
    
    class Meta:
        verbose_name = 'Venta'
        verbose_name_plural = 'Ventas'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Venta {self.code} - {self.get_status_display()}"
    
    def save(self, *args, **kwargs):
        if not self.code:
            # Generar código de venta (ej: V-20230101-001)
            today = timezone.now().strftime('%Y%m%d')
            last_sale = Sale.objects.filter(code__startswith=f'V-{today}').order_by('-code').first()
            if last_sale:
                last_num = int(last_sale.code.split('-')[-1])
                new_num = str(last_num + 1).zfill(3)
            else:
                new_num = '001'
            self.code = f"V-{today}-{new_num}"
        
        # Calcular totales
        # Calcular totales
        if self.pk:
            self.subtotal = sum(item.subtotal for item in self.items.all())
            self.total = self.subtotal + self.tax_amount - self.discount
        else:
            self.subtotal = 0
            self.total = 0
        
        super().save(*args, **kwargs)
    
    def complete_sale(self):
        """Marca la venta como completada y actualiza el stock"""
        if self.status != 'completed':
            # Verificar stock antes de completar
            for item in self.items.all():
                if item.article.stock < item.quantity:
                    raise ValueError(f'Stock insuficiente para {item.article}. Stock actual: {item.article.stock}, Cantidad solicitada: {item.quantity}')
            
            # Actualizar stock
            for item in self.items.all():
                item.article.update_stock(
                    quantity=item.quantity,
                    movement_type='SALE',
                    description=f'Venta {self.code}'
                )
            
            self.status = 'completed'
            self.save()

    def cancel_sale(self):
        """Cancela la venta y devuelve el stock"""
        if self.status == 'completed':
            with transaction.atomic():
                # Devolver stock
                for item in self.items.all():
                    item.article.update_stock(
                        quantity=item.quantity,
                        movement_type='RETURN',
                        description=f'Cancelación Venta {self.code}'
                    )
                
                self.status = 'cancelled'
                self.save()
        elif self.status == 'draft':
            self.status = 'cancelled'
            self.save()


class SaleItem(models.Model):
    """Items de una venta"""
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    article = models.ForeignKey(Article, on_delete=models.PROTECT, verbose_name='Artículo')
    quantity = models.DecimalField('Cantidad', max_digits=12, decimal_places=3, default=1)
    unit_price = models.DecimalField('Precio unitario', max_digits=12, decimal_places=2)
    discount = models.DecimalField('Descuento', max_digits=12, decimal_places=2, default=0)
    subtotal = models.DecimalField('Subtotal', max_digits=12, decimal_places=2)
    created_at = models.DateTimeField('Creado', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Item de venta'
        verbose_name_plural = 'Items de venta'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.article} x {self.quantity}"
    
    def save(self, *args, **kwargs):
        self.subtotal = (self.unit_price * self.quantity) - self.discount
        super().save(*args, **kwargs)
        # Actualizar total de la venta
        self.sale.save()


class CashRegister(models.Model):
    """Control de caja del TPV"""
    STATUS_CHOICES = [
        ('open', 'Abierta'),
        ('closed', 'Cerrada'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name='Usuario')
    opening_balance = models.DecimalField('Saldo inicial', max_digits=12, decimal_places=2, default=0)
    closing_balance = models.DecimalField('Saldo final', max_digits=12, decimal_places=2, null=True, blank=True)
    status = models.CharField('Estado', max_length=20, choices=STATUS_CHOICES, default='open')
    opening_time = models.DateTimeField('Hora de apertura', auto_now_add=True)
    closing_time = models.DateTimeField('Hora de cierre', null=True, blank=True)
    notes = models.TextField('Notas', blank=True)
    
    class Meta:
        verbose_name = 'Caja'
        verbose_name_plural = 'Cajas'
        ordering = ['-opening_time']
    
    def __str__(self):
        return f"Caja {self.id} - {self.get_status_display()} por {self.user.username}"
    
    def get_total_sales(self):
        """Obtiene el total de ventas completadas de esta caja (excluye canceladas)"""
        return self.sales.filter(status='completed').aggregate(total=Sum('total'))['total'] or 0
    
    def get_cancelled_sales_total(self):
        """Obtiene el total de ventas canceladas de esta caja"""
        return self.sales.filter(status='cancelled').aggregate(total=Sum('total'))['total'] or 0
    
    def get_cancelled_sales_count(self):
        """Obtiene la cantidad de ventas canceladas"""
        return self.sales.filter(status='cancelled').count()
    
    def close_register(self, user):
        """Cierra la caja"""
        if self.status == 'open':
            self.status = 'closed'
            self.closing_time = timezone.now()
            self.closing_balance = self.opening_balance + self.get_total_sales()
            self.save()
