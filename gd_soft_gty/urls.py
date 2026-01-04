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
from core.views import DashboardView, CompanySettingsUpdateView, UserProfileUpdateView

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
    path('admin/', admin.site.urls),
    path('clients/', include('clients.urls')),
    path('invoices/', include('invoices.urls')),
    path('tpv/', include('tpv.urls')),
    path('inventory/', include('inventory.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
    path('settings/company/', CompanySettingsUpdateView.as_view(), name='company_settings'),
    path('settings/profile/', UserProfileUpdateView.as_view(), name='user_profile'),
]
