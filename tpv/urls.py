from django.urls import path
from . import views

app_name = 'tpv'

urlpatterns = [
    # Vistas principales
    path('', views.tpv_home, name='home'),
    path('open-register/', views.open_register, name='open_register'),
    path('close-register/', views.close_register, name='close_register'),
    path('new-sale/', views.new_sale, name='new_sale'),
    path('sales/', views.sales_list, name='sales_list'),
    path('sale/<int:sale_id>/', views.sale_detail, name='sale_detail'),
    path('sale/<int:sale_id>/receipt/', views.receipt, name='receipt'),
    path('sale/<int:sale_id>/modify/', views.modify_sale, name='modify_sale'),
    path('sale/<int:sale_id>/delete/', views.delete_sale, name='delete_sale'),
    
    # API Endpoints
    path('api/search-article/', views.search_article, name='search_article'),
    path('api/add-to-cart/', views.add_to_cart, name='add_to_cart'),
    path('api/process-sale/', views.process_sale, name='process_sale'),
]