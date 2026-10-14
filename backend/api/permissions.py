from rest_framework import permissions

from .models import UserRole


class IsOwnerOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == UserRole.OWNER


class IsProjectManager(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == UserRole.PROJECT_MANAGER


class IsOwnerOrPM(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in [UserRole.OWNER, UserRole.PROJECT_MANAGER]


class IsVideographerOrEditor(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in [UserRole.VIDEOGRAPHER, UserRole.EDITOR]


class IsAssignedToProject(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.role == UserRole.OWNER:
            return True
        return obj.project_manager == request.user


class IsAssignedToTask(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.role in [UserRole.OWNER, UserRole.PROJECT_MANAGER]:
            return True
        return obj.assigned_to == request.user
