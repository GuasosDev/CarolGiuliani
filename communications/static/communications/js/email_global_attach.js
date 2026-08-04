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

    function renderPreview() {
        var preview = getPreviewEl();
        if (!preview) return;
        var files = window.__commGlobalAttachFiles || [];
        preview.innerHTML = '';
        if (!files.length) return;

        files.forEach(function (file, index) {
            var row = document.createElement('div');
            row.className = 'd-flex align-items-center justify-content-between p-2 bg-light rounded mb-1 border';

            var info = document.createElement('div');
            info.className = 'd-flex align-items-center flex-grow-1 me-2';
            info.style.minWidth = '0';

            var icon = document.createElement('i');
            icon.className = 'fas fa-file text-secondary me-2';
            if (file.type && file.type.indexOf('image/') === 0) icon.className = 'fas fa-file-image text-primary me-2';
            else if (file.type && file.type.indexOf('pdf') !== -1) icon.className = 'fas fa-file-pdf text-danger me-2';
            else if (file.type && (file.type.indexOf('word') !== -1 || file.type.indexOf('document') !== -1)) icon.className = 'fas fa-file-word text-primary me-2';
            info.appendChild(icon);

            var text = document.createElement('div');
            text.style.minWidth = '0';
            var nameEl = document.createElement('div');
            nameEl.className = 'small fw-bold text-truncate';
            nameEl.textContent = file.name || 'archivo';
            var sizeEl = document.createElement('div');
            sizeEl.className = 'text-muted';
            sizeEl.style.fontSize = '0.7rem';
            sizeEl.textContent = formatSize(file.size);
            text.appendChild(nameEl);
            text.appendChild(sizeEl);
            info.appendChild(text);

            var actions = document.createElement('div');
            actions.className = 'd-flex gap-1 flex-shrink-0';

            var eye = document.createElement('button');
            eye.type = 'button';
            eye.className = 'btn btn-sm btn-outline-primary';
            eye.title = 'Vista previa';
            eye.innerHTML = '<i class="fas fa-eye" aria-hidden="true"></i>';
            eye.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                openPreview(file, index);
            });

            var del = document.createElement('button');
            del.type = 'button';
            del.className = 'btn btn-sm btn-outline-danger';
            del.title = 'Quitar';
            del.innerHTML = '<i class="fas fa-times" aria-hidden="true"></i>';
            del.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                window.commRemoveGlobalAttach(index);
            });

            actions.appendChild(eye);
            actions.appendChild(del);
            row.appendChild(info);
            row.appendChild(actions);
            preview.appendChild(row);
        });
    }

    function openPreview(file, index) {
        if (!file || typeof bootstrap === 'undefined') {
            alert((file && file.name) || 'Archivo');
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
        window.currentUploadFileIndex = index;
        var nameEl = document.getElementById('uploadPreviewFileName');
        var content = document.getElementById('uploadPreviewContent');
        if (nameEl) nameEl.textContent = file.name || 'Vista previa';
        if (content) {
            var ext = ((file.name || '').split('.').pop() || '').toLowerCase();
            var url = URL.createObjectURL(file);
            if (['jpg', 'jpeg', 'png', 'gif', 'webp'].indexOf(ext) !== -1) {
                content.innerHTML = '<img src="' + url + '" alt="" style="max-width:100%;max-height:500px;border-radius:8px;">';
            } else if (ext === 'pdf') {
                content.innerHTML = '<p class="text-muted mb-0">Vista previa de PDF no disponible.<br><strong></strong></p>';
                var strong = content.querySelector('strong');
                if (strong) strong.textContent = file.name;
            } else {
                content.innerHTML = '<p class="text-muted mb-0">Vista previa no disponible.<br><strong></strong></p>';
                var strong2 = content.querySelector('strong');
                if (strong2) strong2.textContent = file.name;
            }
        }
        var delBtn = document.getElementById('uploadPreviewDeleteBtn');
        if (delBtn) {
            delBtn.onclick = function () {
                window.commRemoveGlobalAttach(index);
                var inst = bootstrap.Modal.getInstance(modal);
                if (inst) inst.hide();
            };
        }
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
