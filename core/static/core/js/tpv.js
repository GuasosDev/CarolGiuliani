// TPV (Punto de Venta) JavaScript

// Variables globales
let cart = [];
let currentInput = '';
let currentProductId = null;

// Inicialización
document.addEventListener('DOMContentLoaded', function() {
    // Inicializar el carrito desde localStorage si existe
    loadCart();
    
    // Configurar eventos
    setupEventListeners();
    
    // Actualizar la interfaz
    updateCartUI();
});

// Configurar event listeners
function setupEventListeners() {
    // Búsqueda de productos
    const barcodeInput = document.getElementById('barcode-input');
    if (barcodeInput) {
        barcodeInput.addEventListener('keyup', debounce(handleSearch, 300));
    }
    
    // Teclado numérico
    document.querySelectorAll('.num-btn').forEach(button => {
        button.addEventListener('click', function() {
            handleNumericInput(this.getAttribute('data-num'));
        });
    });
    
    // Botón de borrar
    const backspaceBtn = document.getElementById('backspace');
    if (backspaceBtn) {
        backspaceBtn.addEventListener('click', function() {
            currentInput = currentInput.slice(0, -1);
            updateCurrentInput();
        });
    }
    
    // Botón de limpiar carrito
    const clearCartBtn = document.getElementById('clearCart');
    if (clearCartBtn) {
        clearCartBtn.addEventListener('click', clearCart);
    }
    
    // Botón de cobrar
    const checkoutBtn = document.getElementById('checkout-btn');
    if (checkoutBtn) {
        checkoutBtn.addEventListener('click', function() {
            const checkoutModal = new bootstrap.Modal(document.getElementById('checkoutModal'));
            
            // Actualizar total en el modal
            const total = calculateTotal();
            document.getElementById('total-amount').value = formatCurrency(total);
            
            // Resetear campos
            document.getElementById('amount-received').value = '';
            document.getElementById('change').value = formatCurrency(0);
            
            // Mostrar modal
            checkoutModal.show();
        });
    }
    
    // Calcular cambio
    const amountReceived = document.getElementById('amount-received');
    if (amountReceived) {
        amountReceived.addEventListener('input', calculateChange);
    }
    
    // Confirmar pago
    const confirmPaymentBtn = document.getElementById('confirm-payment');
    if (confirmPaymentBtn) {
        confirmPaymentBtn.addEventListener('click', processPayment);
    }
    
    // Manejar descuento
    const discountInput = document.getElementById('discount');
    if (discountInput) {
        discountInput.addEventListener('input', updateTotals);
    }
    
    // Cargar clientes
    loadCustomers();
}

// Buscar productos
function handleSearch(e) {
    const query = e.target.value.trim();
    if (query.length < 2) return;
    
    fetch(`/tpv/api/search-article/?q=${encodeURIComponent(query)}`)
        .then(response => response.json())
        .then(data => {
            displaySearchResults(data.results);
        })
        .catch(error => {
            console.error('Error al buscar productos:', error);
            showAlert('Error al buscar productos', 'danger');
        });
}

// Mostrar resultados de búsqueda
function displaySearchResults(products) {
    const resultsContainer = document.getElementById('search-results');
    if (!resultsContainer) return;
    
    if (!products || products.length === 0) {
        resultsContainer.innerHTML = `
            <tr>
                <td colspan="6" class="text-center py-3 text-muted">
                    No se encontraron productos
                </td>
            </tr>`;
        return;
    }
    
    resultsContainer.innerHTML = products.map(product => `
        <tr>
            <td>${product.code}</td>
            <td>${product.description}</td>
            <td>${formatCurrency(product.price)}</td>
            <td>${product.stock}</td>
            <td>
                <input type="number" 
                       class="form-control form-control-sm quantity-input" 
                       value="1" min="1" max="${product.stock}" 
                       data-product-id="${product.id}">
            </td>
            <td>
                <button class="btn btn-sm btn-primary add-to-cart" 
                        data-product='${JSON.stringify(product)}'>
                    <i class="bi bi-cart-plus"></i>
                </button>
            </td>
        </tr>
    `).join('');
    
    // Agregar event listeners a los botones de agregar al carrito
    document.querySelectorAll('.add-to-cart').forEach(button => {
        button.addEventListener('click', function() {
            const product = JSON.parse(this.getAttribute('data-product'));
            const input = this.closest('tr').querySelector('.quantity-input');
            const quantity = parseInt(input.value) || 1;
            
            addToCart({
                id: product.id,
                code: product.code,
                description: product.description,
                price: parseFloat(product.price),
                quantity: quantity,
                stock: parseFloat(product.stock)
            });
            
            // Cerrar el modal después de agregar
            const modal = bootstrap.Modal.getInstance(document.getElementById('addProductModal'));
            if (modal) modal.hide();
        });
    });
}

// Manejar entrada numérica
function handleNumericInput(value) {
    if (value === '.') {
        if (!currentInput.includes('.')) {
            currentInput += value;
        }
    } else {
        currentInput += value;
    }
    
    updateCurrentInput();
}

// Actualizar campo de entrada actual
function updateCurrentInput() {
    if (currentProductId) {
        const input = document.querySelector(`.quantity-input[data-product-id="${currentProductId}"]`);
        if (input) {
            input.value = currentInput || '0';
            
            // Actualizar cantidad en el carrito si el producto ya está agregado
            const itemIndex = cart.findIndex(item => item.id === currentProductId);
            if (itemIndex !== -1) {
                updateCartItemQuantity(currentProductId, parseFloat(currentInput) || 1);
            }
        }
    }
    
    // Resetear después de un tiempo de inactividad
    clearTimeout(window.inputTimeout);
    window.inputTimeout = setTimeout(() => {
        currentInput = '';
        currentProductId = null;
    }, 2000);
}

// Agregar producto al carrito
function addToCart(product) {
    // Verificar si el producto ya está en el carrito
    const existingItemIndex = cart.findIndex(item => item.id === product.id);
    
    if (existingItemIndex !== -1) {
        // Actualizar cantidad si ya existe
        cart[existingItemIndex].quantity += product.quantity;
    } else {
        // Agregar nuevo ítem
        cart.push({
            id: product.id,
            code: product.code,
            description: product.description,
            price: product.price,
            quantity: product.quantity,
            stock: product.stock
        });
    }
    
    // Guardar en localStorage
    saveCart();
    
    // Actualizar UI
    updateCartUI();
    
    // Mostrar notificación
    showAlert(`"${product.description}" agregado al carrito`, 'success');
}

// Actualizar cantidad de un ítem en el carrito
function updateCartItemQuantity(productId, quantity) {
    const itemIndex = cart.findIndex(item => item.id === productId);
    
    if (itemIndex !== -1) {
        if (quantity <= 0) {
            // Eliminar si la cantidad es 0 o menos
            cart.splice(itemIndex, 1);
        } else {
            // Actualizar cantidad
            cart[itemIndex].quantity = quantity;
        }
        
        // Guardar cambios
        saveCart();
        updateCartUI();
    }
}

// Eliminar ítem del carrito
function removeFromCart(productId) {
    cart = cart.filter(item => item.id !== productId);
    saveCart();
    updateCartUI();
}

// Limpiar carrito
function clearCart() {
    if (confirm('¿Está seguro de que desea vaciar el carrito?')) {
        cart = [];
        saveCart();
        updateCartUI();
        showAlert('Carrito vaciado', 'info');
    }
}

// Actualizar la interfaz del carrito
function updateCartUI() {
    const cartItems = document.getElementById('cart-items');
    const emptyCartMessage = document.getElementById('empty-cart-message');
    const cartCount = document.getElementById('cart-count');
    const checkoutBtn = document.getElementById('checkout-btn');
    
    // Actualizar contador
    const totalItems = cart.reduce((total, item) => total + item.quantity, 0);
    cartCount.textContent = totalItems;
    
    // Habilitar/deshabilitar botón de cobrar
    if (checkoutBtn) {
        checkoutBtn.disabled = cart.length === 0;
    }
    
    // Mostrar mensaje si el carrito está vacío
    if (cart.length === 0) {
        if (emptyCartMessage) emptyCartMessage.style.display = '';
        if (cartItems) cartItems.innerHTML = '';
        updateTotals();
        return;
    }
    
    // Ocultar mensaje de carrito vacío
    if (emptyCartMessage) emptyCartMessage.style.display = 'none';
    
    // Generar filas de la tabla
    if (cartItems) {
        cartItems.innerHTML = cart.map((item, index) => `
            <tr data-product-id="${item.id}">
                <td>${index + 1}</td>
                <td>
                    <div class="fw-bold">${item.description}</div>
                    <small class="text-muted">${item.code}</small>
                </td>
                <td>
                    <div class="input-group input-group-sm">
                        <button class="btn btn-outline-secondary minus-btn" type="button">-</button>
                        <input type="number" class="form-control text-center quantity" 
                               value="${item.quantity}" min="1" max="${item.stock}">
                        <button class="btn btn-outline-secondary plus-btn" type="button">+</button>
                    </div>
                </td>
                <td class="text-end">${formatCurrency(item.price)}</td>
                <td class="text-end fw-bold">${formatCurrency(item.price * item.quantity)}</td>
                <td class="text-center">
                    <button class="btn btn-sm btn-outline-danger remove-item">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            </tr>
        `).join('');
        
        // Agregar event listeners a los botones de cantidad
        cartItems.querySelectorAll('.quantity').forEach(input => {
            input.addEventListener('change', function() {
                const productId = parseInt(this.closest('tr').getAttribute('data-product-id'));
                const quantity = parseFloat(this.value) || 1;
                updateCartItemQuantity(productId, quantity);
            });
        });
        
        // Botones de incrementar/disminuir
        cartItems.querySelectorAll('.plus-btn').forEach(button => {
            button.addEventListener('click', function() {
                const input = this.previousElementSibling;
                input.stepUp();
                input.dispatchEvent(new Event('change'));
            });
        });
        
        cartItems.querySelectorAll('.minus-btn').forEach(button => {
            button.addEventListener('click', function() {
                const input = this.nextElementSibling;
                input.stepDown();
                input.dispatchEvent(new Event('change'));
            });
        });
        
        // Botones de eliminar
        cartItems.querySelectorAll('.remove-item').forEach(button => {
            button.addEventListener('click', function() {
                const productId = parseInt(this.closest('tr').getAttribute('data-product-id'));
                removeFromCart(productId);
            });
        });
    }
    
    // Actualizar totales
    updateTotals();
}

// Actualizar totales
function updateTotals() {
    const subtotal = calculateSubtotal();
    const discount = parseFloat(document.getElementById('discount').value) || 0;
    const tax = calculateTax(subtotal - discount);
    const total = subtotal - discount + tax;
    
    // Actualizar UI
    document.getElementById('subtotal').textContent = formatCurrency(subtotal);
    document.getElementById('tax').textContent = formatCurrency(tax);
    document.getElementById('total').textContent = formatCurrency(total);
    
    return total;
}

// Calcular subtotal
function calculateSubtotal() {
    return cart.reduce((total, item) => {
        return total + (item.price * item.quantity);
    }, 0);
}

// Calcular impuestos (16%)
function calculateTax(amount) {
    return amount * 0.16; // 16% de IVA
}

// Calcular total
function calculateTotal() {
    const subtotal = calculateSubtotal();
    const discount = parseFloat(document.getElementById('discount').value) || 0;
    return subtotal - discount + calculateTax(subtotal - discount);
}

// Calcular cambio
function calculateChange() {
    const amountReceived = parseFloat(document.getElementById('amount-received').value) || 0;
    const total = calculateTotal();
    const change = amountReceived - total;
    
    document.getElementById('change').value = formatCurrency(change >= 0 ? change : 0);
    
    // Habilitar/deshabilitar botón de confirmar pago
    const confirmBtn = document.getElementById('confirm-payment');
    if (confirmBtn) {
        confirmBtn.disabled = amountReceived < total;
    }
}

// Procesar pago
function processPayment() {
    const amountReceived = parseFloat(document.getElementById('amount-received').value) || 0;
    const total = calculateTotal();
    
    if (amountReceived < total) {
        showAlert('El monto recibido es menor al total', 'danger');
        return;
    }
    
    // Crear objeto con los datos de la venta
    const saleData = {
        items: cart.map(item => ({
            article_id: item.id,
            quantity: item.quantity,
            unit_price: item.price
        })),
        payment_method: document.getElementById('payment-method').value,
        customer_id: document.getElementById('customer').value || null,
        notes: document.getElementById('notes').value,
        amount_received: amountReceived
    };
    
    // Enviar datos al servidor
    fetch('/tpv/api/process-sale/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFTTOKEN': getCookie('csrftoken')
        },
        body: JSON.stringify(saleData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Mostrar recibo
            const receiptWindow = window.open('', '_blank');
            receiptWindow.document.write(`
                <html>
                    <head>
                        <title>Recibo de Venta #${data.sale.code}</title>
                        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
                        <style>
                            body { font-family: Arial, sans-serif; font-size: 14px; }
                            .receipt { width: 80mm; margin: 0 auto; padding: 10px; }
                            .text-center { text-align: center; }
                            .text-right { text-align: right; }
                            .border-top { border-top: 1px dashed #000; }
                            .mt-2 { margin-top: 0.5rem; }
                            .mt-3 { margin-top: 1rem; }
                            .mb-2 { margin-bottom: 0.5rem; }
                            .fw-bold { font-weight: bold; }
                        </style>
                    </head>
                    <body>
                        <div class="receipt">
                            <div class="text-center mb-3">
                                <h4>${document.title || 'Punto de Venta'}</h4>
                                <p class="mb-1">${new Date().toLocaleString()}</p>
                                <p class="mb-1">Venta #${data.sale.code}</p>
                            </div>
                            
                            <table class="table table-sm">
                                <thead>
                                    <tr>
                                        <th>Cant</th>
                                        <th>Descripción</th>
                                        <th class="text-right">Total</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${data.sale.items.map(item => `
                                        <tr>
                                            <td>${item.quantity}</td>
                                            <td>${item.article_description}</td>
                                            <td class="text-right">${formatCurrency(item.subtotal)}</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                            
                            <div class="border-top pt-2">
                                <div class="d-flex justify-content-between">
                                    <span>Subtotal:</span>
                                    <span>${formatCurrency(data.sale.subtotal)}</span>
                                </div>
                                <div class="d-flex justify-content-between">
                                    <span>IVA (16%):</span>
                                    <span>${formatCurrency(data.sale.tax_amount)}</span>
                                </div>
                                <div class="d-flex justify-content-between fw-bold">
                                    <span>Total:</span>
                                    <span>${formatCurrency(data.sale.total)}</span>
                                </div>
                                <div class="d-flex justify-content-between">
                                    <span>Recibido:</span>
                                    <span>${formatCurrency(amountReceived)}</span>
                                </div>
                                <div class="d-flex justify-content-between fw-bold">
                                    <span>Cambio:</span>
                                    <span>${formatCurrency(amountReceived - data.sale.total)}</span>
                                </div>
                            </div>
                            
                            <div class="text-center mt-3">
                                <p class="mb-1">¡Gracias por su compra!</p>
                                <p class="text-muted small">${data.sale.notes || ''}</p>
                            </div>
                        </div>
                        
                        <script>
                            // Imprimir automáticamente
                            window.onload = function() {
                                setTimeout(function() {
                                    window.print();
                                    window.onafterprint = function() {
                                        window.close();
                                    };
                                }, 500);
                            };
                        </script>
                    </body>
                </html>
            `);
            
            // Limpiar carrito y reiniciar
            clearCart();
            
            // Cerrar modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('checkoutModal'));
            if (modal) modal.hide();
            
            // Mostrar mensaje de éxito
            showAlert('Venta registrada correctamente', 'success');
        } else {
            throw new Error(data.error || 'Error al procesar la venta');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showAlert(error.message || 'Error al procesar la venta', 'danger');
    });
}

// Cargar clientes para el select
function loadCustomers() {
    fetch('/api/clients/')
        .then(response => response.json())
        .then(data => {
            const select = document.getElementById('customer');
            if (select) {
                // Limpiar opciones existentes
                select.innerHTML = '<option value="">Seleccionar cliente...</option>';
                
                // Agregar clientes
                data.forEach(client => {
                    const option = document.createElement('option');
                    option.value = client.id;
                    option.textContent = `${client.name} ${client.last_name || ''}`.trim();
                    select.appendChild(option);
                });
            }
        })
        .catch(error => {
            console.error('Error al cargar clientes:', error);
        });
}

// Guardar carrito en localStorage
function saveCart() {
    localStorage.setItem('tpv_cart', JSON.stringify(cart));
}

// Cargar carrito desde localStorage
function loadCart() {
    const savedCart = localStorage.getItem('tpv_cart');
    if (savedCart) {
        try {
            cart = JSON.parse(savedCart);
        } catch (e) {
            console.error('Error al cargar el carrito:', e);
            cart = [];
        }
    }
}

// Mostrar notificación
function showAlert(message, type = 'info') {
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    alert.style.top = '20px';
    alert.style.right = '20px';
    alert.style.zIndex = '9999';
    alert.role = 'alert';
    
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    document.body.appendChild(alert);
    
    // Eliminar después de 3 segundos
    setTimeout(() => {
        alert.classList.remove('show');
        setTimeout(() => alert.remove(), 150);
    }, 3000);
}

// Formatear moneda
function formatCurrency(amount) {
    return new Intl.NumberFormat('es-MX', {
        style: 'currency',
        currency: 'MXN',
        minimumFractionDigits: 2
    }).format(amount);
}

// Obtener cookie por nombre
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Debounce para búsquedas
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Inicializar tooltips
const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
});
