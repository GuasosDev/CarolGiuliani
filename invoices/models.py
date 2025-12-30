from django.db import models
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

    def __str__(self):
        return f"Invoice #{self.pk} - {self.client}"

    def total(self):
        return sum(line.subtotal() for line in self.invoiceline_set.all())

class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE)
    description = models.CharField(max_length=255)
    serial_number = models.CharField(max_length=50, blank=True, null=True)
    quantity = models.IntegerField(default=1)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)

    def subtotal(self):
        return self.quantity * self.unit_cost
