from django.urls import path
from .views import InvoiceListView, InvoiceCreateView, InvoiceUpdateView, InvoiceDeleteView, InvoiceDetailView, InvoiceLineCreateView, InvoiceLineDeleteView, InvoiceLineUpdateView, InvoicePDFView

urlpatterns = [
    path('', InvoiceListView.as_view(), name='invoice_list'),
    path('<int:pk>/', InvoiceDetailView.as_view(), name='invoice_detail'),
    path('<int:pk>/pdf/', InvoicePDFView.as_view(), name='invoice_pdf'),
    path('<int:pk>/add_line/', InvoiceLineCreateView.as_view(), name='invoice_line_create'),
    path('invoice-line/<int:pk>/delete/', InvoiceLineDeleteView.as_view(), name='invoice_line_delete'),
    path('invoice-line/<int:pk>/update/', InvoiceLineUpdateView.as_view(), name='invoice_line_update'),
    path('create/', InvoiceCreateView.as_view(), name='invoice_create'),
    path('update/<int:pk>/', InvoiceUpdateView.as_view(), name='invoice_update'),
    path('delete/<int:pk>/', InvoiceDeleteView.as_view(), name='invoice_delete'),
]
