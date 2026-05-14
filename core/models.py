from django.db import models
from django.contrib.auth.models import User, Group
from django.db.models.signals import post_save
from django.dispatch import receiver

class CompanySettings(models.Model):
    name = models.CharField(max_length=255, default="My Company")
    address = models.TextField(default="123 Street, City")
    phone = models.CharField(max_length=50, default="123-456-7890")
    email = models.EmailField(default="info@example.com")
    whatsapp_templates_enabled = models.BooleanField(default=False, verbose_name="Plantillas WhatsApp habilitadas")
    whatsapp_templates = models.JSONField(default=list, blank=True, verbose_name="Plantillas WhatsApp")
    
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

class UserRole(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nombre del Rol")
    description = models.TextField(blank=True, null=True, verbose_name="Descripción")
    
    # Permissions and Status
    is_active = models.BooleanField(default=True, verbose_name="Activo (Active)")
    is_staff = models.BooleanField(default=False, verbose_name="Acceso al Staff (Staff status)")
    is_superuser = models.BooleanField(default=False, verbose_name="Superusuario (Superuser status)")
    
    # Associated Groups
    groups = models.ManyToManyField(Group, blank=True, related_name="user_roles", verbose_name="Grupos asociados")

    class Meta:
        verbose_name = "Rol"
        verbose_name_plural = "Roles"

    def __str__(self):
        return self.name

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=50, blank=True, null=True)
    work_area = models.ForeignKey(WorkArea, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Área Laboral", related_name="users")
    user_role = models.ForeignKey(UserRole, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Rol del Usuario", related_name="users")
    
    # Personalization
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name="Imagen de Perfil")
    dark_mode = models.BooleanField(default=False, verbose_name="Modo Oscuro")
    font_size = models.IntegerField(default=16, verbose_name="Tamaño de Fuente (px)")

    def __str__(self):
        return f"{self.user.username} - {self.user_role.name if self.user_role else 'Sin Rol'}"

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
