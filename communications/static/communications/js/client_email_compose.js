(function () {
    function formatFileSize(bytes) {
        if (!bytes && bytes !== 0) return '';
        var k = 1024;
        var sizes = ['Bytes', 'KB', 'MB', 'GB'];
        var i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    var form = document.getElementById('emailForm');
    if (!form) return;
    var endpoint = form.dataset.contactsEndpoint || '';
    var inp = document.getElementById('imageInputEmail');
    var prev = document.getElementById('emailFilePreview');

    if (inp && prev) {
        inp.addEventListener('change', function () {
            prev.innerHTML = '';
            if (!this.files || !this.files.length) return;
            var ul = document.createElement('ul');
            ul.className = 'list-unstyled small mb-0';
            Array.from(this.files).forEach(function (f) {
                var li = document.createElement('li');
                li.className = 'text-muted';
                li.textContent = f.name + ' (' + formatFileSize(f.size) + ')';
                ul.appendChild(li);
            });
            prev.appendChild(ul);
        });
    }

    function initFieldAutocomplete(inputId, suggestId) {
        var input = document.getElementById(inputId);
        var suggest = document.getElementById(suggestId);
        if (!input || !suggest || !endpoint) return;

        var items = [];
        var activeIndex = -1;
        var lastQuery = '';
        var timer = null;

        function show() { suggest.style.display = 'block'; }
        function hide() { suggest.style.display = 'none'; suggest.innerHTML = ''; activeIndex = -1; }
        function getCurrentToken() {
            var raw = input.value || '';
            var parts = raw.split(',');
            return (parts[parts.length - 1] || '').trim();
        }
        function replaceCurrentToken(nextEmail) {
            nextEmail = (nextEmail || '').trim();
            if (!nextEmail) return;
            var raw = input.value || '';
            var parts = raw.split(',');
            parts[parts.length - 1] = ' ' + nextEmail;
            input.value = parts.map(function (p) { return (p || '').trim(); }).filter(Boolean).join(', ') + ', ';
            try { input.focus(); } catch (e) {}
            hide();
        }
        function render() {
            suggest.innerHTML = '';
            if (!items.length) { hide(); return; }
            items.forEach(function (it, idx) {
                var row = document.createElement('div');
                row.className = 'comm-email-suggest-item' + (idx === activeIndex ? ' active' : '');
                row.innerHTML = '<div class="comm-email-suggest-name">' + (it.name || it.email) + '</div><div class="comm-email-suggest-email">' + it.email + '</div>';
                row.addEventListener('mousedown', function (e) {
                    e.preventDefault();
                    replaceCurrentToken(it.email);
                });
                suggest.appendChild(row);
            });
            show();
        }
        function fetchItems(q) {
            return fetch(endpoint + '?q=' + encodeURIComponent(q || ''), {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            }).then(function (r) { return r.json(); })
              .then(function (data) { return (data && data.results) ? data.results : []; })
              .catch(function () { return []; });
        }
        function schedule() {
            var q = getCurrentToken();
            if (!q) { hide(); return; }
            if (q === lastQuery && suggest.style.display === 'block') return;
            lastQuery = q;
            if (timer) clearTimeout(timer);
            timer = setTimeout(function () {
                fetchItems(q).then(function (list) {
                    items = list;
                    activeIndex = -1;
                    render();
                });
            }, 200);
        }

        input.addEventListener('input', schedule);
        input.addEventListener('focus', schedule);
        input.addEventListener('keydown', function (e) {
            if (suggest.style.display !== 'block') return;
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                activeIndex = Math.min(items.length - 1, activeIndex + 1);
                render();
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                activeIndex = Math.max(0, activeIndex - 1);
                render();
            } else if (e.key === 'Enter') {
                if (activeIndex >= 0 && activeIndex < items.length) {
                    e.preventDefault();
                    replaceCurrentToken(items[activeIndex].email);
                }
            } else if (e.key === 'Escape') {
                hide();
            }
        });
        document.addEventListener('click', function (evt) {
            if (evt.target === input || suggest.contains(evt.target)) return;
            hide();
        });
    }

    initFieldAutocomplete('emailToInput', 'emailToSuggest');
    initFieldAutocomplete('emailCcInput', 'emailCcSuggest');
    initFieldAutocomplete('emailBccInput', 'emailBccSuggest');

    var convIn = document.getElementById('emailConversationIdInput');
    if (convIn && (!convIn.value || !String(convIn.value).trim())) {
        convIn.removeAttribute('name');
    }

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        var returnUrl = form.getAttribute('data-return-url') || '';
        var emailBodyDiv = document.getElementById('emailBodyDiv');
        var emailBodyInput = document.getElementById('emailBodyInput');
        if (emailBodyDiv && emailBodyInput) {
            var tempDiv = document.createElement('div');
            tempDiv.innerHTML = emailBodyDiv.innerHTML;
            tempDiv.querySelectorAll('img').forEach(function (img) { img.remove(); });
            tempDiv.querySelectorAll('div').forEach(function (div) {
                var h = div.innerHTML || '';
                if (h.indexOf('fa-file-pdf') !== -1 || h.indexOf('fa-file-word') !== -1 ||
                    h.indexOf('fa-file-excel') !== -1 || h.indexOf('fa-file') !== -1) {
                    div.remove();
                }
            });
            var textContent = tempDiv.textContent || tempDiv.innerText || '';
            if (textContent.trim() === '' && (!inp || !inp.files || inp.files.length === 0)) {
                alert('Por favor escribe un mensaje o adjunta archivos antes de enviar.');
                return;
            }
            emailBodyInput.value = emailBodyDiv.innerHTML;
        }

        var formData = new FormData(form);
        if (inp && inp.files.length > 0) {
            formData.delete('attachments');
            Array.from(inp.files).forEach(function (file) {
                formData.append('attachments', file);
            });
        }

        var btn = form.querySelector('button[type="submit"]');
        var originalText = btn ? btn.innerHTML : '';
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin" aria-hidden="true"></i> Enviando...';
        }

        fetch(form.action, {
            method: 'POST',
            body: formData,
            credentials: 'same-origin',
            headers: {
                'X-CSRFToken': formData.get('csrfmiddlewaretoken') || '',
                'Accept': 'application/json'
            }
        }).then(async function (response) {
            var ct = (response.headers.get('content-type') || '').toLowerCase();
            var data = {};
            if (ct.indexOf('application/json') !== -1) {
                try {
                    var raw = await response.text();
                    data = raw ? JSON.parse(raw) : {};
                } catch (parseErr) {
                    data = { error: 'La respuesta JSON del servidor no es valida.' };
                }
            } else {
                var html = await response.text();
                var snippet = html.replace(/\s+/g, ' ').trim().slice(0, 200);
                data = { error: snippet || ('HTTP ' + response.status) };
            }
            if (!response.ok) {
                var errorMsg = data.error || data.detail || ('Error al enviar (HTTP ' + response.status + ')');
                if (typeof errorMsg === 'object') {
                    try { errorMsg = errorMsg.message || JSON.stringify(errorMsg); } catch (e2) { errorMsg = 'Error desconocido'; }
                }
                throw new Error(errorMsg);
            }
            return data;
        }).then(function () {
            if (typeof window.closeModal === 'function') window.closeModal();
            if (returnUrl) {
                window.location.href = returnUrl;
                return;
            }
            window.location.reload();
        }).catch(function (error) {
            alert(error.message || 'No se pudo enviar el correo.');
        }).finally(function () {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = originalText;
            }
        });
    });
})();
