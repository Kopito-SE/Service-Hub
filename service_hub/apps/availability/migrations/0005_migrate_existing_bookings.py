
from django.db import migrations


def migrate_existing_bookings(apps, schema_editor):
    Booking = apps.get_model("bookings", "Booking")
    SlotReservation = apps.get_model("availability", "SlotReservation")

    database = schema_editor.connection.alias

    bookings = (
        Booking.objects.using(database)
        .filter(
            status__in=["pending", "confirmed"]
        )
        .iterator()
    )

    reservations = []

    for booking in bookings:
        reservations.append(
            SlotReservation(
                business_id=booking.business_id,
                staff_member_id=booking.staff_member_id,
                booking_reference=booking.pk,
                start_time=booking.start_time,
                end_time=booking.end_time,
                status=(
                    "active"
                    if booking.status == "pending"
                    else "confirmed"
                ),
                expires_at=None,
            )
        )

    if reservations:
        SlotReservation.objects.using(database).bulk_create(
            reservations,
            batch_size=500,
        )


def reverse_migration(apps, schema_editor):
    SlotReservation = apps.get_model("availability", "SlotReservation")

    database = schema_editor.connection.alias

    SlotReservation.objects.using(database).filter(
        status__in=["active", "confirmed"],
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        (
            "availability",
            "0004_alter_slotreservation_booking_reference_and_more",
        ),
        ("bookings", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            migrate_existing_bookings,
            reverse_migration,
        ),
    ]
