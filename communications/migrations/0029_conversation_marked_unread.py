from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('communications', '0028_merge_20261022_0109'),
    ]

    operations = [
        migrations.AddField(
            model_name='conversation',
            name='marked_unread',
            field=models.BooleanField(default=False, verbose_name='Marcada como no leída'),
        ),
    ]
