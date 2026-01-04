from django.db import models
from clients.models import Client
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from inventory.models import Article, StockMovement
from django.utils import timezone

class Invoice(models.Model):
    client = models.ForeignKey('clients.Client', on_delete=models.CASCADE)
    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=20, choices=[
        ('Pending', 'Pending'),
        ('Paid', 'Paid'),
        ('Overdue', 'Overdue'),
        ('Canceled', 'Canceled'),
    ], default='Pending')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_status = self.status

    def __str__(self):
        return f"Invoice #{self.pk} - {self.client}"

    def total(self):
        return sum(line.subtotal() for line in self.invoiceline_set.all())

@receiver(post_save, sender=Invoice)
def update_stock_on_paid(sender, instance, created, **kwargs):
    if instance.status == 'Paid' and instance._original_status != 'Paid':
        # Status changed to Paid, deduct stock
        for line in instance.invoiceline_set.all():
            if line.article:
                StockMovement.objects.create(
                    article=line.article,
                    quantity=-line.quantity, # Negative for OUT
                    movement_type='OUT',
                    date=timezone.now(),
                    description=f"Invoice #{instance.pk} Payment"
                )
                # Article stock update is handled by StockMovement signal usually?
                # Does StockMovement model have logic to update Article?
                # If not, we should update it here or in StockMovement.save()
                # Let's check inventory/models.py content. 
                # Assuming simple logic: update directly for now.
                line.article.stock -= line.quantity
                line.article.save()



class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE)
    article = models.ForeignKey('inventory.Article', on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=255)
    serial_number = models.CharField(max_length=50, blank=True, null=True)
    quantity = models.IntegerField(default=1)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        if self.article:
            if not self.unit_cost:
                self.unit_cost = self.article.price
            if not self.description:
                self.description = self.article.description
        super().save(*args, **kwargs)

    def subtotal(self):
        return self.quantity * self.unit_cost
