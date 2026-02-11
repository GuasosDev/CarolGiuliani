from django.apps import AppConfig


class CommunicationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'communications'
    verbose_name = 'Sistema de Comunicaciones'
    
    def ready(self):
        """Import signals when app is ready"""
        import communications.signals
