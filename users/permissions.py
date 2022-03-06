from django.contrib.auth.models import Group
from rest_framework import permissions

from users.models import User, Userrole


class IsOwner(permissions.BasePermission):
    #def has_permission(self, request, view):
        #### can write custom code
     #   user = User.objects.get(pk=view.kwargs['pk'])
     #   if request.user == user:
     #       return True
        ## if have more condition then apply
     #   return False
    def has_object_permission(self, request, view, obj):
        return obj.username == request.user.username

class IsStaff(permissions.BasePermission):
    def has_permission(self, request, view):
        g = Group.objects.get(name='Staff')
        u=request.user
        return g in u.groups.all()

class IsMed(permissions.BasePermission):
    def has_permission(self, request, view):
        g = Userrole.objects.get(category='Med')
        u=request.user
        return g in u.roles.all()

