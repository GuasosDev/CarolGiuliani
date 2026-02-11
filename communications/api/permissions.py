"""
Custom permissions for Communications API
"""

from rest_framework import permissions


class IsAgentOrSupervisor(permissions.BasePermission):
    """Allow access to agents and supervisors"""
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_staff


class IsSupervisorOrAdmin(permissions.BasePermission):
    """Allow access only to supervisors and admins"""
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (
            request.user.is_superuser or 
            request.user.groups.filter(name='Supervisor').exists()
        )


class IsAssignedAgent(permissions.BasePermission):
    """Allow access only to the assigned agent or supervisors"""
    
    def has_object_permission(self, request, view, obj):
        # Supervisors and admins can access everything
        if request.user.is_superuser or request.user.groups.filter(name='Supervisor').exists():
            return True
        
        # Check if user is the assigned agent
        if hasattr(obj, 'assigned_to'):
            return obj.assigned_to == request.user
        
        # For messages, check the conversation's assigned agent
        if hasattr(obj, 'conversation'):
            return obj.conversation.assigned_to == request.user
        
        return False
