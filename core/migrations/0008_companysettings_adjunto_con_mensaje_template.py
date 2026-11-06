from django.db import migrations


TEMPLATE_ENTRY = {
    'name': 'adjunto_con_mensaje',
    'language': 'es',
    'label': 'Plantilla con adjunto PDF',
    'body_params': 1,
    'header_type': 'document',
}


def _matches(template):
    return (
        isinstance(template, dict)
        and template.get('name') == TEMPLATE_ENTRY['name']
        and template.get('language') == TEMPLATE_ENTRY['language']
    )


def add_template(apps, schema_editor):
    CompanySettings = apps.get_model('core', 'CompanySettings')
    settings_obj, _ = CompanySettings.objects.get_or_create(pk=1)
    templates = settings_obj.whatsapp_templates
    if not isinstance(templates, list):
        templates = []
    if not any(_matches(template) for template in templates):
        templates.append(dict(TEMPLATE_ENTRY))
        settings_obj.whatsapp_templates = templates
        settings_obj.save(update_fields=['whatsapp_templates'])


def remove_template(apps, schema_editor):
    CompanySettings = apps.get_model('core', 'CompanySettings')
    for settings_obj in CompanySettings.objects.all():
        templates = settings_obj.whatsapp_templates
        if not isinstance(templates, list):
            continue
        filtered = [template for template in templates if not _matches(template)]
        if filtered != templates:
            settings_obj.whatsapp_templates = filtered
            settings_obj.save(update_fields=['whatsapp_templates'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_companysettings_whatsapp_templates'),
    ]

    operations = [
        migrations.RunPython(add_template, remove_template),
    ]
