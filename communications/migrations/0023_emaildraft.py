from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('communications', '0022_emailsignature_image'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailDraft',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('compose_mode', models.CharField(choices=[('new', 'Redactar'), ('reply', 'Responder'), ('reply-all', 'Responder a todos'), ('forward', 'Reenviar')], default='new', max_length=20)),
                ('slot_key', models.CharField(max_length=80, verbose_name='Clave de borrador')),
                ('to_addresses', models.TextField(blank=True)),
                ('cc_addresses', models.TextField(blank=True)),
                ('bcc_addresses', models.TextField(blank=True)),
                ('subject', models.CharField(blank=True, max_length=500)),
                ('html_body', models.TextField(blank=True)),
                ('include_signature', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('conversation', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='email_drafts', to='communications.conversation')),
                ('email_account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='email_drafts', to='communications.emailaccount')),
                ('source_email_message', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='email_drafts', to='communications.emailmessage')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='email_drafts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Borrador de Email',
                'verbose_name_plural': 'Borradores de Email',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='emaildraft',
            constraint=models.UniqueConstraint(fields=('user', 'email_account', 'slot_key'), name='uniq_email_draft_user_account_slot'),
        ),
    ]
