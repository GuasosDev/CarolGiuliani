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
    var attachStore = new DataTransfer();

    function fileKey(f) {
        return [f.name || '', f.size || 0].join('|');
    }

    function renderPreview(files) {
        if (!prev) return;
        prev.innerHTML = '';
        if (!files || !files.length) return;
        var ul = document.createElement('ul');
        ul.className = 'list-unstyled small mb-0';
        Array.from(files).forEach(function (f) {
            var li = document.createElement('li');
            li.className = 'text-muted';
            li.textContent = f.name + ' (' + formatFileSize(f.size) + ')';
            ul.appendChild(li);
        });
        prev.appendChild(ul);
    }

    function setFiles(files) {
        var next = new DataTransfer();
        var seen = {};
        Array.from(files || []).forEach(function (f) {
            if (!f || f.size == null) return;
            var k = fileKey(f);
            if (seen[k]) return;
            seen[k] = true;
            next.items.add(f);
        });
        attachStore = next;
        if (inp) {
            inp.dataset.commAttachSync = '1';
            try { inp.files = next.files; } catch (e) {}
            setTimeout(function () { inp.dataset.commAttachSync = ''; }, 0);
        }
        renderPreview(next.files);
    }

    function appendFiles(fileList) {
        if (!fileList || !fileList.length) return;
        var prevFiles = Array.from(attachStore.files || []);
        setFiles(prevFiles.concat(Array.from(fileList)));
    }

    if (inp) {
        inp.addEventListener('change', function () {
            if (inp.dataset.commAttachSync === '1') return;
            var selected = Array.from(this.files || []);
            if (!selected.length) return;
            appendFiles(selected);
        });
    }

    function isFileDrag(e) {
        var dt = e && e.dataTransfer;
        if (!dt || !dt.types) return false;
        for (var i = 0; i < dt.types.length; i++) {
            if (dt.types[i] === 'Files') return true;
        }
        return false;
    }

    var lastClientDropTs = 0;
    function consumeClientDropOnce() {
        var now = Date.now();
        if (now - lastClientDropTs < 200) return false;
        lastClientDropTs = now;
        return true;
    }

    var dropTarget = form.closest('.modal-content') || form.closest('.modal-body') || form;
    if (dropTarget && !dropTarget.dataset.commDropBound) {
        dropTarget.dataset.commDropBound = '1';
        var dragDepth = 0;
        dropTarget.addEventListener('dragenter', function (e) {
            if (!isFileDrag(e)) return;
            e.preventDefault();
            e.stopPropagation();
            dragDepth += 1;
            dropTarget.classList.add('comm-compose-drop-active');
        });
        dropTarget.addEventListener('dragleave', function (e) {
            if (!isFileDrag(e)) return;
            e.preventDefault();
            dragDepth = Math.max(0, dragDepth - 1);
            if (dragDepth === 0) dropTarget.classList.remove('comm-compose-drop-active');
        });
        dropTarget.addEventListener('dragover', function (e) {
            if (!isFileDrag(e)) return;
            e.preventDefault();
            e.stopPropagation();
            if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
        });
        dropTarget.addEventListener('drop', function (e) {
            if (!isFileDrag(e) && !(e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length)) return;
            e.preventDefault();
            e.stopPropagation();
            dragDepth = 0;
            dropTarget.classList.remove('comm-compose-drop-active');
            if (!consumeClientDropOnce()) return;
            if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
                appendFiles(e.dataTransfer.files);
            }
        });

        function clientComposeDropGuard(e) {
            if (!isFileDrag(e)) return;
            e.preventDefault();
            if (e.type === 'drop' && e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
                if (!consumeClientDropOnce()) return;
                appendFiles(e.dataTransfer.files);
                dropTarget.classList.remove('comm-compose-drop-active');
            }
        }
        document.addEventListener('dragover', clientComposeDropGuard, false);
        document.addEventListener('drop', clientComposeDropGuard, false);
        var hostModal = form.closest('.modal') || document.getElementById('modal');
        if (hostModal) {
            hostModal.setAttribute('data-no-backdrop-close', '1');
            hostModal.addEventListener('hidden.bs.modal', function () {
                document.removeEventListener('dragover', clientComposeDropGuard, false);
                document.removeEventListener('drop', clientComposeDropGuard, false);
                dropTarget.classList.remove('comm-compose-drop-active');
            }, { once: true });
        }
    }

    var bodyDiv = document.getElementById('emailBodyDiv');
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
            appendFiles(files);
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

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        var bodyDiv = document.getElementById('emailBodyDiv');
        var bodyIn = document.getElementById('emailBodyInput');
        if (bodyIn) bodyIn.value = bodyDiv ? (bodyDiv.innerHTML || '') : '';
        var formData = new FormData(form);
        if (inp && inp.files && inp.files.length) {
            formData.delete('attachments');
            Array.from(inp.files).forEach(function (file) {
                formData.append('attachments', file);
            });
        }
        var btn = form.querySelector('button[type="submit"]');
        if (btn) btn.disabled = true;
        fetch(form.action, {
            method: 'POST',
            body: formData,
            credentials: 'same-origin',
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        }).then(function (r) {
            return r.json().then(function (data) { return { ok: r.ok, data: data }; }).catch(function () {
                return { ok: r.ok, data: {} };
            });
        }).then(function (res) {
            if (!res.ok) {
                var msg = (res.data && (res.data.error || res.data.detail)) ? (res.data.error || res.data.detail) : 'No se pudo enviar el correo.';
                alert(msg);
                return;
            }
            try { if (typeof window.closeModal === 'function') window.closeModal(); } catch (err) {}
            var returnUrl = form.dataset.returnUrl;
            if (returnUrl) {
                window.location.href = returnUrl;
            } else if (typeof window.commMailRefreshList === 'function') {
                window.commMailRefreshList();
            } else {
                window.location.reload();
            }
        }).catch(function () {
            alert('Error de red al enviar el correo.');
        }).finally(function () {
            if (btn) btn.disabled = false;
        });
    });

    if (typeof window.commSyncSignaturePreviews === 'function') {
        window.commSyncSignaturePreviews(form);
    }
})();
