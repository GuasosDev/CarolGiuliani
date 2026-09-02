(function () {
    var AUTOSAVE_MS = 25000;

    function configEl() {
        return document.getElementById('comm-mail-config');
    }

    function cfg(name, fallback) {
        var el = configEl();
        if (!el) return fallback || '';
        return el.dataset[name] || fallback || '';
    }

    function csrfToken() {
        var m = document.cookie.match('(^|;) ?csrftoken=([^;]*)(;|$)');
        return m ? decodeURIComponent(m[2]) : '';
    }

    function saveUrl() {
        return cfg('draftSaveUrl');
    }

    function currentUrl() {
        return cfg('draftCurrentUrl');
    }

    function detailUrl(id) {
        var tpl = cfg('draftDetailTemplate');
        if (!tpl) return '';
        return String(tpl).replace('999999', String(id));
    }

    function formBodyEl(form) {
        return form.querySelector('#emailBodyDivGlobal, #emailBodyDiv, #emailBodyDivInline');
    }

    function newComposeSlot() {
        return 'new:' + Date.now() + '-' + Math.random().toString(36).slice(2, 10);
    }

    function slotKey(form, mode, convId, sourceId) {
        mode = mode || 'new';
        if (mode === 'new') {
            if (form && form.dataset.slotKey && String(form.dataset.slotKey).indexOf('new:') === 0) {
                return form.dataset.slotKey;
            }
            return newComposeSlot();
        }
        return mode + ':' + (convId || '0') + ':' + (sourceId || '0');
    }

    function currentMode(form) {
        return (form && form.dataset.composeMode) || 'new';
    }

    function convIdOf(form) {
        var el = form.querySelector('[name="conversation_id"]');
        return el ? String(el.value || '').trim() : (form.getAttribute('data-conversation-id') || '').trim();
    }

    function sourceIdOf(form) {
        var el = form.querySelector('[name="source_email_message_id"]');
        if (el && String(el.value || '').trim()) return String(el.value).trim();
        return (form.getAttribute('data-forward-email-message-id') || '').trim();
    }

    function collect(form) {
        var mode = currentMode(form);
        var bodyEl = formBodyEl(form);
        var sig = form.querySelector('input[name="include_signature"][type="checkbox"]');
        var toEl = form.querySelector('[name="to_addresses"]');
        var ccEl = form.querySelector('[name="cc_addresses"]');
        var bccEl = form.querySelector('[name="bcc_addresses"]');
        var subEl = form.querySelector('[name="subject"]');
        var convId = convIdOf(form);
        var sourceId = sourceIdOf(form);
        var key = slotKey(form, mode, convId, sourceId);
        form.dataset.slotKey = key;
        return {
            compose_mode: mode,
            slot_key: key,
            conversation_id: convId,
            source_email_message_id: sourceId,
            to_addresses: toEl ? toEl.value : '',
            cc_addresses: ccEl ? ccEl.value : '',
            bcc_addresses: bccEl ? bccEl.value : '',
            subject: subEl ? subEl.value : '',
            html_body: bodyEl ? (bodyEl.innerHTML || '') : '',
            include_signature: (sig && sig.checked) ? '1' : '0'
        };
    }

    function syncAddrRows(form) {
        form.querySelectorAll('[data-comm-email-row]').forEach(function (row) {
            var input = row.querySelector('input');
            var type = row.dataset.commEmailRow;
            var toggle = form.querySelector('[data-comm-email-toggle="' + type + '"]');
            var has = !!(input && String(input.value || '').trim());
            row.classList.toggle('d-none', !has);
            if (toggle) toggle.classList.toggle('d-none', has);
        });
    }

    function applyDraft(form, draft, modalEl) {
        if (!form || !draft) return;
        var toEl = form.querySelector('[name="to_addresses"]');
        var ccEl = form.querySelector('[name="cc_addresses"]');
        var bccEl = form.querySelector('[name="bcc_addresses"]');
        var subEl = form.querySelector('[name="subject"]');
        var bodyEl = formBodyEl(form);
        var convEl = form.querySelector('[name="conversation_id"]');
        var srcEl = form.querySelector('[name="source_email_message_id"]');
        var sig = form.querySelector('input[name="include_signature"][type="checkbox"]');
        if (toEl) toEl.value = draft.to_addresses || '';
        if (ccEl) ccEl.value = draft.cc_addresses || '';
        if (bccEl) bccEl.value = draft.bcc_addresses || '';
        if (subEl) subEl.value = draft.subject || '';
        if (bodyEl) bodyEl.innerHTML = draft.html_body || '';
        if (convEl && draft.conversation_id) {
            convEl.setAttribute('name', 'conversation_id');
            convEl.value = String(draft.conversation_id);
        }
        if (srcEl && draft.source_email_message_id) {
            srcEl.value = String(draft.source_email_message_id);
        }
        if (sig) sig.checked = !!draft.include_signature;
        form.dataset.draftId = String(draft.id || '');
        form.dataset.composeMode = draft.compose_mode || form.dataset.composeMode || 'new';
        if (draft.slot_key) form.dataset.slotKey = draft.slot_key;
        syncAddrRows(form);
        if (typeof window.commSyncSignaturePreviews === 'function') {
            window.commSyncSignaturePreviews(modalEl || form);
        }
        var title = (modalEl || document).querySelector('#emailComposeModalGlobalLabel, #emailComposeModalLabel');
        if (title) {
            var labels = {
                'new': ['fas fa-pen', 'Redactar correo'],
                'reply': ['fas fa-reply', 'Responder'],
                'reply-all': ['fas fa-reply-all', 'Responder a todos'],
                'forward': ['fas fa-share', 'Reenviar correo']
            };
            var meta = labels[draft.compose_mode] || labels.new;
            title.innerHTML = '<i class="' + meta[0] + ' me-2 text-primary"></i>' + meta[1];
        }
    }

    function markDirty(form) {
        if (!form || form.dataset.commDraftSending === '1') return;
        form.dataset.commDraftDirty = '1';
    }

    function syncDraftsCount(data, opts) {
        opts = opts || {};
        if (!data || data.drafts_count == null) return;
        var n = parseInt(data.drafts_count, 10);
        if (isNaN(n)) return;
        var els = document.querySelectorAll('[data-comm-drafts-count]');
        var prev = els.length ? parseInt((els[0].textContent || '').trim(), 10) : NaN;
        els.forEach(function (el) { el.textContent = String(n); });
        var onDrafts = /(?:\?|&)folder=drafts(?:&|$)/.test(window.location.search || '');
        if (onDrafts && typeof window.commMailRefreshList === 'function' && (opts.refreshList || prev !== n)) {
            window.commMailRefreshList();
        }
    }

    function updateDeleteButtonVisibility(form) {
        if (!form) return;
        var modal = form.closest('.modal');
        if (!modal) {
            modal = document.getElementById('emailComposeModalGlobal');
        }
        if (!modal) return;
        var deleteBtn = modal.querySelector('.comm-draft-delete-btn');
        if (!deleteBtn) return;
        var hasDraftId = !!(form.dataset.draftId && String(form.dataset.draftId).trim());
        if (hasDraftId) {
            deleteBtn.classList.remove('d-none');
        } else {
            deleteBtn.classList.add('d-none');
        }
    }

    function saveDraft(form, opts) {
        opts = opts || {};
        if (!form || !saveUrl()) return Promise.resolve();
        if (form.dataset.commDraftSending === '1' && !opts.forceDiscardEmpty) return Promise.resolve();
        if (form.dataset.commDraftDirty !== '1' && !opts.force) return Promise.resolve();
        var payload = collect(form);
        var fd = new FormData();
        Object.keys(payload).forEach(function (k) {
            fd.append(k, payload[k] == null ? '' : payload[k]);
        });
        return fetch(saveUrl(), {
            method: 'POST',
            body: fd,
            credentials: 'same-origin',
            keepalive: !!opts.keepalive,
            headers: { 'X-CSRFToken': csrfToken(), 'X-Requested-With': 'XMLHttpRequest' }
        }).then(function (r) { return r.json().catch(function () { return {}; }); })
          .then(function (data) {
              if (data && data.id) form.dataset.draftId = String(data.id);
              if (data && data.deleted) form.dataset.draftId = '';
              form.dataset.commDraftDirty = '0';
              syncDraftsCount(data);
              updateDeleteButtonVisibility(form);
              return data;
          }).catch(function () { return null; });
    }

    function discardDraft(form) {
        if (!form) return Promise.resolve();
        form.dataset.commDraftSending = '1';
        form.dataset.commDraftDirty = '0';
        var id = form.dataset.draftId;
        var url = id ? detailUrl(id) : '';
        var p;
        if (id && url) {
            var fd = new FormData();
            fd.append('action', 'discard');
            p = fetch(url, {
                method: 'POST',
                body: fd,
                credentials: 'same-origin',
                headers: { 'X-CSRFToken': csrfToken(), 'X-Requested-With': 'XMLHttpRequest' }
            }).then(function (r) { return r.json().catch(function () { return {}; }); })
              .then(function (data) {
                  syncDraftsCount(data, { refreshList: true });
                  return data;
              }).catch(function () { return null; });
        } else {
            p = saveDraft(form, { force: true, forceDiscardEmpty: true, keepalive: true });
        }
        return p.finally(function () {
            form.dataset.draftId = '';
        });
    }

    function restoreCurrent(form) {
        if (!form || !currentUrl()) return Promise.resolve(null);
        var mode = currentMode(form);
        var convId = convIdOf(form);
        var sourceId = sourceIdOf(form);
        var key = form.dataset.slotKey || slotKey(form, mode, convId, sourceId);
        var url = currentUrl() + '?compose_mode=' + encodeURIComponent(mode)
            + '&slot_key=' + encodeURIComponent(key)
            + '&conversation_id=' + encodeURIComponent(convId || '')
            + '&source_email_message_id=' + encodeURIComponent(sourceId || '');
        return fetch(url, {
            credentials: 'same-origin',
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        }).then(function (r) { return r.json(); })
          .then(function (data) { return (data && data.draft) ? data.draft : null; })
          .catch(function () { return null; });
    }

    function bindForm(form, modalEl) {
        if (!form || form.dataset.commDraftBound === '1') return;
        form.dataset.commDraftBound = '1';
        form.dataset.commDraftDirty = '0';
        function onDirty() { markDirty(form); }
        form.querySelectorAll('input[name="to_addresses"], input[name="cc_addresses"], input[name="bcc_addresses"], input[name="subject"], input[name="include_signature"]').forEach(function (el) {
            el.addEventListener('input', onDirty);
            el.addEventListener('change', onDirty);
        });
        var bodyEl = formBodyEl(form);
        if (bodyEl) {
            bodyEl.addEventListener('input', onDirty);
            bodyEl.addEventListener('keyup', onDirty);
        }
        form._commDraftTimer = setInterval(function () {
            if (form.dataset.commDraftDirty === '1') saveDraft(form);
        }, AUTOSAVE_MS);
        var modal = modalEl || form.closest('.modal');
        if (modal && !modal.dataset.commDraftHideBound) {
            modal.dataset.commDraftHideBound = '1';
            modal.addEventListener('hide.bs.modal', function () {
                var f = modal.querySelector('form.comm-email-compose-form') || form;
                if (f.dataset.commDraftSending === '1') return;
                saveDraft(f, { keepalive: true });
            });
        }
        updateDeleteButtonVisibility(form);
    }

    function prepareOpen(form, mode, modalEl) {
        if (!form) return Promise.resolve();
        form.dataset.composeMode = mode || 'new';
        form.dataset.commDraftSending = '0';
        form.dataset.commDraftDirty = '0';
        bindForm(form, modalEl);
        if ((mode || 'new') === 'new') {
            form.dataset.slotKey = newComposeSlot();
            form.dataset.draftId = '';
            updateDeleteButtonVisibility(form);
            return Promise.resolve(null);
        }
        form.dataset.slotKey = slotKey(form, mode, convIdOf(form), sourceIdOf(form));
        return restoreCurrent(form).then(function (draft) {
            if (draft) applyDraft(form, draft, modalEl);
            form.dataset.commDraftDirty = '0';
            updateDeleteButtonVisibility(form);
            return draft;
        });
    }

    window.commEmailDraftBindForm = bindForm;
    window.commEmailDraftPrepare = prepareOpen;
    window.commEmailDraftSave = saveDraft;
    window.commEmailDraftDiscard = discardDraft;
    
    window.commEmailDraftDiscardAndClose = function (form) {
        if (!form) return;
        discardDraft(form).then(function () {
            var modal = form.closest('.modal');
            if (!modal) {
                modal = document.getElementById('emailComposeModalGlobal');
            }
            if (modal && typeof bootstrap !== 'undefined') {
                var inst = bootstrap.Modal.getInstance(modal);
                if (inst) inst.hide();
            }
        }).catch(function () {
            alert('Error al eliminar el borrador.');
        });
    };
    
    window.commEmailDraftMarkSending = function (form) {
        if (!form) return;
        form.dataset.commDraftSending = '1';
        form.dataset.commDraftDirty = '0';
    };

    window.commOpenEmailDraft = function (id) {
        if (!id) return;
        var url = detailUrl(id);
        if (!url) {
            alert('No se pudo determinar la URL del borrador.');
            return;
        }
        fetch(url, {
            credentials: 'same-origin',
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        }).then(function (r) { return r.json(); })
          .then(function (data) {
              var draft = data && data.draft;
              if (!draft) return;
              var modal = document.getElementById('emailComposeModalGlobal');
              var form = document.getElementById('emailFormGlobal');
              if (!modal || !form || typeof bootstrap === 'undefined') {
                  alert('No se pudo abrir el borrador.');
                  return;
              }
              if (typeof window.commMailOpenComposeGlobal === 'function') {
                  window.__commSkipDraftRestore = true;
                  window.commMailOpenComposeGlobal(); // <--- CORREGIDO AQUÍ
                  window.__commSkipDraftRestore = false;
              }
              form.dataset.composeMode = draft.compose_mode || 'new';
              applyDraft(form, draft, modal);
              form.dataset.commDraftDirty = '0';
              bindForm(form, modal);
              var deleteBtn = modal.querySelector('.comm-draft-delete-btn');
              if (deleteBtn && form.dataset.draftId && String(form.dataset.draftId).trim()) {
                  deleteBtn.classList.remove('d-none');
              }
          }).catch(function () {
              alert('No se pudo abrir el borrador.');
          });
    };

    document.addEventListener('visibilitychange', function () {
        if (document.visibilityState !== 'hidden') return;
        document.querySelectorAll('form.comm-email-compose-form').forEach(function (form) {
            saveDraft(form, { keepalive: true });
        });
    });
    window.addEventListener('pagehide', function () {
        document.querySelectorAll('form.comm-email-compose-form').forEach(function (form) {
            saveDraft(form, { keepalive: true });
        });
    });

    document.body.addEventListener('htmx:afterSwap', function () {
        var modal = document.getElementById('emailComposeModal');
        if (modal) {
            var form = modal.querySelector('#emailForm');
            if (form) bindForm(form, modal);
        }
    });

    var globalForm = document.getElementById('emailFormGlobal');
    var globalModal = document.getElementById('emailComposeModalGlobal');
    if (globalForm) bindForm(globalForm, globalModal);
})();