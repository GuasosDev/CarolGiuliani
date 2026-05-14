from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_userrole_groups_userrole_is_active_userrole_is_staff_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='companysettings',
            name='whatsapp_templates_enabled',
            field=models.BooleanField(default=False, verbose_name='Plantillas WhatsApp habilitadas'),
        ),
        migrations.AddField(
            model_name='companysettings',
            name='whatsapp_templates',
            field=models.JSONField(blank=True, default=list, verbose_name='Plantillas WhatsApp'),
        ),
    ]

