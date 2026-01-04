from django.db import models
from django.utils import timezone

class Article(models.Model):
    code = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stock = models.IntegerField(default=0)

    def __str__(self):
        return f"[{self.code}] {self.description}"

class StockMovement(models.Model):
    MOVEMENT_TYPES = [
        ('IN', 'In'),
        ('OUT', 'Out'),
        ('ADJ', 'Adjustment'),
    ]

    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    movement_type = models.CharField(max_length=3, choices=MOVEMENT_TYPES)
    date = models.DateTimeField(default=timezone.now)
    description = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.movement_type} - {self.article} ({self.quantity})"
