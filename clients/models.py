from django.db import models

class ClientTag(models.Model):
    name = models.CharField(max_length=50, verbose_name="Nombre")
    color = models.CharField(max_length=7, default="#6c757d", verbose_name="Color") # Hex color
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Client(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nombre")
    email = models.EmailField(verbose_name="Email")
    phone = models.CharField(max_length=20, verbose_name="Teléfono", blank=True, null=True)
    address = models.CharField(max_length=255, verbose_name="Dirección", blank=True, null=True)
    tags = models.ManyToManyField(ClientTag, blank=True, verbose_name="Etiquetas")

    @property
    def tags_display(self):
        return ", ".join([t.name for t in self.tags.all()])

    def __str__(self):
        return self.name
