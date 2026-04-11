"""
URL configuration for gd_soft_gty project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.views import (
    DashboardView, CompanySettingsUpdateView, UserProfileUpdateView, GlobalSearchView,
    PrivacyPolicyView, TermsOfServiceView, DataDeletionView, update_personalization,
    WorkAreaListView, WorkAreaCreateView, WorkAreaUpdateView, WorkAreaDeleteView,
    UserManagementListView, UserManagementCreateView, UserManagementUpdateView, UserManagementDeleteView,
    GroupListView, GroupCreateView, GroupUpdateView, GroupDeleteView,
    UserRoleListView, UserRoleCreateView, UserRoleUpdateView, UserRoleDeleteView
)

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
    path('search/', GlobalSearchView.as_view(), name='global_search'),
    path('admin/', admin.site.urls),
    path('clients/', include('clients.urls')),
    path('communications/', include('communications.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
    path('settings/company/', CompanySettingsUpdateView.as_view(), name='company_settings'),
    path('settings/profile/', UserProfileUpdateView.as_view(), name='user_profile'),
    path('settings/personalization/', update_personalization, name='update_personalization'),
    
    # Work Areas
    path('settings/work-areas/', WorkAreaListView.as_view(), name='work_area_list'),
    path('settings/work-areas/create/', WorkAreaCreateView.as_view(), name='work_area_create'),
    path('settings/work-areas/<int:pk>/update/', WorkAreaUpdateView.as_view(), name='work_area_update'),
    path('settings/work-areas/<int:pk>/delete/', WorkAreaDeleteView.as_view(), name='work_area_delete'),
    
    # User Roles
    path('settings/roles/', UserRoleListView.as_view(), name='user_role_list'),
    path('settings/roles/create/', UserRoleCreateView.as_view(), name='user_role_create'),
    path('settings/roles/<int:pk>/update/', UserRoleUpdateView.as_view(), name='user_role_update'),
    path('settings/roles/<int:pk>/delete/', UserRoleDeleteView.as_view(), name='user_role_delete'),
    
    # Privileges (Groups)
    path('settings/privileges/', GroupListView.as_view(), name='privilege_list'),
    path('settings/privileges/create/', GroupCreateView.as_view(), name='privilege_create'),
    path('settings/privileges/<int:pk>/update/', GroupUpdateView.as_view(), name='privilege_update'),
    path('settings/privileges/<int:pk>/delete/', GroupDeleteView.as_view(), name='privilege_delete'),
    
    # User Management
    path('settings/users/', UserManagementListView.as_view(), name='user_management_list'),
    path('settings/users/create/', UserManagementCreateView.as_view(), name='user_management_create'),
    path('settings/users/<int:pk>/update/', UserManagementUpdateView.as_view(), name='user_management_update'),
    path('settings/users/<int:pk>/delete/', UserManagementDeleteView.as_view(), name='user_management_delete'),
    
    # Legal Pages (Public)
    path('privacy-policy/', PrivacyPolicyView.as_view(), name='privacy_policy'),
    path('terms-of-service/', TermsOfServiceView.as_view(), name='terms_of_service'),
    path('data-deletion/', DataDeletionView.as_view(), name='data_deletion'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
