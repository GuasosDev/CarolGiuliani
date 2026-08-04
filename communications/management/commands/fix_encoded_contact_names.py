from django.core.management.base import BaseCommand
from django.db import transaction

from clients.models import Client
from communications.utils.email_headers import decode_mime_header


def looks_like_mime_header(value):
    value = (value or "").strip()
    return value.startswith("=?") and value.endswith("?=")


class Command(BaseCommand):
    help = "Decodifica nombres de clientes/contactos guardados en formato MIME, como =?ISO-8859-1?...?="

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Guarda los cambios en la base. Sin esta opción solo muestra una vista previa.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limita la cantidad de registros a procesar.",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        limit = options["limit"] or 0

        queryset = Client.objects.exclude(name__isnull=True).exclude(name__exact="")
        clients = []

        for client in queryset.iterator():
            original_name = (client.name or "").strip()
            if not looks_like_mime_header(original_name):
                continue

            decoded_name = decode_mime_header(original_name).strip()
            if not decoded_name or decoded_name == original_name:
                continue

            clients.append((client, original_name, decoded_name))
            if limit and len(clients) >= limit:
                break

        if not clients:
            self.stdout.write(self.style.SUCCESS("No se encontraron nombres codificados para corregir."))
            return

        self.stdout.write(f"Se encontraron {len(clients)} cliente(s) con nombre MIME codificado.")

        for client, original_name, decoded_name in clients:
            self.stdout.write(
                f"- ID {client.id} | {original_name} -> {decoded_name}"
            )

        if not apply_changes:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "Vista previa solamente. Ejecutá de nuevo con --apply para guardar los cambios."
                )
            )
            return

        updated = 0
        with transaction.atomic():
            for client, _original_name, decoded_name in clients:
                client.name = decoded_name
                client.save(update_fields=["name"])
                updated += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Se actualizaron {updated} cliente(s)."))
