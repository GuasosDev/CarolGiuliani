(function () {
    var form = document.getElementById('internalChatForm');
    var area = document.getElementById('internalChatMessagesArea');
    if (!form || !area) return;

    var url = form.dataset.messagesUrl || '';
    var currentUserId = parseInt(form.dataset.currentUserId || '0', 10);
    var lastInboundId = 0;
    var initialized = false;
    var textarea = form.querySelector('textarea[name="content"]');
    var suggestions = document.getElementById('internalChatMentionSuggestions');
    var mentionUsers = [];
    var filteredMentionUsers = [];
    var activeMentionIndex = 0;
    var mentionStart = -1;

    mentionUsers = JSON.parse(
        document.getElementById('internalChatMentionUsers').textContent
    );

    function hideMentionSuggestions() {
        if (!suggestions) return;
        suggestions.hidden = true;
        suggestions.replaceChildren();
        filteredMentionUsers = [];
        activeMentionIndex = 0;
        mentionStart = -1;
    }

    function insertMention(user) {
        if (!textarea || mentionStart < 0) return;
        var cursor = textarea.selectionStart;
        var before = textarea.value.slice(0, mentionStart);
        var after = textarea.value.slice(cursor);
        var inserted = '@' + user.username + ' ';
        textarea.value = before + inserted + after;
        var nextCursor = before.length + inserted.length;
        textarea.focus();
        textarea.setSelectionRange(nextCursor, nextCursor);
        hideMentionSuggestions();
    }

    function renderMentionSuggestions(users) {
        suggestions.replaceChildren();
        users.forEach(function (user, index) {
            var option = document.createElement('button');
            option.type = 'button';
            option.className = 'internal-chat-mention-option' +
                (index === activeMentionIndex ? ' active' : '');
            option.setAttribute('role', 'option');
            option.setAttribute('aria-selected', index === activeMentionIndex ? 'true' : 'false');

            var avatar = document.createElement('span');
            avatar.className = 'internal-chat-mention-avatar';
            avatar.textContent = user.initials;
            var name = document.createElement('span');
            name.textContent = user.name;
            var username = document.createElement('small');
            username.className = 'text-muted ms-auto';
            username.textContent = '@' + user.username;
            option.append(avatar, name, username);

            option.addEventListener('mousedown', function (event) {
                event.preventDefault();
                insertMention(user);
            });
            suggestions.appendChild(option);
        });
        suggestions.hidden = users.length === 0;
    }

    function updateMentionSuggestions() {
        if (!textarea || !suggestions) return;
        var cursor = textarea.selectionStart;
        var beforeCursor = textarea.value.slice(0, cursor);
        var match = beforeCursor.match(/(^|[^\p{L}\p{N}_@])@([\p{L}\p{N}_@.+ -]*)$/u);
        if (!match) {
            hideMentionSuggestions();
            return;
        }

        mentionStart = cursor - match[2].length - 1;
        var query = match[2].trim().toLocaleLowerCase();
        filteredMentionUsers = mentionUsers.filter(function (user) {
            return user.username.toLocaleLowerCase().includes(query) ||
                user.name.toLocaleLowerCase().includes(query);
        }).slice(0, 8);
        activeMentionIndex = 0;
        renderMentionSuggestions(filteredMentionUsers);
    }

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

    if (textarea) {
        textarea.addEventListener('input', updateMentionSuggestions);
        textarea.addEventListener('click', updateMentionSuggestions);
        textarea.addEventListener('keyup', function (event) {
            if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
                updateMentionSuggestions();
            }
        });
        textarea.addEventListener('keydown', function (e) {
            if (!suggestions.hidden && filteredMentionUsers.length) {
                if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                    e.preventDefault();
                    var direction = e.key === 'ArrowDown' ? 1 : -1;
                    activeMentionIndex = (
                        activeMentionIndex + direction + filteredMentionUsers.length
                    ) % filteredMentionUsers.length;
                    renderMentionSuggestions(filteredMentionUsers);
                    return;
                }
                if (e.key === 'Enter' || e.key === 'Tab') {
                    e.preventDefault();
                    insertMention(filteredMentionUsers[activeMentionIndex]);
                    return;
                }
                if (e.key === 'Escape') {
                    e.preventDefault();
                    hideMentionSuggestions();
                    return;
                }
            }
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
            hideMentionSuggestions();
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
