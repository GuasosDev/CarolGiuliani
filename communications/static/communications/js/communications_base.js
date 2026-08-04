(function () {
    function getMailConfig() {
        return document.getElementById('comm-mail-config');
    }

    function configValue(name) {
        var el = getMailConfig();
        return el ? (el.dataset[name] || '') : '';
    }

    function commMailUrlById(tpl, id) {
        return String(tpl || '').replace('999999', String(id));
    }

    function commMailGetCookie(name) {
        var m = document.cookie.match('(^|;) ?' + name + '=([^;]*)(;|$)');
        return m ? decodeURIComponent(m[2]) : '';
    }

    function commMailCurrentConversationId() {
        var p = new URLSearchParams(window.location.search);
        var id = p.get('conversation');
        if (id) return id;
        var em = p.get('email_message');
        if (em) {
            var el = document.querySelector('.conversation-item[data-id="' + String(em) + '"]');
            if (el) return el.getAttribute('data-conversation-id') || el.getAttribute('data-id');
        }
        var active = document.querySelector('.conversation-item.active');
        if (!active) return null;
        return active.getAttribute('data-conversation-id') || active.getAttribute('data-id');
    }

    function commMailClearDetailPanel() {
        var panel = document.getElementById('conversation-detail-panel');
        if (!panel) return;
        panel.innerHTML = '<div class="d-flex flex-column align-items-center justify-content-center h-100 text-muted p-4">' +
            '<div class="bg-white p-4 rounded-circle shadow-sm mb-3"><i class="far fa-comments fa-3x text-primary opacity-50"></i></div>' +
            '<h5>Selecciona una conversacion</h5><p class="small text-center">Elige un correo de la lista para verlo aqui.</p></div>';
    }

    function commMailRefreshList() {
        var el = document.getElementById('dashboard-conversations-container');
        if (!el || typeof htmx === 'undefined') {
            window.location.reload();
            return;
        }
        var path = window.location.pathname + window.location.search;
        htmx.ajax('GET', path, {
            source: el,
            target: '#dashboard-conversations-container',
            swap: 'outerHTML',
            select: '#dashboard-conversations-container'
        });
    }

    window.commMailRefreshList = commMailRefreshList;

    window.commMailCompose = function (mode) {
        mode = mode || 'new';
        if (mode === 'new') {
            if (typeof window.commMailOpenComposeGlobal === 'function' && document.getElementById('emailComposeModalGlobal')) {
                window.commMailOpenComposeGlobal();
                return;
            }
            var composeUrl = configValue('composeUrl');
            if (typeof htmx === 'undefined') {
                window.location.href = composeUrl;
                return;
            }
            try { if (typeof window.closeModal === 'function') window.closeModal(); } catch (e0) {}
            try { if (typeof window.closeModalSecondary === 'function') window.closeModalSecondary(); } catch (e1) {}
            var modal = document.getElementById('modal');
            if (modal) modal.setAttribute('data-no-backdrop-close', '1');
            var modalBody = document.getElementById('modal-body');
            if (modalBody) {
                modalBody.innerHTML = '<div class="p-4 text-center text-muted"><div class="spinner-border text-primary mb-3" role="status"></div><div>Abriendo redaccion...</div></div>';
            }
            if (typeof window.openModal === 'function') window.openModal();
            var returnUrl = encodeURIComponent(window.location.pathname + window.location.search);
            htmx.ajax('GET', composeUrl + '?return_url=' + returnUrl, {
                target: '#modal-body',
                swap: 'innerHTML'
            });
            return;
        }

        if (typeof window.commMailOpenCompose === 'function') {
            window.commMailOpenCompose(mode);
            return;
        }
        alert('Selecciona un correo de la lista para responder o reenviar.');
    };

    window.commMailMoveToTrash = function () {
        var id = commMailCurrentConversationId();
        if (!id) { alert('Selecciona una conversacion.'); return; }
        if (!confirm('¿Eliminar este email?\n\nSe movera a la Papelera.')) return;
        var fd = new FormData();
        fd.append('status', 'closed');
        fd.append('csrfmiddlewaretoken', commMailGetCookie('csrftoken'));
        fetch(commMailUrlById(configValue('changeStatusTemplate'), id), {
            method: 'POST',
            body: fd,
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': commMailGetCookie('csrftoken'), 'HX-Request': 'true' }
        }).then(function (r) {
            if (!r.ok) { alert('No se pudo eliminar (permisos o error de red).'); return; }
            var u = new URL(window.location.href);
            u.searchParams.delete('conversation');
            u.searchParams.delete('email_message');
            window.history.replaceState({}, '', u);
            commMailClearDetailPanel();
            commMailRefreshList();
        }).catch(function () { alert('Error de red al eliminar.'); });
    };

    window.commMailMarkUnread = function () {
        var id = commMailCurrentConversationId();
        if (!id) { alert('Selecciona una conversacion.'); return; }
        fetch(commMailUrlById(configValue('markUnreadTemplate'), id), {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': commMailGetCookie('csrftoken') }
        }).then(function (r) {
            if (!r.ok) { alert('No se pudo marcar como no leido.'); return; }
            commMailRefreshList();
        }).catch(function () { alert('Error de red.'); });
    };

    window.commMailMarkRead = function () {
        var id = commMailCurrentConversationId();
        if (!id) { alert('Selecciona una conversacion.'); return; }
        fetch(commMailUrlById(configValue('markReadTemplate'), id), {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': commMailGetCookie('csrftoken') }
        }).then(function (r) {
            if (!r.ok) { alert('No se pudo marcar como leido.'); return; }
            commMailRefreshList();
        }).catch(function () { alert('Error de red.'); });
    };
})();

(function () {
    function getComposeModalEl() {
        return document.getElementById('emailComposeModalGlobal');
    }

    var modalEl = getComposeModalEl();
    if (!modalEl) return;

    function cleanupOverlays(exceptId) {
        exceptId = exceptId || '';
        try { if (typeof window.closeModal === 'function') window.closeModal(); } catch (e0) {}
        try { if (typeof window.closeModalSecondary === 'function') window.closeModalSecondary(); } catch (e1) {}

        ['modal', 'modal-secondary'].forEach(function (id) {
            var legacy = document.getElementById(id);
            if (!legacy) return;
            try {
                legacy.classList.remove('show');
                legacy.style.display = 'none';
                legacy.setAttribute('aria-hidden', 'true');
            } catch (e2) {}
        });

        document.querySelectorAll('.modal.show').forEach(function (m) {
            if (!m || !m.id || m.id === exceptId) return;
            try {
                var inst = bootstrap.Modal.getInstance(m);
                if (inst) {
                    inst.hide();
                    return;
                }
            } catch (e3) {}
            try {
                m.classList.remove('show');
                m.style.display = 'none';
                m.setAttribute('aria-hidden', 'true');
            } catch (e4) {}
        });
        document.querySelectorAll('.modal-backdrop').forEach(function (b) {
            try { b.remove(); } catch (e5) {}
        });
        document.body.classList.remove('modal-open');
        document.body.style.removeProperty('padding-right');
        document.body.style.removeProperty('overflow');
    }

    function formatFileSize(bytes) {
        if (!bytes && bytes !== 0) return '';
        var k = 1024;
        var sizes = ['Bytes', 'KB', 'MB', 'GB'];
        var i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    var globalAttachStore = new DataTransfer();

    function getGlobalAttachInput() {
        return document.getElementById('emailAttachGlobal');
    }

    function fileKey(f) {
        return [f.name || '', f.size || 0].join('|');
    }

    function setGlobalAttachFiles(files) {
        var input = getGlobalAttachInput();
        var next = new DataTransfer();
        var seen = {};
        Array.from(files || []).forEach(function (f) {
            if (!f || f.size == null) return;
            var k = fileKey(f);
            if (seen[k]) return;
            seen[k] = true;
            next.items.add(f);
        });
        globalAttachStore = next;
        if (input) {
            input.dataset.commAttachSync = '1';
            try {
                input.files = next.files;
            } catch (e) {}
            setTimeout(function () { input.dataset.commAttachSync = ''; }, 0);
        }
        renderGlobalAttachPreview();
    }

    function clearGlobalAttach() {
        var input = getGlobalAttachInput();
        globalAttachStore = new DataTransfer();
        if (input) {
            input.dataset.commAttachSync = '1';
            try { input.value = ''; } catch (e) {}
            try { input.files = globalAttachStore.files; } catch (e2) {}
            setTimeout(function () { input.dataset.commAttachSync = ''; }, 0);
        }
        var preview = document.getElementById('emailFilePreviewGlobal');
        if (preview) preview.innerHTML = '';
    }

    function appendGlobalFiles(fileList) {
        if (!fileList || !fileList.length) return;
        var prev = Array.from(globalAttachStore.files || []);
        setGlobalAttachFiles(prev.concat(Array.from(fileList)));
    }

    function removeGlobalAttach(index) {
        var kept = [];
        Array.from(globalAttachStore.files || []).forEach(function (f, i) {
            if (i !== index) kept.push(f);
        });
        setGlobalAttachFiles(kept);
        if (!kept.length) {
            var preview = document.getElementById('emailFilePreviewGlobal');
            if (preview) preview.innerHTML = '';
        }
    }

    function renderGlobalAttachPreview() {
        var preview = document.getElementById('emailFilePreviewGlobal');
        var input = getGlobalAttachInput();
        if (!preview) return;
        preview.innerHTML = '';
        var files = (input && input.files) ? input.files : globalAttachStore.files;
        if (!files || !files.length) return;
        Array.from(files).forEach(function (file, index) {
            var fileItem = document.createElement('div');
            fileItem.className = 'd-flex align-items-center justify-content-between p-2 bg-light rounded mb-1';
            var size = formatFileSize(file.size);
            var eyeBtn = '<button type="button" class="btn btn-sm btn-outline-primary" title="Vista previa"><i class="fas fa-eye"></i></button>';
            var delBtn = '<button type="button" class="btn btn-sm btn-outline-danger" title="Quitar"><i class="fas fa-times"></i></button>';
            if (file.type && file.type.indexOf('image/') === 0) {
                var reader = new FileReader();
                reader.onload = function (e) {
                    fileItem.innerHTML = '<div class="d-flex align-items-center flex-grow-1">' +
                        '<img src="' + e.target.result + '" style="width: 40px; height: 40px; object-fit: cover; border-radius: 4px;" class="me-2">' +
                        '<div><div class="small fw-bold"></div><div class="text-muted" style="font-size: 0.7rem;"></div></div></div>' +
                        '<div class="d-flex gap-1">' + eyeBtn + delBtn + '</div>';
                    fileItem.querySelector('.fw-bold').textContent = file.name;
                    fileItem.querySelector('.text-muted').textContent = size;
                    bindPreviewButtons(fileItem, file, index);
                };
                reader.readAsDataURL(file);
            } else {
                var icon = 'fas fa-file text-secondary';
                if (file.type && file.type.indexOf('pdf') !== -1) icon = 'fas fa-file-pdf text-danger';
                else if (file.type && (file.type.indexOf('word') !== -1 || file.type.indexOf('document') !== -1)) icon = 'fas fa-file-word text-primary';
                else if (file.type && (file.type.indexOf('excel') !== -1 || file.type.indexOf('spreadsheet') !== -1)) icon = 'fas fa-file-excel text-success';
                fileItem.innerHTML = '<div class="d-flex align-items-center flex-grow-1">' +
                    '<i class="' + icon + ' me-2"></i><div><div class="small fw-bold"></div><div class="text-muted" style="font-size: 0.7rem;"></div></div></div>' +
                    '<div class="d-flex gap-1">' + eyeBtn + delBtn + '</div>';
                fileItem.querySelector('.fw-bold').textContent = file.name;
                fileItem.querySelector('.text-muted').textContent = size;
                bindPreviewButtons(fileItem, file, index);
            }
            preview.appendChild(fileItem);
        });
    }

    function bindPreviewButtons(fileItem, file, index) {
        var buttons = fileItem.querySelectorAll('button');
        if (buttons[0]) {
            buttons[0].addEventListener('click', function (e) {
                e.preventDefault();
                openGlobalAttachPreview(file, index);
            });
        }
        if (buttons[1]) {
            buttons[1].addEventListener('click', function (e) {
                e.preventDefault();
                removeGlobalAttach(index);
            });
        }
    }

    function ensureUploadPreviewModal() {
        var modal = document.getElementById('uploadPreviewModal');
        if (modal) return modal;
        modal = document.createElement('div');
        modal.id = 'uploadPreviewModal';
        modal.className = 'modal fade';
        modal.tabIndex = -1;
        modal.innerHTML = '<div class="modal-dialog modal-lg modal-dialog-centered"><div class="modal-content">' +
            '<div class="modal-header"><h5 class="modal-title" id="uploadPreviewFileName">Vista previa</h5>' +
            '<button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button></div>' +
            '<div class="modal-body text-center" id="uploadPreviewContent"></div>' +
            '<div class="modal-footer">' +
            '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cerrar</button>' +
            '<button type="button" class="btn btn-danger" id="uploadPreviewRemoveBtn">Eliminar archivo</button>' +
            '</div></div></div>';
        document.body.appendChild(modal);
        var removeBtn = modal.querySelector('#uploadPreviewRemoveBtn');
        if (removeBtn) {
            removeBtn.addEventListener('click', function () {
                if (window.currentUploadFileSource === 'global' && window.currentUploadFileIndex != null) {
                    removeGlobalAttach(window.currentUploadFileIndex);
                    window.currentUploadFileSource = null;
                    var inst = bootstrap.Modal.getInstance(modal);
                    if (inst) inst.hide();
                } else if (typeof window.removeUploadFile === 'function') {
                    window.removeUploadFile();
                }
            });
        }
        return modal;
    }

    function openGlobalAttachPreview(file, index) {
        if (!file || typeof bootstrap === 'undefined') return;
        var modal = ensureUploadPreviewModal();
        var fileNameElement = document.getElementById('uploadPreviewFileName');
        var previewContent = document.getElementById('uploadPreviewContent');
        if (!fileNameElement || !previewContent) return;
        window.currentUploadFileIndex = index;
        window.currentUploadFileSource = 'global';
        fileNameElement.textContent = file.name;
        var ext = (file.name.split('.').pop() || '').toLowerCase();
        var url = URL.createObjectURL(file);
        var html = '';
        if (['jpg', 'jpeg', 'png', 'gif', 'webp'].indexOf(ext) !== -1) {
            html = '<img src="' + url + '" alt="" style="max-width:100%;max-height:500px;border-radius:8px;">';
        } else if (ext === 'pdf') {
            html = '<div class="p-4"><i class="fas fa-file-pdf fa-4x text-danger mb-3"></i><h5></h5><p class="text-muted">Vista previa de PDF no disponible.</p></div>';
        } else {
            html = '<div class="p-4"><i class="fas fa-file fa-4x text-secondary mb-3"></i><h5></h5><p class="text-muted">Vista previa no disponible.</p></div>';
        }
        previewContent.innerHTML = html;
        var h5 = previewContent.querySelector('h5');
        if (h5) h5.textContent = file.name;
        bootstrap.Modal.getOrCreateInstance(modal).show();
    }

    function isGlobalFileDrag(e) {
        var dt = e && e.dataTransfer;
        if (!dt || !dt.types) return false;
        for (var i = 0; i < dt.types.length; i++) {
            if (dt.types[i] === 'Files') return true;
        }
        return false;
    }

    var globalComposeDropGuardOn = false;
    var lastGlobalDropTs = 0;
    function consumeGlobalDropOnce() {
        var now = Date.now();
        if (now - lastGlobalDropTs < 200) return false;
        lastGlobalDropTs = now;
        return true;
    }
    function globalComposeDropGuard(e) {
        if (!isGlobalFileDrag(e)) return;
        e.preventDefault();
        if (e.type !== 'drop') return;
        if (!modalEl.classList.contains('show')) return;
        if (!consumeGlobalDropOnce()) return;
        if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
            appendGlobalFiles(e.dataTransfer.files);
        }
        var content = modalEl.querySelector('.modal-content');
        if (content) content.classList.remove('comm-compose-drop-active');
    }
    function enableGlobalComposeDropGuard() {
        if (globalComposeDropGuardOn) return;
        globalComposeDropGuardOn = true;
        document.addEventListener('dragover', globalComposeDropGuard, false);
        document.addEventListener('drop', globalComposeDropGuard, false);
    }
    function disableGlobalComposeDropGuard() {
        if (!globalComposeDropGuardOn) return;
        globalComposeDropGuardOn = false;
        document.removeEventListener('dragover', globalComposeDropGuard, false);
        document.removeEventListener('drop', globalComposeDropGuard, false);
    }

    function ensureComposeModalBound(el) {
        if (!el || el.dataset.commComposeBound) return;
        el.dataset.commComposeBound = '1';
        el.setAttribute('data-bs-backdrop', 'static');
        el.setAttribute('data-bs-keyboard', 'false');
        // Capture: corta el dismiss de Bootstrap antes de que cierre por click en el fondo
        function blockBackdropDismiss(e) {
            if (e.target === el) {
                e.preventDefault();
                e.stopImmediatePropagation();
            }
        }
        el.addEventListener('click', blockBackdropDismiss, true);
        el.addEventListener('mousedown', blockBackdropDismiss, true);
        el.addEventListener('shown.bs.modal', enableGlobalComposeDropGuard);
        el.addEventListener('hidden.bs.modal', function () {
            disableGlobalComposeDropGuard();
            clearGlobalAttach();
            setTimeout(function () { cleanupOverlays(el.id); }, 0);
        });
    }

    function bindGlobalAttachDnD(el) {
        el = el || modalEl;
        if (!el) return;
        var input = getGlobalAttachInput();
        var dropTarget = el.querySelector('.modal-content') || el;
        var bodyDiv = document.getElementById('emailBodyDivGlobal');
        if (input && !input.dataset.commAttachBound) {
            input.dataset.commAttachBound = '1';
            input.addEventListener('change', function () {
                if (input.dataset.commAttachSync === '1') return;
                var selected = Array.from(this.files || []);
                if (!selected.length) return;
                appendGlobalFiles(selected);
            });
        }
        if (dropTarget && !dropTarget.dataset.commDropBound) {
            dropTarget.dataset.commDropBound = '1';
            var dragDepth = 0;
            dropTarget.addEventListener('dragenter', function (e) {
                if (!isGlobalFileDrag(e)) return;
                e.preventDefault();
                e.stopPropagation();
                dragDepth += 1;
                dropTarget.classList.add('comm-compose-drop-active');
            });
            dropTarget.addEventListener('dragleave', function (e) {
                if (!isGlobalFileDrag(e)) return;
                e.preventDefault();
                dragDepth = Math.max(0, dragDepth - 1);
                if (dragDepth === 0) dropTarget.classList.remove('comm-compose-drop-active');
            });
            dropTarget.addEventListener('dragover', function (e) {
                if (!isGlobalFileDrag(e)) return;
                e.preventDefault();
                e.stopPropagation();
                if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
            });
            dropTarget.addEventListener('drop', function (e) {
                if (!isGlobalFileDrag(e) && !(e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length)) return;
                e.preventDefault();
                e.stopPropagation();
                dragDepth = 0;
                dropTarget.classList.remove('comm-compose-drop-active');
                if (!consumeGlobalDropOnce()) return;
                if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
                    appendGlobalFiles(e.dataTransfer.files);
                }
            });
        }
        if (bodyDiv && !bodyDiv.dataset.commPasteBound) {
            bodyDiv.dataset.commPasteBound = '1';
            bodyDiv.addEventListener('paste', function (e) {
                var cd = e.clipboardData || (e.originalEvent && e.originalEvent.clipboardData);
                if (!cd) return;
                var files = [];
                if (cd.files && cd.files.length) {
                    files = Array.from(cd.files);
                } else if (cd.items) {
                    for (var i = 0; i < cd.items.length; i++) {
                        if (cd.items[i].kind !== 'file') continue;
                        var blob = cd.items[i].getAsFile();
                        if (!blob) continue;
                        files.push(new File([blob], blob.name || ('pegado_' + Date.now() + '.png'), { type: blob.type || 'application/octet-stream' }));
                    }
                }
                if (!files.length) return;
                e.preventDefault();
                appendGlobalFiles(files);
            });
        }
    }

    window.commMailOpenComposeGlobal = function () {
        if (typeof bootstrap === 'undefined') return;
        modalEl = getComposeModalEl();
        if (!modalEl) {
            alert('No se pudo abrir el redactor de correo.');
            return;
        }
        ensureComposeModalBound(modalEl);
        bindGlobalAttachDnD(modalEl);
        if (modalEl.parentElement !== document.body) {
            document.body.appendChild(modalEl);
        }
        cleanupOverlays(modalEl.id);
        ['emailToInputGlobal', 'emailSubjectInputGlobal', 'emailCcInputGlobal', 'emailBccInputGlobal'].forEach(function (id) {
            var el = document.getElementById(id);
            if (el) el.value = '';
        });
        var body = document.getElementById('emailBodyDivGlobal');
        if (body) body.innerHTML = '';
        clearGlobalAttach();

        var existing = bootstrap.Modal.getInstance(modalEl);
        if (existing) {
            try { existing.dispose(); } catch (eDisp) {}
        }
        modalEl.setAttribute('data-bs-backdrop', 'static');
        modalEl.setAttribute('data-bs-keyboard', 'false');
        var inst = new bootstrap.Modal(modalEl, { backdrop: 'static', keyboard: false });
        try {
            if (inst._config) {
                inst._config.backdrop = 'static';
                inst._config.keyboard = false;
            }
        } catch (eCfg) {}
        inst.show();
        try {
            var to = document.getElementById('emailToInputGlobal');
            if (to) to.focus();
        } catch (e) {}
    };

    if (modalEl) {
        ensureComposeModalBound(modalEl);
        bindGlobalAttachDnD(modalEl);
    }

    function initAutocomplete() {
        var input = document.getElementById('emailToInputGlobal');
        var suggest = document.getElementById('emailToSuggestGlobal');
        if (!input || !suggest) return;
        var endpoint = modalEl.dataset.contactsEndpoint || '';
        if (!endpoint) return;
        var items = [];
        var activeIndex = -1;
        var lastQuery = '';
        var timer = null;

        function show() { suggest.classList.remove('d-none'); }
        function hide() { suggest.classList.add('d-none'); activeIndex = -1; }
        function getCurrentToken() {
            var raw = input.value || '';
            var parts = raw.split(',');
            return (parts[parts.length - 1] || '').trim();
        }
        function replaceCurrentToken(nextEmail) {
            var raw = input.value || '';
            var parts = raw.split(',');
            parts[parts.length - 1] = ' ' + nextEmail;
            input.value = parts.map(function (p) { return (p || '').trim(); }).filter(Boolean).join(', ') + ', ';
            input.focus();
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
            if (q === lastQuery && !suggest.classList.contains('d-none')) return;
            lastQuery = q;
            if (timer) clearTimeout(timer);
            timer = setTimeout(function () {
                fetchItems(q).then(function (list) {
                    items = list;
                    activeIndex = -1;
                    render();
                });
            }, 250);
        }

        input.addEventListener('input', schedule);
        input.addEventListener('focus', schedule);
        input.addEventListener('keydown', function (e) {
            if (suggest.classList.contains('d-none')) return;
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

    initAutocomplete();

    var form = document.getElementById('emailFormGlobal');
    if (form) {
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            var bodyDiv = document.getElementById('emailBodyDivGlobal');
            var bodyIn = document.getElementById('emailBodyInputGlobal');
            if (bodyIn) bodyIn.value = bodyDiv ? (bodyDiv.innerHTML || '') : '';
            var btn = document.getElementById('emailSendBtnGlobal');
            if (btn) btn.disabled = true;
            var fd = new FormData(form);
            var attachInput = getGlobalAttachInput();
            if (attachInput && attachInput.files && attachInput.files.length) {
                fd.delete('attachments');
                Array.from(attachInput.files).forEach(function (file) {
                    fd.append('attachments', file);
                });
            }
            fetch(form.action, {
                method: 'POST',
                body: fd,
                credentials: 'same-origin',
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            }).then(function (r) {
                return r.json().then(function (data) { return { ok: r.ok, data: data }; });
            }).then(function (res) {
                if (!res.ok) {
                    var msg = (res.data && (res.data.error || res.data.detail)) ? (res.data.error || res.data.detail) : 'No se pudo enviar el correo.';
                    alert(msg);
                    return;
                }
                bootstrap.Modal.getOrCreateInstance(modalEl).hide();
                if (typeof window.commMailRefreshList === 'function') window.commMailRefreshList();
            }).catch(function () {
                alert('Error de red al enviar el correo.');
            }).finally(function () {
                if (btn) btn.disabled = false;
            });
        });
    }
})();

(function () {
    if (window.commNotify) return;

    var state = {
        enabled: false,
        ctx: null,
        lastPlayAt: 0
    };

    function getAudioContext() {
        if (state.ctx) return state.ctx;
        var AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx) return null;
        state.ctx = new AudioCtx();
        return state.ctx;
    }

    function beep(ctx, freq, startAt, durationSec, volume) {
        var osc = ctx.createOscillator();
        var gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq, startAt);
        gain.gain.setValueAtTime(0.0001, startAt);
        gain.gain.exponentialRampToValueAtTime(volume, startAt + 0.005);
        gain.gain.exponentialRampToValueAtTime(0.0001, startAt + durationSec);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(startAt);
        osc.stop(startAt + durationSec + 0.03);
    }

    function unlockAudio() {
        state.enabled = true;
        document.removeEventListener('pointerdown', unlockAudio, true);
        document.removeEventListener('keydown', unlockAudio, true);
    }

    document.addEventListener('pointerdown', unlockAudio, true);
    document.addEventListener('keydown', unlockAudio, true);

    function playDing(kind) {
        var nowMs = Date.now();
        if (nowMs - state.lastPlayAt < 800) return false;
        state.lastPlayAt = nowMs;
        var ctx = getAudioContext();
        if (!ctx) return false;
        if (ctx.state === 'suspended') ctx.resume().catch(function () {});
        var t = ctx.currentTime + 0.01;
        var vol = 0.12;
        if (kind === 'whatsapp') {
            beep(ctx, 784, t, 0.075, vol);
            beep(ctx, 988, t + 0.10, 0.085, vol);
            return true;
        }
        if (kind === 'email') {
            beep(ctx, 659, t, 0.085, vol);
            beep(ctx, 523, t + 0.13, 0.11, vol);
            return true;
        }
        if (kind === 'internal') {
            beep(ctx, 880, t, 0.06, 0.10);
            beep(ctx, 880, t + 0.085, 0.06, 0.10);
            beep(ctx, 880, t + 0.17, 0.06, 0.10);
            return true;
        }
        beep(ctx, 880, t, 0.08, vol);
        return true;
    }

    window.commNotify = {
        playDing: playDing,
        unlockAudio: unlockAudio,
        isEnabled: function () { return state.enabled; }
    };

    document.body.addEventListener('htmx:afterSwap', function () {
        var transferModal = document.getElementById('transferModal');
        if (transferModal && typeof bootstrap !== 'undefined') {
            bootstrap.Modal.getOrCreateInstance(transferModal);
        }
    });
})();
