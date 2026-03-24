from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class CompanySettings(models.Model):
    name = models.CharField(max_length=255, default="My Company")
    address = models.TextField(default="123 Street, City")
    phone = models.CharField(max_length=50, default="123-456-7890")
    email = models.EmailField(default="info@example.com")
    
    class Meta:
        verbose_name = "Configuración de Empresa"
        verbose_name_plural = "Configuración de Empresa"

    def save(self, *args, **kwargs):
        if not self.pk and CompanySettings.objects.exists():
            return
        super(CompanySettings, self).save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return self.name

class WorkArea(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nombre del Área")
    description = models.TextField(blank=True, null=True, verbose_name="Descripción")

    class Meta:
        verbose_name = "Área Laboral"
        verbose_name_plural = "Áreas Laborales"

    def __str__(self):
        return self.name

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Administrador'),
        ('supervisor', 'Supervisor'),
        ('employee', 'Empleado'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=50, blank=True, null=True)
    work_area = models.ForeignKey(WorkArea, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Área Laboral", related_name="users")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='employee', verbose_name="Rol del Usuario")

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'userprofile'):
        instance.userprofile.save()
    else:
        UserProfile.objects.create(user=instance)
