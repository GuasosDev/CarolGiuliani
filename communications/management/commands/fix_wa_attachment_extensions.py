"""
Renombra adjuntos de WhatsApp guardados con extensión incorrecta
(p.ej. .sheet en vez de .xlsx) para que Excel/Word los abran.
"""
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile

from communications.models import Message
from communications.whatsapp_handler import extension_from_mime, safe_inbound_filename


BAD_EXTENSIONS = {
    'sheet',
    'vnd.ms-excel',
    'document',
    'msword',
    'presentation',
    'presentationml.presentation',
    'wordprocessingml.document',
    'spreadsheetml.sheet',
    'octet-stream',
}


class Command(BaseCommand):
    help = "Corrige extensiones de adjuntos WhatsApp (Excel/Office) mal guardadas"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo muestra qué se renombraría, sin escribir',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        qs = Message.objects.filter(
            message_type='whatsapp',
            file__isnull=False,
        ).exclude(file='')

        fixed = 0
        skipped = 0

        for message in qs.iterator():
            path = (message.file.name or '').strip()
            if not path:
                skipped += 1
                continue

            current_name = path.rsplit('/', 1)[-1]
            root, ext = current_name.rsplit('.', 1) if '.' in current_name else (current_name, '')
            ext = (ext or '').lower()
            meta = message.metadata or {}
            mime = (meta.get('media_mime_type') or '').strip()
            original = meta.get('original_filename') or ''

            needs_fix = ext in BAD_EXTENSIONS
            if not needs_fix and not mime:
                skipped += 1
                continue
            if not needs_fix:
                # También arreglar si MIME es Excel pero la extensión no coincide
                want = extension_from_mime(mime)
                if want in ('xlsx', 'xls', 'docx', 'doc', 'pptx', 'ppt') and ext != want:
                    needs_fix = True

            if not needs_fix:
                skipped += 1
                continue

            new_name = safe_inbound_filename(
                original or current_name,
                message.pk,
                mime or 'application/octet-stream',
            )
            if new_name == current_name:
                skipped += 1
                continue

            self.stdout.write(f"Message {message.pk}: {current_name} → {new_name}")

            if dry_run:
                fixed += 1
                continue

            try:
                message.file.open('rb')
                data = message.file.read()
                message.file.close()
                old_name = message.file.name
                message.file.save(new_name, ContentFile(data), save=True)
                meta = dict(message.metadata or {})
                meta['original_filename'] = meta.get('original_filename') or new_name
                meta['media_mime_type'] = meta.get('media_mime_type') or mime
                message.metadata = meta
                message.save(update_fields=['metadata'])
                # Borrar el archivo viejo si quedó huérfano con otro nombre
                if old_name and old_name != message.file.name:
                    try:
                        storage = message.file.storage
                        if storage.exists(old_name):
                            storage.delete(old_name)
                    except Exception:
                        pass
                fixed += 1
            except Exception as exc:
                self.stderr.write(f"Error en message {message.pk}: {exc}")

        mode = 'dry-run' if dry_run else 'aplicado'
        self.stdout.write(self.style.SUCCESS(
            f"Listo ({mode}): {fixed} corregidos, {skipped} sin cambios"
        ))
