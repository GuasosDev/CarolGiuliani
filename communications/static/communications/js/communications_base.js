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

    window.commMailSyncNow = function (buttonEl) {
        var syncUrl = configValue('syncNowUrl');
        if (!syncUrl) {
            alert('No hay una cuenta de email activa para sincronizar.');
            return;
        }

        var btn = buttonEl || document.getElementById('commMailSyncNowBtn');
        var originalHtml = btn ? btn.innerHTML : '';
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<span class="comm-mail-tb-ico"><i class="fas fa-spinner fa-spin"></i></span><span>Sincronizando...</span>';
        }

        fetch(syncUrl, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'X-CSRFToken': commMailGetCookie('csrftoken'),
                'X-Requested-With': 'XMLHttpRequest'
            }
        }).then(function (r) {
            return r.json().catch(function () { return {}; }).then(function (data) {
                return { ok: r.ok, data: data };
            });
        }).then(function (res) {
            if (!res.ok) {
                var msg = (res.data && (res.data.error || res.data.detail)) ? (res.data.error || res.data.detail) : 'No se pudo iniciar la sincronizacion manual.';
                throw new Error(msg);
            }
            alert('Sincronizacion iniciada. El sistema va a consultar el servidor de correo y actualizar la bandeja en unos segundos.');
            setTimeout(function () {
                commMailRefreshList();
            }, 3000);
            setTimeout(function () {
                commMailRefreshList();
            }, 7000);
        }).catch(function (err) {
            alert(err.message || 'No se pudo iniciar la sincronizacion manual.');
        }).finally(function () {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = originalHtml;
            }
        });
    };

    window.commMailCompose = function (mode) {
        mode = mode || 'new';
        if (mode === 'new') {
            var composeUrl = configValue('composeUrl');
            if (typeof htmx === 'undefined') {
                window.location.href = composeUrl;
                return;
            }
            try { if (typeof window.closeModal === 'function') window.closeModal(); } catch (e0) {}
            try { if (typeof window.closeModalSecondary === 'function') window.closeModalSecondary(); } catch (e1) {}
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
    var modalEl = document.getElementById('emailComposeModalGlobal');
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

    window.commMailOpenComposeGlobal = function () {
        if (typeof bootstrap === 'undefined') return;
        cleanupOverlays(modalEl.id);
        ['emailToInputGlobal', 'emailSubjectInputGlobal', 'emailCcInputGlobal', 'emailBccInputGlobal'].forEach(function (id) {
            var el = document.getElementById(id);
            if (el) el.value = '';
        });
        var body = document.getElementById('emailBodyDivGlobal');
        if (body) body.innerHTML = '';
        var preview = document.getElementById('emailFilePreviewGlobal');
        if (preview) preview.innerHTML = '';
        var fileInput = document.getElementById('emailAttachGlobal');
        if (fileInput) fileInput.value = '';
        bootstrap.Modal.getOrCreateInstance(modalEl).show();
        try {
            var to = document.getElementById('emailToInputGlobal');
            if (to) to.focus();
        } catch (e) {}
    };

    modalEl.addEventListener('hidden.bs.modal', function () {
        setTimeout(function () { cleanupOverlays(modalEl.id); }, 0);
    });

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

    var attachInput = document.getElementById('emailAttachGlobal');
    var attachPreview = document.getElementById('emailFilePreviewGlobal');
    if (attachInput && attachPreview) {
        attachInput.addEventListener('change', function () {
            attachPreview.innerHTML = '';
            if (!this.files || !this.files.length) return;
            var ul = document.createElement('ul');
            ul.className = 'list-unstyled small mb-0';
            Array.from(this.files).forEach(function (f) {
                var li = document.createElement('li');
                li.className = 'text-muted';
                li.textContent = f.name + ' (' + (f.size ? Math.round((f.size / 1024) * 10) / 10 + ' KB' : 'Archivo') + ')';
                ul.appendChild(li);
            });
            attachPreview.appendChild(ul);
        });
    }

    var form = document.getElementById('emailFormGlobal');
    if (form) {
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            var bodyDiv = document.getElementById('emailBodyDivGlobal');
            var bodyIn = document.getElementById('emailBodyInputGlobal');
            if (bodyIn) bodyIn.value = bodyDiv ? (bodyDiv.innerHTML || '') : '';
            var btn = document.getElementById('emailSendBtnGlobal');
            if (btn) btn.disabled = true;
            fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
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
