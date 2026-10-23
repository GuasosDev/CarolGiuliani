/**
 * Adjuntos del modal Redactar (#emailComposeModalGlobal).
 * Independiente del resto: onchange inline + este archivo alcanzan.
 */
(function () {
    'use strict';

    if (!Array.isArray(window.__commGlobalAttachFiles)) {
        window.__commGlobalAttachFiles = [];
    }

    function fileKey(f) {
        return [(f && f.name) || '', (f && f.size) || 0].join('|');
    }

    function dedupe(files) {
        var out = [];
        var seen = {};
        Array.from(files || []).forEach(function (f) {
            if (!f) return;
            var k = fileKey(f);
            if (seen[k]) return;
            seen[k] = true;
            out.push(f);
        });
        return out;
    }

    function formatSize(bytes) {
        if (!bytes && bytes !== 0) return '';
        var k = 1024;
        var sizes = ['Bytes', 'KB', 'MB', 'GB'];
        var i = Math.floor(Math.log(Math.max(bytes, 1)) / Math.log(k));
        if (bytes === 0) return '0 Bytes';
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function getPreviewEl() {
        return document.getElementById('emailFilePreviewGlobal');
    }

    function fileIconClass(file) {
        var type = (file && file.type) || '';
        if (type.indexOf('image/') === 0) return 'fas fa-file-image text-primary';
        if (type.indexOf('pdf') !== -1) return 'fas fa-file-pdf text-danger';
        if (type.indexOf('word') !== -1 || type.indexOf('document') !== -1) return 'fas fa-file-word text-primary';
        if (type.indexOf('excel') !== -1 || type.indexOf('spreadsheet') !== -1) return 'fas fa-file-excel text-success';
        return 'fas fa-file text-secondary';
    }

    function renderPreview() {
        var preview = getPreviewEl();
        if (!preview) return;
        var files = window.__commGlobalAttachFiles || [];
        preview.innerHTML = '';
        if (!files.length) return;

        var list = document.createElement('div');
        list.className = 'comm-attach-preview-list';
        list.setAttribute('role', 'list');
        list.setAttribute('aria-label', files.length + ' archivo(s) adjunto(s)');

        files.forEach(function (file, index) {
            var chip = document.createElement('div');
            chip.className = 'comm-attach-chip';
            chip.setAttribute('role', 'listitem');
            chip.title = (file.name || 'archivo') + ' · ' + formatSize(file.size);

            var icon = document.createElement('i');
            icon.className = fileIconClass(file);
            icon.setAttribute('aria-hidden', 'true');

            var nameEl = document.createElement('span');
            nameEl.className = 'comm-attach-chip-name';
            nameEl.textContent = file.name || 'archivo';

            var sizeEl = document.createElement('span');
            sizeEl.className = 'comm-attach-chip-size';
            sizeEl.textContent = formatSize(file.size);

            var eye = document.createElement('button');
            eye.type = 'button';
            eye.className = 'comm-attach-chip-btn';
            eye.title = 'Vista previa';
            eye.setAttribute('aria-label', 'Vista previa de ' + (file.name || 'archivo'));
            eye.innerHTML = '<i class="fas fa-eye" aria-hidden="true"></i>';
            eye.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                openPreview(file, index);
            });

            var del = document.createElement('button');
            del.type = 'button';
            del.className = 'comm-attach-chip-btn comm-attach-chip-btn-danger';
            del.title = 'Quitar';
            del.setAttribute('aria-label', 'Quitar ' + (file.name || 'archivo'));
            del.innerHTML = '<i class="fas fa-times" aria-hidden="true"></i>';
            del.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                window.commRemoveGlobalAttach(index);
            });

            chip.appendChild(icon);
            chip.appendChild(nameEl);
            chip.appendChild(sizeEl);
            chip.appendChild(eye);
            chip.appendChild(del);
            list.appendChild(chip);
        });

        preview.appendChild(list);
    }

    function raiseUploadPreviewAboveCompose(modal) {
        if (!modal) return;
        modal.style.zIndex = '1100';
        var markBackdrops = function () {
            var backs = document.querySelectorAll('.modal-backdrop');
            if (!backs.length) return;
            backs[backs.length - 1].classList.add('modal-backdrop-upload-preview');
        };
        modal.addEventListener('shown.bs.modal', markBackdrops, { once: true });
        setTimeout(markBackdrops, 50);
    }

    function isPdfFile(file) {
        if (!file) return false;
        var name = (file.name || '').toLowerCase();
        var type = (file.type || '').toLowerCase();
        return name.slice(-4) === '.pdf' || type === 'application/pdf' || type.indexOf('pdf') !== -1;
    }

    function renderFilePreviewHtml(file) {
        var name = file.name || 'Archivo';
        var ext = (name.split('.').pop() || '').toLowerCase();
        var url = URL.createObjectURL(file);
        if (['jpg', 'jpeg', 'png', 'gif', 'webp'].indexOf(ext) !== -1) {
            return '<img src="' + url + '" alt="" style="max-width:100%;max-height:500px;border-radius:8px;">';
        }
        if (isPdfFile(file) || ext === 'pdf') {
            return (
                '<div class="text-start">' +
                '<embed src="' + url + '#toolbar=1" type="application/pdf" ' +
                'style="width:100%;height:min(70vh,560px);border:1px solid #dee2e6;border-radius:8px;background:#f8f9fa;">' +
                '<p class="text-muted small mt-2 mb-0">Si no se ve el PDF: ' +
                '<a href="' + url + '" target="_blank" rel="noopener">abrir en pestaña</a></p>' +
                '</div>'
            );
        }
        return (
            '<p class="text-muted mb-0">Vista previa no disponible.<br><strong>' +
            String(name).replace(/</g, '&lt;') +
            '</strong></p>'
        );
    }

    function openPreview(file, index) {
        if (!file) {
            alert('Archivo');
            return;
        }
        window.currentUploadFileIndex = index;
        window.currentUploadFileSource = 'global';

        if (typeof bootstrap === 'undefined') {
            // Sin Bootstrap: al menos abrir el PDF/archivo
            try {
                window.open(URL.createObjectURL(file), '_blank');
            } catch (e) {
                alert(file.name || 'Archivo');
            }
            return;
        }

        var modal = document.getElementById('uploadPreviewModal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'uploadPreviewModal';
            modal.className = 'modal fade';
            modal.tabIndex = -1;
            modal.innerHTML =
                '<div class="modal-dialog modal-lg modal-dialog-centered"><div class="modal-content">' +
                '<div class="modal-header"><h5 class="modal-title"><i class="fas fa-eye me-2"></i>' +
                '<span id="uploadPreviewFileName">Vista previa</span></h5>' +
                '<button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>' +
                '<div class="modal-body text-center" id="uploadPreviewContent"></div>' +
                '<div class="modal-footer">' +
                '<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cerrar</button>' +
                '<button type="button" class="btn btn-danger" id="uploadPreviewDeleteBtn">' +
                '<i class="fas fa-trash me-2"></i>Eliminar</button></div></div></div>';
            document.body.appendChild(modal);
        }

        var nameEl = document.getElementById('uploadPreviewFileName');
        var content = document.getElementById('uploadPreviewContent');
        if (nameEl) nameEl.textContent = file.name || 'Vista previa';
        if (content) content.innerHTML = renderFilePreviewHtml(file);

        var delBtn = document.getElementById('uploadPreviewDeleteBtn');
        if (delBtn) {
            delBtn.onclick = function () {
                window.commRemoveGlobalAttach(index);
                var inst = bootstrap.Modal.getInstance(modal);
                if (inst) inst.hide();
            };
        }
        raiseUploadPreviewAboveCompose(modal);
        bootstrap.Modal.getOrCreateInstance(modal).show();
    }

    window.commGlobalOnAttachChange = function (input) {
        if (!input) return;
        var selected = Array.from(input.files || []);
        if (!selected.length) return;

        window.__commGlobalAttachFiles = dedupe(
            (window.__commGlobalAttachFiles || []).concat(selected)
        );
        renderPreview();

        try {
            input.value = '';
        } catch (e) {}
    };

    window.commAppendGlobalAttachFiles = function (fileList) {
        if (!fileList || !fileList.length) return;
        window.__commGlobalAttachFiles = dedupe(
            (window.__commGlobalAttachFiles || []).concat(Array.from(fileList))
        );
        renderPreview();
    };

    window.commRemoveGlobalAttach = function (index) {
        window.__commGlobalAttachFiles = (window.__commGlobalAttachFiles || []).filter(function (_f, i) {
            return i !== index;
        });
        renderPreview();
    };

    window.commClearGlobalAttach = function () {
        window.__commGlobalAttachFiles = [];
        var input = document.getElementById('emailAttachGlobal');
        if (input) {
            try { input.value = ''; } catch (e) {}
        }
        renderPreview();
    };

    window.commGetGlobalAttachFiles = function () {
        return (window.__commGlobalAttachFiles || []).slice();
    };
})();
