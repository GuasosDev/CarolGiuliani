from django.urls import path
from .views import (
    ClientListView, ClientCreateView, ClientUpdateView, ClientDeleteView,
    ClientTagListView, ClientTagCreateView, ClientTagUpdateView, ClientTagDeleteView,
    ClientManageTagsView, ClientUpdateNoteView
)

urlpatterns = [
    path('', ClientListView.as_view(), name='client_list'),
    path('create/', ClientCreateView.as_view(), name='client_create'),
    path('update/<int:pk>/', ClientUpdateView.as_view(), name='client_update'),
    path('delete/<int:pk>/', ClientDeleteView.as_view(), name='client_delete'),
    
    # Tag Management
    path('tags/', ClientTagListView.as_view(), name='client_tag_list'),
    path('all-tags/', ClientTagListView.as_view(template_name='clients/tag_full_list.html'), name='client_tag_full_list'),
    path('tags/create/', ClientTagCreateView.as_view(), name='client_tag_create'),
    path('tags/update/<int:pk>/', ClientTagUpdateView.as_view(), name='client_tag_update'),
    path('tags/delete/<int:pk>/', ClientTagDeleteView.as_view(), name='client_tag_delete'),
    
    # Client Tag Assignment
    path('manage-tags/<int:pk>/', ClientManageTagsView.as_view(), name='client_manage_tags'),
    path('update-note/<int:pk>/', ClientUpdateNoteView.as_view(), name='client_update_note'),
    # For when accessing tag manager from a specific client context
    path('tags/client/<int:client_id>/', ClientTagListView.as_view(), name='client_tag_list_for_client'),
    path('tags/create/client/<int:client_id>/', ClientTagCreateView.as_view(), name='client_tag_create_for_client'),
    

]
