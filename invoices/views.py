from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from core.views import GenericListView, GenericCreateView, GenericUpdateView, GenericDeleteView
from .models import Invoice, InvoiceLine
from .utils import render_to_pdf
from django.shortcuts import get_object_or_404, render
from django.views import View
from django.http import HttpResponse
from django.template.loader import render_to_string




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
        from inventory.models import Article
        context['company_settings'] = CompanySettings.load()
        context['articles'] = Article.objects.all()
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
        article_id = request.POST.get('article')
        article = None
        if article_id:
             from inventory.models import Article
             article = Article.objects.get(pk=article_id)

        InvoiceLine.objects.create(
            invoice=invoice,
            article=article,
            description=request.POST.get('description'),
            serial_number=request.POST.get('serial_number'),
            quantity=request.POST.get('quantity'),
            unit_cost=request.POST.get('unit_cost')
        )
        
        
        # Render lines list (OOB) - we wrap in a tbody with the id and Swap OOB attribute
        # But wait, we can't just wrap it if the template already has the id on the existing tbody.
        # Actually, if we send back a <tbody id="invoice-lines" hx-swap-oob="innerHTML">...</tbody>
        # HTMX will duplicate the tbody if we are not careful OR swap the innerHTML of the target..
        # Easier: Return the partial as is, but wrapped in a div/template with hx-swap-oob.
        # OR: Just change the views to return multiple OOB blocks and NO main content, 
        # since the triggering element (form/button) will handle the "none" swap.
        
        lines_html = render_to_string('invoices/partials/invoice_lines.html', {'invoice': invoice}, request=request)
        # Wrap lines_html to target the tbody. IMPORTANT: Wrap in <table> for browser parsing!
        lines_oob = f'<table><tbody id="invoice-lines" hx-swap-oob="innerHTML">{lines_html}</tbody></table>'
        
        # Render totals (OOB)
        totals_html = render_to_string('invoices/partials/invoice_totals.html', {'invoice': invoice}, request=request)
        
        return HttpResponse(lines_oob + totals_html)

class InvoiceLineDeleteView(LoginRequiredMixin, View):
    def delete(self, request, pk):
        line = get_object_or_404(InvoiceLine, pk=pk)
        invoice = line.invoice
        line.delete()
        
        # Render lines list (OOB)
        # Render lines list (OOB)
        lines_html = render_to_string('invoices/partials/invoice_lines.html', {'invoice': invoice}, request=request)
        lines_oob = f'<table><tbody id="invoice-lines" hx-swap-oob="innerHTML">{lines_html}</tbody></table>'

        # Render totals (OOB)
        totals_html = render_to_string('invoices/partials/invoice_totals.html', {'invoice': invoice}, request=request)
        
        return HttpResponse(lines_oob + totals_html)

class InvoiceLineUpdateView(LoginRequiredMixin, View):
    def get(self, request, pk):
        line = get_object_or_404(InvoiceLine, pk=pk)
        
        if request.GET.get('cancel') == 'true':
             return render(request, 'invoices/partials/invoice_line_row.html', {'line': line})
        
        return render(request, 'invoices/partials/invoice_line_form.html', {'line': line})

    def post(self, request, pk):
        line = get_object_or_404(InvoiceLine, pk=pk)
        invoice = line.invoice
        
        line.description = request.POST.get('description')
        line.serial_number = request.POST.get('serial_number')
        line.quantity = request.POST.get('quantity')
        line.unit_cost = request.POST.get('unit_cost')
        line.save()
        
        # Similar return to Create/Delete: Update the whole list + totals
        # OR just update this row + totals.
        # Updating whole list is safer/easier for numbering etc.
        
        lines_html = render_to_string('invoices/partials/invoice_lines.html', {'invoice': invoice}, request=request)
        lines_oob = f'<table><tbody id="invoice-lines" hx-swap-oob="innerHTML">{lines_html}</tbody></table>'
        
        invoice.refresh_from_db()
        totals_html = render_to_string('invoices/partials/invoice_totals.html', {'invoice': invoice}, request=request)
        
        return HttpResponse(lines_oob + totals_html)


