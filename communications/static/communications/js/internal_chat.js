(function () {
    var form = document.getElementById('internalChatForm');
    var area = document.getElementById('internalChatMessagesArea');
    if (!form || !area) return;

    var url = form.dataset.messagesUrl || '';
    var currentUserId = parseInt(form.dataset.currentUserId || '0', 10);
    var lastInboundId = 0;
    var initialized = false;

    function getLastMetaFromRoot(rootEl) {
        if (!rootEl) return { id: 0, authorId: 0 };
        var rows = rootEl.querySelectorAll('.omni-msg-row[data-message-id]');
        var last = rows.length ? rows[rows.length - 1] : null;
        var id = last ? parseInt(last.getAttribute('data-message-id') || '0', 10) : 0;
        var authorId = last ? parseInt(last.getAttribute('data-author-id') || '0', 10) : 0;
        return {
            id: Number.isFinite(id) ? id : 0,
            authorId: Number.isFinite(authorId) ? authorId : 0
        };
    }

    function scrollToBottom() {
        area.scrollTop = area.scrollHeight;
    }

    function refresh() {
        var prevId = lastInboundId;
        fetch(url, { headers: { 'HX-Request': 'true' } })
            .then(function (r) { return r.text(); })
            .then(function (html) {
                var wrapper = document.createElement('div');
                wrapper.innerHTML = html;
                var meta = getLastMetaFromRoot(wrapper);
                area.innerHTML = html;
                scrollToBottom();

                if (!initialized) {
                    lastInboundId = meta.id;
                    initialized = true;
                    return;
                }

                if (meta.id && meta.id > prevId && meta.authorId && meta.authorId !== currentUserId) {
                    lastInboundId = meta.id;
                    if (window.commNotify && typeof window.commNotify.playDing === 'function') {
                        window.commNotify.playDing('internal');
                    }
                    return;
                }
                lastInboundId = meta.id;
            })
            .catch(function () {});
    }

    var textarea = form.querySelector('textarea[name="content"]');
    if (textarea) {
        textarea.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                form.dispatchEvent(new Event('submit'));
            }
        });
    }

    form.addEventListener('submit', function (e) {
        e.preventDefault();
        var formData = new FormData(form);
        var btn = form.querySelector('button[type="submit"]');
        var original = btn ? btn.innerHTML : '';
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        }

        fetch(form.action, {
            method: 'POST',
            body: formData,
            headers: { 'X-CSRFToken': formData.get('csrfmiddlewaretoken') || '' }
        }).then(async function (r) {
            if (!r.ok) {
                var data = await r.json().catch(function () { return {}; });
                throw new Error(data.error || 'Error al enviar');
            }
            if (textarea) textarea.value = '';
            refresh();
        }).catch(function (err) {
            alert(err.message);
        }).finally(function () {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = original;
            }
        });
    });

    refresh();
    setTimeout(scrollToBottom, 200);
    if (window.internalChatPollInterval) clearInterval(window.internalChatPollInterval);
    window.internalChatPollInterval = setInterval(refresh, 5000);
})();
