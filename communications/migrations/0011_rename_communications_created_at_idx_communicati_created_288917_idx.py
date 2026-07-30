from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('communications', '0010_internalchatmessage'),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='internalchatmessage',
            new_name='communicati_created_288917_idx',
            old_name='communications_created_at_idx',
        ),
    ]
