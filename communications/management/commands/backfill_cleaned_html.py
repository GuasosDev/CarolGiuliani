"""
Populate cleaned_html cache for existing EmailMessage records.
Run in batches to avoid blocking the database.

Usage:
    python manage.py backfill_cleaned_html [--batch-size=500]
"""
import logging
import time

from django.core.management.base import BaseCommand
from django.db import transaction

from communications.models import EmailMessage
from communications.utils.html_cleaner import limpiar_email_html

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Backfill cleaned_html field for existing EmailMessage records"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Number of records to process per batch (default: 500)",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        total = EmailMessage.objects.filter(
            cleaned_html__isnull=True
        ).exclude(html_body__isnull=True).exclude(html_body="").count()

        self.stdout.write(f"Found {total} emails to process (batch size: {batch_size})")

        processed = 0
        start_time = time.time()

        while True:
            qs = (
                EmailMessage.objects.filter(cleaned_html__isnull=True)
                .exclude(html_body__isnull=True)
                .exclude(html_body="")
                .only("id", "html_body")[:batch_size]
            )
            batch = list(qs)
            if not batch:
                break

            with transaction.atomic():
                for em in batch:
                    try:
                        em.cleaned_html = limpiar_email_html(em.html_body)
                        em.save(update_fields=["cleaned_html"])
                        processed += 1
                    except Exception as e:
                        logger.error("Failed to clean email %s: %s", em.id, e)

            elapsed = time.time() - start_time
            rate = processed / elapsed if elapsed > 0 else 0
            self.stdout.write(
                f"Processed {processed}/{total} ({rate:.1f}/s)"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Processed {processed} emails in {time.time() - start_time:.1f}s"
            )
        )
