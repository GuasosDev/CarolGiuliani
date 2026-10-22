from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('communications', '0025_emailmessage_emailmsg_acct_date_idx'),
    ]

    operations = [
        migrations.AddField(
            model_name='contact',
            name='force_welcome_menu',
            field=models.BooleanField(default=False, verbose_name='Forzar menú de bienvenida'),
        ),
    ]
