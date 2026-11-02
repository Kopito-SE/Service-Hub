from django.core.management.base import BaseCommand, CommandError
from apps.events.processor import process_pending_deliveries

class Command(BaseCommand):
    help = "Process Pending events in the transactional outbox."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Maximum number"
        )
    def handle(self, *args, **options):
        limit = options["limit"]

        if limit < 1:
            raise CommandError("--limit must be greater than zero.")

        self.stdout.write(
            self.style.NOTICE("Starting Outbox Process...")
        )

        result = process_pending_deliveries(limit=limit)

        self.stdout.write("")
        self.stdout.write(f"Processed: {result['processed']}")
        self.stdout.write(
            self.style.SUCCESS(f"Succeeded: {result['succeeded']}")
        )
        self.stdout.write(
            self.style.WARNING(f"Failed: {result['failed']}")
        )
        self.stdout.write(
            self.style.ERROR(f"Dead: {result['dead']}")
        )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS("Outbox processing completed.")
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Administrator alerts created: {result['alerts_created']}"
            )
        )

        self.stdout.write(
            self.style.WARNING(
                f"Alert creation failures: {result['alert_failures']}"
            )
        )