from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import StaffWorkingHours, StaffTimeOff
from .serializers import(StaffWorkingHoursSerializer, StaffTimeOffSerializer)



class StaffWorkingHoursViewSet(viewsets.ModelViewSet):
    serializer_class = StaffWorkingHoursSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = [
        "get", "post", "put", "patch", "delete", "head", "options"
    ]

    def get_queryset(self):
        return(
            StaffWorkingHours.objects
            .filter(staff_member__business__owner=self.request.user)
            .select_related("staff_member", "staff_member__business")
        )

class StaffTimeOffViewSet(viewsets.ModelViewSet):
    serializer_class = StaffTimeOffSerializer
    permission_classes = [IsAuthenticated]

    http_method_names = [
        "get", "post", "patch", "put", "delete", "head", "options"
    ]

    def get_queryset(self):
        return(
            StaffTimeOff.objects
            .filter(staff_member__business__owner=self.request.user)
            .select_related("staff_member", "staff_member__business")
        )

