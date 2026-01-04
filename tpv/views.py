from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q, Sum
from django.utils import timezone
from .models import Sale, SaleItem, CashRegister
from inventory.models import Article
from clients.models import Client
from django.db import transaction
import json
from decimal import Decimal

@login_required
def tpv_home(request):
    """Vista principal del TPV"""
    # Verificar si hay una caja abierta para este usuario
    active_register = CashRegister.objects.filter(
        user=request.user,
        status='open'
    ).first()
    
    context = {
        'active_register': active_register,
        'recent_sales': Sale.objects.filter(seller=request.user).order_by('-created_at')[:5]
    }
    return render(request, 'tpv/home.html', context)

@login_required
def open_register(request):
    """Abrir caja"""
    # Verificar si ya tiene caja abierta
    if CashRegister.objects.filter(user=request.user, status='open').exists():
        messages.warning(request, 'Ya tienes una caja abierta.')
        return redirect('tpv:new_sale')
        
    if request.method == 'POST':
        opening_balance = request.POST.get('opening_balance', 0)
        notes = request.POST.get('notes', '')
        
        CashRegister.objects.create(
            user=request.user,
            opening_balance=opening_balance,
            status='open',
            notes=notes
        )
        messages.success(request, 'Caja abierta exitosamente.')
        return redirect('tpv:new_sale')
        
    return render(request, 'tpv/open_register.html')

@login_required
def close_register(request):
    """Cerrar caja"""
    register = get_object_or_404(CashRegister, user=request.user, status='open')
    
    if request.method == 'POST':
        try:
            # IMPORTANTE: Vincular ventas huérfanas antes de cerrar
            # Esto corrige ventas creadas antes de agregar el campo cash_register
            orphan_sales = Sale.objects.filter(
                seller=request.user,
                cash_register__isnull=True,
                created_at__gte=register.opening_time,
                status='completed'
            )
            orphan_count = orphan_sales.update(cash_register=register)
            
            register.close_register(request.user)
            messages.success(request, f'Caja cerrada. Total de ventas: ${register.get_total_sales()}')
            if orphan_count > 0:
                messages.info(request, f'Se vincularon {orphan_count} ventas a esta caja.')
            return redirect('tpv:home')
        except Exception as e:
            messages.error(request, f'Error al cerrar caja: {str(e)}')
            return redirect('tpv:home')
    
    # Calcular totales incluyendo ventas huérfanas para la vista previa
    current_total = register.get_total_sales()
    orphan_total = Sale.objects.filter(
        seller=request.user,
        cash_register__isnull=True,
        created_at__gte=register.opening_time,
        status='completed'
    ).aggregate(total=Sum('total'))['total'] or 0
    
    total_sales = current_total + orphan_total
    
    # Calcular ventas canceladas
    cancelled_count = register.get_cancelled_sales_count()
    cancelled_total = register.get_cancelled_sales_total()
    
    # Mostrar resumen antes de cerrar
    context = {
        'register': register,
        'total_sales': total_sales,
        'cancelled_count': cancelled_count,
        'cancelled_total': cancelled_total,
        'expected_balance': register.opening_balance + total_sales
    }
    return render(request, 'tpv/close_register.html', context)

@login_required
def new_sale(request):
    """Interfaz principal de venta"""
    # Verificar caja abierta
    register = CashRegister.objects.filter(user=request.user, status='open').first()
    if not register:
        messages.warning(request, 'Debes abrir caja antes de realizar ventas.')
        return redirect('tpv:open_register')
        
    context = {
        'register': register,
        'clients': Client.objects.all(),
    }
    return render(request, 'tpv/new_sale.html', context)

@login_required
def sales_list(request):
    """Historial de ventas"""
    sales = Sale.objects.filter(seller=request.user).order_by('-created_at')
    return render(request, 'tpv/sales_list.html', {'sales': sales})

@login_required
def sale_detail(request, sale_id):
    """Detalle de venta"""
    sale = get_object_or_404(Sale, id=sale_id)
    return render(request, 'tpv/sale_detail.html', {'sale': sale})

@login_required
def receipt(request, sale_id):
    """Vista de ticket/factura"""
    sale = get_object_or_404(Sale, id=sale_id)
    return render(request, 'tpv/receipt.html', {'sale': sale})

@login_required
@transaction.atomic
def modify_sale(request, sale_id):
    """
    Modificar una venta existente:
    1. Cancela la venta actual (revierte stock).
    2. Carga los items en la interfaz de nueva venta.
    """
    sale = get_object_or_404(Sale, id=sale_id)
    
    # Solo permitir modificar si no está ya cancelada
    if sale.status == 'cancelled':
        messages.error(request, 'No se puede modificar una venta cancelada.')
        return redirect('tpv:sale_detail', sale_id=sale.id)

    # Cancelar la venta antigua
    try:
        sale.cancel_sale()
        messages.info(request, f'Venta {sale.code} revertida para edición. Se ha creado un borrador con los items.')
    except Exception as e:
        messages.error(request, f'Error al revertir venta: {str(e)}')
        return redirect('tpv:sale_detail', sale_id=sale.id)

    # Preparar el contexto para new_sale como si fuera una nueva venta
    # pero precargando el carrito
    register = CashRegister.objects.filter(user=request.user, status='open').first()
    if not register:
        messages.warning(request, 'Debes abrir caja para modificar sventas.')
        return redirect('tpv:open_register')
        
    # Construir carrito inicial desde los items de la venta
    initial_cart = []
    for item in sale.items.all():
        initial_cart.append({
            'id': item.article.id,
            'description': item.article.description,
            'price': float(item.unit_price), # Usar precio original de la venta? O actual?
            # Si es edición, deberíamos preservar el precio al que se vendió, 
            # pero mi new_sale usa el precio actual del articulo.
            # Por simplicidad y consistencia, usaremos el precio guardado en el item.
            # PERO new_sale logic recalcula subtotales en JS basado en precio.
            'quantity': float(item.quantity),
            'subtotal': float(item.subtotal)
        })

    context = {
        'register': register,
        'clients': Client.objects.all(),
        'initial_cart': json.dumps(initial_cart),
        'initial_client': sale.customer.id if sale.customer else '',
        'initial_payment': sale.payment_method
    }
    return render(request, 'tpv/new_sale.html', context)

@login_required
@require_POST
@transaction.atomic
def delete_sale(request, sale_id):
    """
    Eliminar una venta (solo admin y si pertenece a caja abierta)
    """
    # Verificar que el usuario es administrador
    if not request.user.is_staff:
        messages.error(request, 'No tienes permisos para eliminar ventas.')
        return redirect('tpv:sales_list')
    
    sale = get_object_or_404(Sale, id=sale_id)
    
    # Verificar que la venta pertenece a una caja abierta
    if not sale.cash_register or sale.cash_register.status != 'open':
        messages.error(request, 'Solo se pueden eliminar ventas de cajas abiertas.')
        return redirect('tpv:sales_list')
    
    # Verificar que no esté ya cancelada
    if sale.status == 'cancelled':
        messages.warning(request, 'Esta venta ya está cancelada.')
        return redirect('tpv:sales_list')
    
    try:
        sale_code = sale.code
        sale.cancel_sale()
        messages.success(request, f'Venta {sale_code} eliminada correctamente. Stock revertido.')
    except Exception as e:
        messages.error(request, f'Error al eliminar venta: {str(e)}')
    
    return redirect('tpv:sales_list')

# API Endpoints for AJAX interactions

@login_required
def search_article(request):
    """Buscar artículos por código, código de barras o descripción"""
    query = request.GET.get('q', '')
    if len(query) < 2:
        return JsonResponse([], safe=False)
        
    articles = Article.objects.filter(
        Q(code__icontains=query) |
        Q(barcode__icontains=query) |
        Q(description__icontains=query),
        is_active=True
    )[:10]
    
    results = [{
        'id': a.id,
        'code': a.code,
        'description': a.description,
        'price': float(a.price),
        'stock': float(a.stock),
        'barcode': a.barcode
    } for a in articles]
    
    return JsonResponse(results, safe=False)

@login_required
@require_POST
def add_to_cart(request):
    """Validar y preparar item para agregar"""
    try:
        data = json.loads(request.body)
        article_id = data.get('article_id')
        quantity = float(data.get('quantity', 1))
        
        article = get_object_or_404(Article, id=article_id)
        
        if article.stock < quantity:
            return JsonResponse({
                'error': f'Stock insuficiente. Disponible: {article.stock}'
            }, status=400)
            
        return JsonResponse({
            'success': True,
            'item': {
                'id': article.id,
                'description': article.description,
                'price': float(article.price),
                'quantity': quantity,
                'subtotal': float(article.price) * quantity
            }
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@require_POST
@transaction.atomic
def process_sale(request):
    """Procesar y guardar la venta completa"""
    try:
        data = json.loads(request.body)
        items = data.get('items', [])
        client_id = data.get('client_id')
        payment_method = data.get('payment_method', 'cash')
        
        if not items:
            return JsonResponse({'error': 'No hay items en la venta'}, status=400)
            
        # Obtener caja abierta
        register = CashRegister.objects.filter(user=request.user, status='open').first()
        if not register:
             return JsonResponse({'error': 'No hay una caja abierta para este usuario.'}, status=400)

        # Crear venta
        sale = Sale(
            seller=request.user,
            cash_register=register,
            payment_method=payment_method,
            status='draft'  # Se pasará a completed al final
        )
        
        if client_id:
            sale.customer_id = client_id
            
        sale.save() # Para generar ID y Código
        
        # Crear items
        for item_data in items:
            article = Article.objects.get(id=item_data['id'])
            quantity = Decimal(str(item_data['quantity']))
            
            SaleItem.objects.create(
                sale=sale,
                article=article,
                quantity=quantity,
                unit_price=article.price, # Usar precio actual
                subtotal=article.price *  quantity 
            )
            
        # Recalcular totales y completar
        sale.save() # Recalcula totales en save()
        sale.complete_sale() # Descuenta stock y marca como completed
        
        return JsonResponse({
            'success': True,
            'sale_id': sale.id,
            'redirect_url': f'/tpv/sale/{sale.id}/receipt/'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

