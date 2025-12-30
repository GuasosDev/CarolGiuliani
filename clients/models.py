from django.db import models

class Client(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nombre")
    email = models.EmailField(verbose_name="Email")
    phone = models.CharField(max_length=20, verbose_name="Teléfono", blank=True, null=True)
    address = models.CharField(max_length=255, verbose_name="Dirección", blank=True, null=True)

    def __str__(self):
        return self.name
