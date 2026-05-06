from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('communications', '0011_internalchatreadstate'),
    ]

    operations = [
        migrations.AddField(
            model_name='internalchatmessage',
            name='file',
            field=models.FileField(blank=True, null=True, upload_to='internal_chat/'),
        ),
        migrations.AddField(
            model_name='internalchatmessage',
            name='mime_type',
            field=models.CharField(blank=True, max_length=120, null=True),
        ),
        migrations.AddField(
            model_name='internalchatmessage',
            name='original_filename',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]

