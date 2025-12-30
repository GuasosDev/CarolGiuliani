from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from core.views import GenericListView, GenericCreateView, GenericUpdateView, GenericDeleteView
from .models import Invoice, InvoiceLine
from .utils import render_to_pdf
from django.shortcuts import get_object_or_404, render
from django.views import View
from django.http import HttpResponse



class InvoiceListView(GenericListView):
    model = Invoice
    list_fields = ['id', 'client', 'issue_date', 'due_date', 'status', 'total']
    list_headers = ['#', 'Issued to', 'Issue Date', 'Due Date', 'Status', 'Amount']
    title = "Facturas"
    create_url_name = 'invoice_create'
    # update_url_name = 'invoice_update' # Removing to use custom Edit action pointing to Detail
    delete_url_name = 'invoice_delete'
    detail_url_name = 'invoice_detail'
    action_template_name = 'invoices/partials/invoice_actions.html'

class InvoicePDFView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        invoice = get_object_or_404(Invoice, pk=kwargs['pk'])
        # Get company settings
        from core.models import CompanySettings
        company_settings = CompanySettings.load()
        
        data = {
            'invoice': invoice,
            'company_settings': company_settings,
        }
        pdf = render_to_pdf('invoices/invoice_pdf.html', data)
        return HttpResponse(pdf, content_type='application/pdf')

class InvoiceDetailView(LoginRequiredMixin, DetailView):
    model = Invoice
    template_name = 'invoices/invoice_detail.html'
    context_object_name = 'invoice'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from core.models import CompanySettings
        context['company_settings'] = CompanySettings.load()
        context['readonly'] = self.request.GET.get('readonly') == 'true'
        context['print_mode'] = self.request.GET.get('print') == 'true'
        return context

class InvoiceCreateView(GenericCreateView):
    model = Invoice
    fields = ['client', 'issue_date', 'due_date', 'status']
    title = "Nueva Factura"

class InvoiceUpdateView(GenericUpdateView):
    model = Invoice
    fields = ['client', 'issue_date', 'due_date', 'status']
    title = "Editar Factura"

class InvoiceDeleteView(GenericDeleteView):
    model = Invoice

# --- Invoice Lines ---

class InvoiceLineCreateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        InvoiceLine.objects.create(
            invoice=invoice,
            description=request.POST.get('description'),
            serial_number=request.POST.get('serial_number'),
            quantity=request.POST.get('quantity'),
            unit_cost=request.POST.get('unit_cost')
        )
        return render(request, 'invoices/partials/invoice_lines.html', {'invoice': invoice})

class InvoiceLineDeleteView(LoginRequiredMixin, View):
    def delete(self, request, pk):
        line = get_object_or_404(InvoiceLine, pk=pk)
        invoice = line.invoice
        line.delete()
        return render(request, 'invoices/partials/invoice_lines.html', {'invoice': invoice})

