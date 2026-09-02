(function () {
    function parseCatalog() {
        try {
            var el = document.getElementById('email-compose-recipient-catalog');
            if (!el || !el.textContent) return [];
            return JSON.parse(el.textContent);
        } catch (e) {
            return [];
        }
    }

    function contactsSearchUrl() {
        var cfg = document.getElementById('comm-mail-config');
        if (cfg && cfg.dataset.contactsSearchUrl) return cfg.dataset.contactsSearchUrl;
        var modal = document.getElementById('emailComposeModal');
        if (modal && modal.dataset.contactsEndpoint) return modal.dataset.contactsEndpoint;
        var form = document.querySelector('form[data-contacts-endpoint]');
        if (form && form.dataset.contactsEndpoint) return form.dataset.contactsEndpoint;
        return '/communications/contacts/email-search/';
    }

    var panel = null;
    var activeInput = null;
    var debTimer = null;
    var catalog = parseCatalog();
    var fetchSeq = 0;

    function ensurePanel() {
        if (panel) return panel;
        panel = document.createElement('ul');
        panel.id = 'emailRecipientSuggestList';
        panel.className = 'comm-email-recipient-suggest';
        panel.setAttribute('role', 'listbox');
        panel.setAttribute('aria-label', 'Sugerencias de destinatarios');
        document.body.appendChild(panel);
        return panel;
    }

    function hidePanel() {
        if (!panel) return;
        panel.style.display = 'none';
        panel.innerHTML = '';
    }

    function tokenAtCursor(input) {
        var v = input.value || '';
        var pos = typeof input.selectionStart === 'number' ? input.selectionStart : v.length;
        var before = v.slice(0, pos);
        var i = before.lastIndexOf(',');
        return ((i === -1 ? before : before.slice(i + 1)).trim());
    }

    function replaceActiveToken(input, insertText) {
        insertText = (insertText || '').trim();
        if (!insertText) return;
        var v = input.value || '';
        var pos = typeof input.selectionStart === 'number' ? input.selectionStart : v.length;
        var before = v.slice(0, pos);
        var after = v.slice(pos);
        var lastComma = before.lastIndexOf(',');
        var start = lastComma + 1;
        var prefix = v.slice(0, start);
        var needsSpace = prefix.length > 0 && !/\s$/.test(prefix);
        var newBefore = prefix + (needsSpace ? ' ' : '') + insertText + ', ';
        input.value = newBefore + after.replace(/^\s*,?\s*/, '');
        var np = newBefore.length;
        try { input.setSelectionRange(np, np); } catch (e) {}
    }

    function filterGroupMatches(q) {
        if (!q || q.length < 1) return [];
        var ql = q.toLowerCase();
        var out = [];
        for (var i = 0; i < catalog.length && out.length < 8; i++) {
            var it = catalog[i];
            if (it.t !== 'g') continue;
            var lg = (it.l || '').toLowerCase();
            if (lg.indexOf(ql) !== -1) {
                out.push(it);
                continue;
            }
            if (it.emails) {
                for (var j = 0; j < it.emails.length; j++) {
                    if ((it.emails[j] || '').toLowerCase().indexOf(ql) !== -1) {
                        out.push(it);
                        break;
                    }
                }
            }
        }
        return out;
    }

    function fetchContacts(q) {
        var endpoint = contactsSearchUrl();
        if (!endpoint || endpoint.startsWith('data:')) return Promise.resolve([]);
        return fetch(endpoint + '?q=' + encodeURIComponent(q || ''), {
            credentials: 'same-origin',
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        }).then(function (r) { return r.json(); })
          .then(function (data) {
              var rows = (data && data.results) ? data.results : [];
              return rows.filter(function (it) { return it && it.email; }).map(function (it) {
                  return {
                      t: 'c',
                      id: it.id,
                      l: (it.name || it.email || '').trim(),
                      e: String(it.email || '').trim()
                  };
              });
          }).catch(function () { return []; });
    }

    function positionPanel(input) {
        var el = ensurePanel();
        var r = input.getBoundingClientRect();
        el.style.position = 'fixed';
        el.style.display = 'block';
        el.style.top = (r.bottom + 4) + 'px';
        el.style.left = r.left + 'px';
        el.style.width = Math.max(r.width, 300) + 'px';
        el.style.zIndex = '11000';
    }

    function applyPick(it) {
        if (!activeInput) return;
        if (it.t === 'c') {
            replaceActiveToken(activeInput, it.e);
        } else {
            replaceActiveToken(activeInput, (it.emails || []).join(', '));
        }
        hidePanel();
        activeInput.focus();
        try {
            activeInput.dispatchEvent(new Event('input', { bubbles: true }));
        } catch (e) {}
    }

    function renderSuggest(matches) {
        var el = ensurePanel();
        el.innerHTML = '';
        if (!matches.length || !activeInput) {
            hidePanel();
            return;
        }
        positionPanel(activeInput);
        matches.forEach(function (it) {
            var li = document.createElement('li');
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.setAttribute('role', 'option');
            var span = document.createElement('span');
            span.className = 'fw-semibold';
            span.textContent = (it.t === 'g' ? '[Grupo] ' : '[Contacto] ') + (it.l || '');
            btn.appendChild(span);
            var meta = document.createElement('div');
            meta.className = 'sug-meta';
            meta.textContent = it.t === 'g' ? ((it.emails || []).length + ' direcciones') : (it.e || '');
            btn.appendChild(meta);
            btn.addEventListener('mousedown', function (ev) {
                ev.preventDefault();
                applyPick(it);
            });
            li.appendChild(btn);
            el.appendChild(li);
        });
    }

    function onInput(ev) {
        activeInput = ev.target;
        clearTimeout(debTimer);
        debTimer = setTimeout(function () {
            catalog = parseCatalog();
            var t = tokenAtCursor(activeInput);
            if (!t || t.length < 1) {
                hidePanel();
                return;
            }
            var seq = ++fetchSeq;
            var groups = filterGroupMatches(t);
            fetchContacts(t).then(function (contacts) {
                if (seq !== fetchSeq || !activeInput) return;
                var seen = Object.create(null);
                var merged = [];
                contacts.forEach(function (it) {
                    var key = (it.e || '').toLowerCase();
                    if (!key || seen[key]) return;
                    seen[key] = true;
                    merged.push(it);
                });
                groups.forEach(function (it) { merged.push(it); });
                renderSuggest(merged.slice(0, 20));
            });
        }, 200);
    }

    function bindField(inp) {
        if (!inp || inp.dataset.commRecipientSuggest) return;
        // Redactar global ya usa el buscador por API (communications_base.js)
        if (inp.dataset.commAutoBound || /Global$/i.test(inp.id || '')) return;
        inp.dataset.commRecipientSuggest = '1';
        inp.addEventListener('input', onInput);
        inp.addEventListener('focus', function (e) {
            activeInput = e.target;
            onInput(e);
        });
        inp.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') hidePanel();
        });
        inp.addEventListener('blur', function () {
            setTimeout(function () { hidePanel(); }, 320);
        });
    }

    function initRecipientSuggest() {
        catalog = parseCatalog();
        var roots = [
            document.querySelector('#conversation-detail-panel #emailComposeModal'),
            document.querySelector('body > #emailComposeModal'),
            document.getElementById('emailComposeModal'),
            document.getElementById('emailFormInline')
        ].filter(Boolean);

        roots.forEach(function (root) {
            [
                '#emailToInput',
                '#emailCcInput',
                '#emailBccInput',
                '#emailToInputInline',
                '#emailCcInputInline',
                '#emailBccInputInline'
            ].forEach(function (sel) {
                bindField(root.querySelector(sel));
            });
            root.querySelectorAll(
                'input[name="to_addresses"], input[name="cc_addresses"], input[name="bcc_addresses"]'
            ).forEach(bindField);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initRecipientSuggest);
    } else {
        initRecipientSuggest();
    }

    document.body.addEventListener('htmx:afterSwap', initRecipientSuggest);
    document.addEventListener('shown.bs.modal', function (event) {
        if (!event.target) return;
        if (event.target.id === 'emailComposeModal' || event.target.id === 'emailComposeModalGlobal') {
            initRecipientSuggest();
        }
    });
    document.addEventListener('hidden.bs.modal', function (event) {
        if (event.target && (event.target.id === 'emailComposeModal' || event.target.id === 'emailComposeModalGlobal')) {
            hidePanel();
        }
    });
})();
