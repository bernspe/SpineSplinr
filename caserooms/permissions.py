from rest_framework import permissions

from caserooms.models import CaseRoom


class IsOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.owner == request.user

class IsPatient(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if 'Patient' in request.user.role: ## this selects Caregiver of Patients and patients as well
            return True
        else:
            return False