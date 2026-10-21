from django.db import models
from django.db.models import Q, F

class StaffWorkingHours(models.Model):
    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    staff_member = models.ForeignKey(

        "businesses.StaffMember",
        on_delete=models.CASCADE,
        related_name="working_hours",

    )

    weekday = models.PositiveIntegerField(
        choices=Weekday.choices,
    )

    opening_time = models.TimeField()
    closing_time = models.TimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["staff_member", "weekday"],
                name="unique_staff_working_day"
            ),
            models.CheckConstraint(
                condition=Q(closing_time__gt=F("opening_time")),
                name="staff_closing_after_opening"
            ),
        ]
        ordering = ["weekday", "opening_time"]

    def __str__(self):
        return(
            f"{self.staff_member.display_name} - "
            f"{self.get_weekday_display()}: "
            f"{self.opening_time}-{self.closing_time}"
        )

class StaffTimeOff(models.Model):
    staff_member = models.ForeignKey(
        "businesses.StaffMember",
        on_delete=models.CASCADE,
        related_name="time_off_periods",
    )
    start_time = models.DateTimeField()
    end_time=models.DateTimeField()
    reason = models.CharField(
        max_length=255,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(end_time__gt=F("start_time")),
                name="staff_timeoff_start_idk",
            ),
        ]
        ordering = ["start_time"]
    def __str__(self):
        return(
            f"{self.staff_member.display_name}: "
            f"{self.start_time} - {self.end_time}"
        )
