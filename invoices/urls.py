from django.urls import path
from .views import InvoiceListView, InvoiceCreateView, InvoiceUpdateView, InvoiceDeleteView, InvoiceDetailView, InvoiceLineCreateView, InvoiceLineDeleteView, InvoicePDFView

urlpatterns = [
    path('', InvoiceListView.as_view(), name='invoice_list'),
    path('<int:pk>/', InvoiceDetailView.as_view(), name='invoice_detail'),
    path('<int:pk>/pdf/', InvoicePDFView.as_view(), name='invoice_pdf'),
    path('<int:pk>/add_line/', InvoiceLineCreateView.as_view(), name='invoice_line_create'),
    path('line/<int:pk>/delete/', InvoiceLineDeleteView.as_view(), name='invoice_line_delete'),
    path('create/', InvoiceCreateView.as_view(), name='invoice_create'),
    path('update/<int:pk>/', InvoiceUpdateView.as_view(), name='invoice_update'),
    path('delete/<int:pk>/', InvoiceDeleteView.as_view(), name='invoice_delete'),
]
