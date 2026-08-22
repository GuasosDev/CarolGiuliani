(function () {
    if (window.__commConversationContentInit) {
        if (typeof window.__commInitConversationContent === 'function') {
            window.__commInitConversationContent();
        }
        return;
    }
    window.__commConversationContentInit = true;

    function getConfig() {
        return document.getElementById('conversationContentConfig');
    }

    function cfg(name) {
        var el = getConfig();
        return el ? (el.dataset[name] || '') : '';
    }

    function isReady() {
        return Boolean(getConfig());
    }

    function ensureBootstrapModalRoot(modalEl) {
        if (!modalEl) return null;
        if (modalEl.parentElement !== document.body) {
            document.body.appendChild(modalEl);
        }
        return modalEl;
    }

    function getEmailComposeModal() {
        // Preferir el modal visible (puede estar en body); evita adjuntar en un modal fantasma del panel
        var shown = document.querySelector('#emailComposeModal.show');
        if (shown) return shown;
        var onBody = document.querySelector('body > #emailComposeModal');
        if (onBody) return onBody;
        var panel = document.getElementById('conversation-detail-panel');
        if (panel) {
            var inPanel = panel.querySelector('#emailComposeModal');
            if (inPanel) return inPanel;
        }
        return document.getElementById('emailComposeModal');
    }

    function cleanupOrphanedEmailComposeModals() {
        var panel = document.getElementById('conversation-detail-panel');
        var freshInPanel = panel && panel.querySelector('#emailComposeModal');
        if (!freshInPanel) return;
        document.querySelectorAll('body > #emailComposeModal').forEach(function (el) {
            try {
                if (typeof bootstrap !== 'undefined') {
                    var inst = bootstrap.Modal.getInstance(el);
                    if (inst) inst.dispose();
                }
            } catch (e) {}
            el.remove();
        });
    }

    function clearEmailComposeFields(modalEl) {
        if (!modalEl) return;
        ['[name="to_addresses"]', '[name="cc_addresses"]', '[name="bcc_addresses"]', '[name="subject"]'].forEach(function (sel) {
            var el = modalEl.querySelector(sel);
            if (el) el.value = '';
        });
        var body = modalEl.querySelector('#emailBodyDiv');
        if (body) body.innerHTML = '';
        var bodyIn = modalEl.querySelector('#emailBodyInput');
        if (bodyIn) bodyIn.value = '';
        var preview = modalEl.querySelector('#emailFilePreview');
        if (preview) preview.innerHTML = '';
        var fileIn = modalEl.querySelector('#imageInputEmail');
        if (fileIn) clearEmailAttachInput(fileIn);
        var srcIn = modalEl.querySelector('#emailSourceEmailMessageIdInput');
        if (srcIn) srcIn.value = '';
    }

    /** Acumula adjuntos en input._commFiles (no se pierde al vaciar el input nativo). */
    var emailAttachStores = new WeakMap();

    function getReplyAttachFiles(input) {
        if (!input) return [];
        if (!Array.isArray(input._commFiles)) input._commFiles = [];
        return input._commFiles;
    }

    function setReplyAttachFiles(input, files, formContext) {
        if (!input) return;
        input._commFiles = dedupeFiles(files || []);
        var next = new DataTransfer();
        input._commFiles.forEach(function (f) {
            try { next.items.add(f); } catch (e) {}
        });
        emailAttachStores.set(input, next);
        displayEmailFilePreview(input._commFiles, formContext || input.closest('form') || getEmailComposeModal());
    }

    function clearEmailAttachInput(input) {
        if (!input) return;
        input._commFiles = [];
        emailAttachStores.set(input, new DataTransfer());
        try { input.value = ''; } catch (e) {}
    }

    function fileKey(f) {
        return [f.name || '', f.size || 0].join('|');
    }

    function dedupeFiles(files) {
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

    function appendEmailFiles(input, fileList, formContext) {
        if (!input || !fileList || !fileList.length) return;
        var prev = getReplyAttachFiles(input);
        setReplyAttachFiles(input, prev.concat(Array.from(fileList)), formContext);
    }

    function commitEmailAttachFiles(input, formContext) {
        if (!input) return;
        setReplyAttachFiles(input, getReplyAttachFiles(input), formContext);
        try { input.value = ''; } catch (e) {}
    }

    /** Justo antes de enviar: volcar _commFiles al input para FormData. */
    function flushEmailAttachToInput(input) {
        if (!input) return;
        var files = dedupeFiles(getReplyAttachFiles(input));
        input._commFiles = files;
        var next = new DataTransfer();
        files.forEach(function (f) {
            try { next.items.add(f); } catch (e) {}
        });
        emailAttachStores.set(input, next);
        try {
            input.files = next.files;
        } catch (e) {}
    }

    function filesFromClipboardData(clipboardData) {
        var out = [];
        if (!clipboardData) return out;
        if (clipboardData.files && clipboardData.files.length) {
            Array.from(clipboardData.files).forEach(function (f) { out.push(f); });
            return out;
        }
        var items = clipboardData.items;
        if (!items) return out;
        for (var i = 0; i < items.length; i++) {
            var item = items[i];
            if (item.kind !== 'file') continue;
            var blob = item.getAsFile();
            if (!blob) continue;
            var name = blob.name || ('pegado_' + Date.now() + ((blob.type || '').indexOf('png') !== -1 ? '.png' : ''));
            out.push(new File([blob], name, { type: blob.type || 'application/octet-stream' }));
        }
        return out;
    }

    function isFileDragEvent(e) {
        var dt = e && e.dataTransfer;
        if (!dt || !dt.types) return false;
        for (var i = 0; i < dt.types.length; i++) {
            if (dt.types[i] === 'Files') return true;
        }
        return false;
    }

    var emailComposeDropGuardDepth = 0;
    var lastEmailDropTs = 0;
    function consumeEmailDropOnce() {
        var now = Date.now();
        if (now - lastEmailDropTs < 200) return false;
        lastEmailDropTs = now;
        return true;
    }
    function emailComposeDropGuard(e) {
        if (!isFileDragEvent(e)) return;
        e.preventDefault();
        if (e.type !== 'drop') return;
        var modal = getEmailComposeModal();
        if (!modal || !modal.classList.contains('show')) return;
        if (!consumeEmailDropOnce()) return;
        var input = modal.querySelector('#imageInputEmail');
        if (input && e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
            appendEmailFiles(input, e.dataTransfer.files, modal);
        }
        var content = modal.querySelector('.modal-content');
        if (content) content.classList.remove('comm-compose-drop-active');
    }
    function enableEmailComposeDropGuard() {
        emailComposeDropGuardDepth += 1;
        if (emailComposeDropGuardDepth !== 1) return;
        document.addEventListener('dragover', emailComposeDropGuard, false);
        document.addEventListener('drop', emailComposeDropGuard, false);
    }
    function disableEmailComposeDropGuard() {
        emailComposeDropGuardDepth = Math.max(0, emailComposeDropGuardDepth - 1);
        if (emailComposeDropGuardDepth > 0) return;
        document.removeEventListener('dragover', emailComposeDropGuard, false);
        document.removeEventListener('drop', emailComposeDropGuard, false);
    }

    function bindEmailDropAndPaste(rootEl, fileInput, formContext) {
        if (!rootEl || !fileInput || rootEl.dataset.commDropBound) return;
        rootEl.dataset.commDropBound = '1';
        var dragDepth = 0;
        var dropTarget = rootEl.querySelector('.modal-content') || rootEl;

        dropTarget.addEventListener('dragenter', function (e) {
            if (!isFileDragEvent(e)) return;
            e.preventDefault();
            e.stopPropagation();
            dragDepth += 1;
            dropTarget.classList.add('comm-compose-drop-active');
        });
        dropTarget.addEventListener('dragleave', function (e) {
            if (!isFileDragEvent(e)) return;
            e.preventDefault();
            dragDepth = Math.max(0, dragDepth - 1);
            if (dragDepth === 0) dropTarget.classList.remove('comm-compose-drop-active');
        });
        dropTarget.addEventListener('dragover', function (e) {
            if (!isFileDragEvent(e)) return;
            e.preventDefault();
            e.stopPropagation();
            if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
        });
        dropTarget.addEventListener('drop', function (e) {
            if (!isFileDragEvent(e) && !(e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length)) return;
            e.preventDefault();
            e.stopPropagation();
            dragDepth = 0;
            dropTarget.classList.remove('comm-compose-drop-active');
            if (!consumeEmailDropOnce()) return;
            if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
                appendEmailFiles(fileInput, e.dataTransfer.files, formContext);
            }
        });

        if (rootEl.classList && rootEl.classList.contains('modal')) {
            rootEl.addEventListener('shown.bs.modal', enableEmailComposeDropGuard);
            rootEl.addEventListener('hidden.bs.modal', function () {
                disableEmailComposeDropGuard();
                dropTarget.classList.remove('comm-compose-drop-active');
            });
            if (rootEl.classList.contains('show')) enableEmailComposeDropGuard();
        }

        var bodyDiv = rootEl.querySelector('#emailBodyDiv, #emailBodyDivInline');
        if (bodyDiv && !bodyDiv.dataset.commPasteFilesBound) {
            bodyDiv.dataset.commPasteFilesBound = '1';
            bodyDiv.addEventListener('paste', function (e) {
                var files = filesFromClipboardData(e.clipboardData || (e.originalEvent && e.originalEvent.clipboardData));
                if (!files.length) return;
                e.preventDefault();
                appendEmailFiles(fileInput, files, formContext);
            });
        }
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        if (!bytes) return '';
        var k = 1024;
        var sizes = ['Bytes', 'KB', 'MB', 'GB'];
        var i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function getDetailsOpenState(container) {
        var state = {};
        if (!container) return state;
        container.querySelectorAll('details').forEach(function (details, index) {
            var key = details.id || ('details-' + index);
            state[key] = details.hasAttribute('open');
        });
        return state;
    }

    function restoreDetailsOpenState(container, state) {
        if (!container) return;
        container.querySelectorAll('details').forEach(function (details, index) {
            var key = details.id || ('details-' + index);
            if (state[key]) {
                details.setAttribute('open', '');
            }
        });
    }

    function updateMoreMessagesIndicator() {
        var chatArea = document.getElementById('chatMessagesArea');
        var indicator = document.getElementById('moreMessagesIndicator');
        if (!chatArea || !indicator) return;
        var atBottom = chatArea.scrollHeight - chatArea.scrollTop <= chatArea.clientHeight + 40;
        indicator.classList.toggle('d-none', atBottom);
    }

    function scrollChatToBottom() {
        var chatArea = document.getElementById('chatMessagesArea');
        if (!chatArea) return;
        chatArea.scrollTop = chatArea.scrollHeight;
        requestAnimationFrame(updateMoreMessagesIndicator);
        setTimeout(updateMoreMessagesIndicator, 50);
    }

    function refreshMessages() {
        var messagesArea = document.getElementById('chatMessagesArea');
        if (!messagesArea) return;
        var openState = getDetailsOpenState(messagesArea);
        var previousScrollTop = messagesArea.scrollTop;
        var wasAtBottom = messagesArea.scrollHeight - messagesArea.scrollTop <= messagesArea.clientHeight + 100;
        var url = cfg('conversationDetailUrl');
        if (!url) return;

        fetch(url, { headers: { 'HX-Request': 'true' } })
            .then(function (response) { return response.text(); })
            .then(function (html) {
                var parser = new DOMParser();
                var doc = parser.parseFromString(html, 'text/html');
                var newMessages = doc.getElementById('chatMessagesArea');
                if (!newMessages) return;
                messagesArea.innerHTML = newMessages.innerHTML;
                restoreDetailsOpenState(messagesArea, openState);
                if (wasAtBottom) {
                    messagesArea.scrollTop = messagesArea.scrollHeight;
                } else {
                    messagesArea.scrollTop = Math.min(previousScrollTop, messagesArea.scrollHeight - messagesArea.clientHeight);
                }
                requestAnimationFrame(updateMoreMessagesIndicator);
                setTimeout(updateMoreMessagesIndicator, 50);
            })
            .catch(function (err) { console.error('Error refreshing messages:', err); });
    }

    window.refreshMessages = refreshMessages;

    function setForwardPreviewVisible(modalEl, visible) {
        if (!modalEl) return;
        // Compat: ya no hay preview separado; limpiar restos si existieran.
        var preview = modalEl.querySelector('#emailForwardPreview');
        if (preview) preview.classList.add('d-none');
        var writeHint = modalEl.querySelector('#emailComposeWriteHint');
        if (writeHint) writeHint.classList.add('d-none');
        modalEl.classList.remove('comm-compose-forward-mode');
        var body = modalEl.querySelector('#emailBodyDiv');
        if (body) {
            body.setAttribute(
                'data-placeholder',
                'Escribe el contenido del correo... (arrastrá archivos o pegá con Ctrl+V)'
            );
        }
    }

    function getReplyQuoteHtml(modalEl) {
        if (!modalEl) return '';
        var tpl = modalEl.querySelector('#emailReplyQuoteTemplate');
        if (!tpl) return '';
        return tpl.innerHTML || '';
    }

    function getForwardBodyHtml(modalEl) {
        if (!modalEl) return '';
        var tpl = modalEl.querySelector('#emailForwardBodyTemplate');
        if (!tpl) return '';
        return tpl.innerHTML || '';
    }

    window.commMailOpenCompose = function (mode, options) {
        var modalEl = getEmailComposeModal();
        if (!modalEl || typeof bootstrap === 'undefined') return;
        ensureBootstrapModalRoot(modalEl);
        cleanupOverlays(modalEl.id);
        options = options || {};
        mode = mode || 'reply';
        var form = modalEl.querySelector('#emailForm');
        var to = modalEl.querySelector('#emailToInput');
        var subj = modalEl.querySelector('#emailSubjectInput');
        var body = modalEl.querySelector('#emailBodyDiv');
        var convInput = modalEl.querySelector('#emailConversationIdInput');
        var title = modalEl.querySelector('#emailComposeModalLabel');
        var ccIn = modalEl.querySelector('#emailCcInput');
        var bccIn = modalEl.querySelector('#emailBccInput');
        var fileIn = modalEl.querySelector('#imageInputEmail');
        if (fileIn) clearEmailAttachInput(fileIn);
        var previewEl = modalEl.querySelector('#emailFilePreview');
        if (previewEl) previewEl.innerHTML = '';
        var replyTo = form && form.getAttribute('data-reply-to') ? form.getAttribute('data-reply-to').trim() : '';
        var replySubject = form && form.getAttribute('data-reply-subject') ? form.getAttribute('data-reply-subject').trim() : '';
        var replyCc = form && form.getAttribute('data-reply-cc') ? form.getAttribute('data-reply-cc').trim() : '';
        var convIdDefault = form && form.getAttribute('data-conversation-id') ? String(form.getAttribute('data-conversation-id')).trim() : '';

        function setTitle(iconClass, text) {
            if (!title) return;
            title.innerHTML = '<i class="' + iconClass + ' me-2 text-primary"></i>' + text;
        }

        if (mode === 'new') {
            if (to) to.value = Object.prototype.hasOwnProperty.call(options, 'initialTo') ? String(options.initialTo) : '';
            if (subj) subj.value = '';
            if (body) body.innerHTML = '';
            if (convInput) {
                convInput.value = '';
                convInput.removeAttribute('name');
            }
            var srcInNew = modalEl.querySelector('#emailSourceEmailMessageIdInput');
            if (srcInNew) srcInNew.value = '';
            if (ccIn) ccIn.value = '';
            if (bccIn) bccIn.value = '';
            setForwardPreviewVisible(modalEl, false);
            setTitle('fas fa-pen', 'Redactar correo');
        } else if (mode === 'forward') {
            if (to) to.value = '';
            if (subj) subj.value = replySubject ? ('Fwd: ' + replySubject) : 'Fwd: ';
            if (body) body.innerHTML = '<p><br></p>' + getForwardBodyHtml(modalEl);
            if (convInput) {
                convInput.value = '';
                convInput.removeAttribute('name');
            }
            var srcId = form && form.getAttribute('data-forward-email-message-id') ? String(form.getAttribute('data-forward-email-message-id')).trim() : '';
            var srcIn = modalEl.querySelector('#emailSourceEmailMessageIdInput');
            if (srcIn) srcIn.value = srcId;
            if (ccIn) ccIn.value = '';
            if (bccIn) bccIn.value = '';
            setForwardPreviewVisible(modalEl, false);
            setTitle('fas fa-share', 'Reenviar correo');
        } else if (mode === 'reply-all') {
            if (to) to.value = replyTo;
            if (subj) subj.value = replySubject ? ('Re: ' + replySubject) : 'Re: ';
            if (body) body.innerHTML = '<p><br></p>' + getReplyQuoteHtml(modalEl);
            if (convInput) {
                convInput.setAttribute('name', 'conversation_id');
                convInput.value = convIdDefault;
            }
            var srcInAll = modalEl.querySelector('#emailSourceEmailMessageIdInput');
            if (srcInAll) srcInAll.value = '';
            if (ccIn) {
                ccIn.value = replyCc;
                var ccRowAll = ccIn.closest('[data-comm-email-row="cc"]');
                var ccToggleAll = form && form.querySelector('[data-comm-email-toggle="cc"]');
                if (replyCc) {
                    if (ccRowAll) ccRowAll.classList.remove('d-none');
                    if (ccToggleAll) ccToggleAll.classList.add('d-none');
                } else {
                    if (ccRowAll) ccRowAll.classList.add('d-none');
                    if (ccToggleAll) ccToggleAll.classList.remove('d-none');
                }
            }
            if (bccIn) bccIn.value = '';
            setForwardPreviewVisible(modalEl, false);
            setTitle('fas fa-reply-all', 'Responder a todos');
        } else {
            if (to) to.value = replyTo;
            if (subj) subj.value = replySubject ? ('Re: ' + replySubject) : 'Re: ';
            if (body) body.innerHTML = '<p><br></p>' + getReplyQuoteHtml(modalEl);
            if (convInput) {
                convInput.setAttribute('name', 'conversation_id');
                convInput.value = convIdDefault;
            }
            var srcInReply = modalEl.querySelector('#emailSourceEmailMessageIdInput');
            if (srcInReply) srcInReply.value = '';
            if (ccIn) {
                ccIn.value = '';
                var ccRowReply = ccIn.closest('[data-comm-email-row="cc"]');
                var ccToggleReply = form && form.querySelector('[data-comm-email-toggle="cc"]');
                if (ccRowReply) ccRowReply.classList.add('d-none');
                if (ccToggleReply) ccToggleReply.classList.remove('d-none');
            }
            if (bccIn) bccIn.value = '';
            setForwardPreviewVisible(modalEl, false);
            setTitle('fas fa-reply', 'Responder');
        }
        modalEl.setAttribute('data-bs-backdrop', 'static');
        modalEl.setAttribute('data-bs-keyboard', 'false');
        var existingInst = bootstrap.Modal.getInstance(modalEl);
        if (existingInst) {
            try { existingInst.dispose(); } catch (eDisp) {}
        }
        var modalInst = new bootstrap.Modal(modalEl, { backdrop: 'static', keyboard: false });
        modalEl.addEventListener('shown.bs.modal', function onShownComposeFocus() {
            modalEl.removeEventListener('shown.bs.modal', onShownComposeFocus);
            if ((mode === 'forward' || mode === 'reply' || mode === 'reply-all') && body) {
                try {
                    body.focus();
                    var range = document.createRange();
                    var sel = window.getSelection();
                    range.setStart(body, 0);
                    range.collapse(true);
                    sel.removeAllRanges();
                    sel.addRange(range);
                } catch (eFocus) {}
            }
        });
        function finishOpenCompose() {
            modalInst.show();
            if (typeof window.commSyncSignaturePreviews === 'function') {
                window.commSyncSignaturePreviews(modalEl);
            }
        }
        if (form) {
            form.dataset.composeMode = mode;
            form.dataset.commDraftSending = '0';
        }
        if (form && typeof window.commEmailDraftPrepare === 'function') {
            window.commEmailDraftPrepare(form, mode, modalEl).then(finishOpenCompose).catch(finishOpenCompose);
        } else {
            finishOpenCompose();
        }
    };

    function tryOpenComposeFromQuery() {
        try {
            var u = new URL(window.location.href);
            var c = u.searchParams.get('compose');
            if (c !== '1' && c !== 'new') return;
            if (!getEmailComposeModal()) return;
            var rawTo = u.searchParams.get('to');
            var initialTo = '';
            if (rawTo != null && String(rawTo).length) {
                try { initialTo = decodeURIComponent(String(rawTo).replace(/\+/g, ' ')); }
                catch (e1) { initialTo = String(rawTo); }
            }
            window.commMailOpenCompose('new', { initialTo: initialTo });
            u.searchParams.delete('compose');
            u.searchParams.delete('to');
            var qs = u.searchParams.toString();
            window.history.replaceState({}, '', u.pathname + (qs ? '?' + qs : '') + u.hash);
        } catch (e) {
            console.warn('tryOpenComposeFromQuery', e);
        }
    }

    function bindEmailComposeModal() {
        cleanupOrphanedEmailComposeModals();
        var modalEl = getEmailComposeModal();
        if (!modalEl || modalEl.dataset.commBound) return;
        modalEl.dataset.commBound = '1';
        modalEl.addEventListener('hidden.bs.modal', function () {
            var frm = modalEl.querySelector('#emailForm');
            var convIn = modalEl.querySelector('#emailConversationIdInput');
            if (convIn && frm) {
                convIn.setAttribute('name', 'conversation_id');
                var defId = frm.getAttribute('data-conversation-id');
                convIn.value = defId != null ? String(defId) : '';
            }
            clearEmailComposeFields(modalEl);
            setTimeout(function () {
                document.querySelectorAll('.modal-backdrop').forEach(function (b) { try { b.remove(); } catch (e) {} });
                document.body.classList.remove('modal-open');
                document.body.style.removeProperty('padding-right');
                document.body.style.removeProperty('overflow');
            }, 0);
        });
        tryOpenComposeFromQuery();
    }

    function isWhatsappChannelActive() {
        var whatsappContainer = document.getElementById('channel-whatsapp');
        return !!(whatsappContainer && !whatsappContainer.classList.contains('d-none'));
    }

    function setMicButtonRecording(isRecording) {
        var btn = document.getElementById('whatsappMicBtn');
        if (!btn) return;
        btn.innerHTML = isRecording ? '<i class="fas fa-stop-circle text-danger"></i>' : '<i class="fas fa-microphone"></i>';
    }

    function ensureWhatsappVoiceState() {
        if (!window.whatsappVoiceState) {
            window.whatsappVoiceState = {
                recording: false,
                recorder: null,
                chunks: [],
                blob: null,
                url: null,
                mimeType: null,
                stream: null
            };
        }
    }

    window.toggleWhatsappVoiceRecording = async function () {
        if (!isWhatsappChannelActive()) {
            alert('Para grabar audio, primero selecciona el canal WhatsApp.');
            return;
        }
        ensureWhatsappVoiceState();
        var state = window.whatsappVoiceState;
        if (state.recording) {
            stopWhatsappVoiceRecording();
            return;
        }
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            alert('Tu navegador no soporta grabacion de audio.');
            return;
        }
        if (typeof MediaRecorder === 'undefined') {
            alert('Tu navegador no soporta MediaRecorder para grabar audio.');
            return;
        }
        clearWhatsappVoiceNote();
        var stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        state.stream = stream;
        var preferredMimeTypes = ['audio/ogg;codecs=opus', 'audio/webm;codecs=opus', 'audio/mp4'];
        var selectedMime = '';
        for (var i = 0; i < preferredMimeTypes.length; i++) {
            var mt = preferredMimeTypes[i];
            if (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(mt)) {
                selectedMime = mt;
                break;
            }
        }
        var recorder = selectedMime ? new MediaRecorder(stream, { mimeType: selectedMime }) : new MediaRecorder(stream);
        state.recorder = recorder;
        state.mimeType = recorder.mimeType || selectedMime || '';
        state.chunks = [];
        state.recording = true;
        setMicButtonRecording(true);
        recorder.addEventListener('dataavailable', function (evt) {
            if (evt.data && evt.data.size > 0) state.chunks.push(evt.data);
        });
        recorder.addEventListener('stop', function () {
            state.recording = false;
            setMicButtonRecording(false);
            try {
                if (state.stream) state.stream.getTracks().forEach(function (t) { t.stop(); });
            } catch (e) {}
            state.stream = null;
            var blobType = state.mimeType || 'audio/ogg';
            state.blob = new Blob(state.chunks, { type: blobType });
            state.url = URL.createObjectURL(state.blob);
            renderWhatsappVoicePreview();
        });
        recorder.start();
    };

    function stopWhatsappVoiceRecording() {
        ensureWhatsappVoiceState();
        var state = window.whatsappVoiceState;
        if (!state.recorder || state.recorder.state === 'inactive') return;
        state.recorder.stop();
    }

    function renderWhatsappVoicePreview() {
        ensureWhatsappVoiceState();
        var state = window.whatsappVoiceState;
        var el = document.getElementById('whatsappVoicePreview');
        if (!state || !el || !state.url) return;
        el.classList.remove('d-none');
        el.innerHTML = '<div class="d-flex align-items-center justify-content-between p-2 bg-light rounded">' +
            '<audio controls style="max-width: 260px;"><source src="' + state.url + '"></audio>' +
            '<div class="d-flex gap-2 ms-2">' +
            '<button type="button" class="btn btn-sm btn-success" onclick="sendWhatsappVoiceNote()"><i class="fas fa-paper-plane"></i></button>' +
            '<button type="button" class="btn btn-sm btn-outline-danger" onclick="clearWhatsappVoiceNote()"><i class="fas fa-trash"></i></button>' +
            '</div></div>';
    }

    window.clearWhatsappVoiceNote = function () {
        ensureWhatsappVoiceState();
        var state = window.whatsappVoiceState;
        if (state.url) {
            try { URL.revokeObjectURL(state.url); } catch (e) {}
        }
        state.blob = null;
        state.url = null;
        state.chunks = [];
        state.mimeType = null;
        var el = document.getElementById('whatsappVoicePreview');
        if (el) {
            el.innerHTML = '';
            el.classList.add('d-none');
        }
    };

    window.sendWhatsappVoiceNote = function () {
        var form = document.getElementById('whatsappForm');
        if (form) sendMessage(form, 'whatsapp');
    };

    window.insertQuickReply = function (content) {
        var whatsappContainer = document.getElementById('channel-whatsapp');
        var emailContainer = document.getElementById('channel-email');
        if (whatsappContainer && !whatsappContainer.classList.contains('d-none')) {
            var activeTextarea = whatsappContainer.querySelector('textarea[name="message"]');
            if (activeTextarea) {
                var start = activeTextarea.selectionStart;
                var end = activeTextarea.selectionEnd;
                var text = activeTextarea.value;
                activeTextarea.value = text.substring(0, start) + content + text.substring(end);
                activeTextarea.selectionStart = activeTextarea.selectionEnd = start + content.length;
                activeTextarea.focus();
            }
        } else if (emailContainer && !emailContainer.classList.contains('d-none')) {
            var composeModal = getEmailComposeModal();
            var emailBodyDiv = (composeModal && composeModal.classList.contains('show') && composeModal.querySelector('#emailBodyDiv'))
                || emailContainer.querySelector('#emailBodyDivInline');
            if (emailBodyDiv) {
                emailBodyDiv.innerHTML += content;
                emailBodyDiv.focus();
                var range = document.createRange();
                var sel = window.getSelection();
                range.selectNodeContents(emailBodyDiv);
                range.collapse(false);
                sel.removeAllRanges();
                sel.addRange(range);
            }
        }
    };

    window.filterQuickReplies = function (input) {
        var filter = input.value.toLowerCase();
        var items = document.querySelectorAll('#quick-replies-list .quick-reply-item, #quick-replies-list-modal .quick-reply-item');
        items.forEach(function (item) {
            item.style.display = item.innerText.toLowerCase().includes(filter) ? '' : 'none';
        });
    };

    window.openFileSelector = function () {
        var whatsappContainer = document.getElementById('channel-whatsapp');
        var composeModal = getEmailComposeModal();
        var emailInput = (composeModal && composeModal.classList.contains('show') && composeModal.querySelector('#imageInputEmail'))
            || document.getElementById('imageInputEmail')
            || document.getElementById('imageInputEmailInline');
        var whatsappInput = document.getElementById('imageInputWhatsapp');
        if (whatsappContainer && !whatsappContainer.classList.contains('d-none') && whatsappInput) {
            whatsappInput.click();
        } else if (emailInput) {
            emailInput.click();
        }
    };

    function displayEmailFilePreview(files, formContext) {
        var preview = null;
        if (formContext) {
            preview = formContext.querySelector('#emailFilePreview, #emailFilePreviewInline');
        }
        if (!preview) {
            var modal = getEmailComposeModal();
            preview = (modal && modal.querySelector('#emailFilePreview'))
                || document.getElementById('emailFilePreviewInline');
        }
        if (!preview) return;
        preview.innerHTML = '';
        var fileArr = Array.from(files || []);
        fileArr.forEach(function (file, index) {
            var fileItem = document.createElement('div');
            fileItem.className = 'd-flex align-items-center justify-content-between p-2 bg-light rounded mb-1';

            var info = document.createElement('div');
            info.className = 'd-flex align-items-center flex-grow-1';

            if (file.type && file.type.indexOf('image/') === 0) {
                var img = document.createElement('img');
                img.className = 'me-2';
                img.style.cssText = 'width:40px;height:40px;object-fit:cover;border-radius:4px;';
                info.appendChild(img);
                var reader = new FileReader();
                reader.onload = function (e) { img.src = e.target.result; };
                try { reader.readAsDataURL(file); } catch (err) {}
            } else {
                var icon = document.createElement('i');
                icon.className = 'fas fa-file text-secondary me-2';
                if (file.type && file.type.indexOf('pdf') !== -1) icon.className = 'fas fa-file-pdf text-danger me-2';
                else if (file.type && (file.type.indexOf('word') !== -1 || file.type.indexOf('document') !== -1)) icon.className = 'fas fa-file-word text-primary me-2';
                else if (file.type && (file.type.indexOf('excel') !== -1 || file.type.indexOf('spreadsheet') !== -1)) icon.className = 'fas fa-file-excel text-success me-2';
                info.appendChild(icon);
            }

            var textWrap = document.createElement('div');
            var nameEl = document.createElement('div');
            nameEl.className = 'small fw-bold';
            nameEl.textContent = file.name || 'archivo';
            var sizeEl = document.createElement('div');
            sizeEl.className = 'text-muted';
            sizeEl.style.fontSize = '0.7rem';
            sizeEl.textContent = formatFileSize(file.size);
            textWrap.appendChild(nameEl);
            textWrap.appendChild(sizeEl);
            info.appendChild(textWrap);

            var actions = document.createElement('div');
            actions.className = 'd-flex gap-1 flex-shrink-0';

            var eyeBtn = document.createElement('button');
            eyeBtn.type = 'button';
            eyeBtn.className = 'btn btn-sm btn-outline-primary';
            eyeBtn.title = 'Vista previa';
            eyeBtn.innerHTML = '<i class="fas fa-eye"></i>';
            eyeBtn.addEventListener('click', function (e) {
                e.preventDefault();
                openUploadPreview(file, index);
            });

            var delBtn = document.createElement('button');
            delBtn.type = 'button';
            delBtn.className = 'btn btn-sm btn-outline-danger';
            delBtn.innerHTML = '<i class="fas fa-times"></i>';
            delBtn.addEventListener('click', function (e) {
                e.preventDefault();
                removeEmailFile(index);
            });

            actions.appendChild(eyeBtn);
            actions.appendChild(delBtn);
            fileItem.appendChild(info);
            fileItem.appendChild(actions);
            preview.appendChild(fileItem);
        });
    }

    window.removeEmailFile = function (index) {
        var modal = getEmailComposeModal();
        var input = (modal && modal.querySelector('#imageInputEmail'))
            || document.getElementById('imageInputEmail')
            || document.getElementById('imageInputEmailInline');
        if (!input) return;
        if (!Array.isArray(input._commFiles)) input._commFiles = [];
        input._commFiles = input._commFiles.filter(function (_f, i) { return i !== index; });
        var ctx = (modal && modal.contains(input)) ? modal : (input.closest('form') || modal);
        setReplyAttachFiles(input, input._commFiles, ctx);
    };

    function displayWhatsappFilePreview(files) {
        var preview = document.getElementById('whatsappFilePreview');
        if (!preview) return;
        preview.innerHTML = '';
        Array.from(files).forEach(function (file, index) {
            var fileItem = document.createElement('div');
            fileItem.className = 'd-flex align-items-center justify-content-between p-2 bg-light rounded mb-1';
            var size = formatFileSize(file.size);
            if (file.type.startsWith('image/')) {
                var reader = new FileReader();
                reader.onload = function (e) {
                    fileItem.innerHTML = '<div class="d-flex align-items-center flex-grow-1">' +
                        '<img src="' + e.target.result + '" style="width: 40px; height: 40px; object-fit: cover; border-radius: 4px;" class="me-2">' +
                        '<div><div class="small fw-bold">' + file.name + '</div><div class="text-muted" style="font-size: 0.7rem;">' + size + '</div></div></div>' +
                        '<div class="d-flex gap-1">' +
                        '<button type="button" class="btn btn-sm btn-outline-primary" onclick="event.preventDefault(); openUploadPreview(document.getElementById(\'imageInputWhatsapp\').files[' + index + '], ' + index + ')" title="Vista previa"><i class="fas fa-eye"></i></button>' +
                        '<button type="button" class="btn btn-sm btn-outline-danger ms-2" onclick="removeWhatsappFile(' + index + ')"><i class="fas fa-times"></i></button></div>';
                };
                reader.readAsDataURL(file);
            } else {
                fileItem.innerHTML = '<div class="d-flex align-items-center flex-grow-1"><i class="fas fa-file me-2"></i>' +
                    '<div><div class="small fw-bold">' + file.name + '</div><div class="text-muted" style="font-size: 0.7rem;">' + size + '</div></div></div>' +
                    '<div class="d-flex gap-1">' +
                    '<button type="button" class="btn btn-sm btn-outline-primary" onclick="event.preventDefault(); openUploadPreview(document.getElementById(\'imageInputWhatsapp\').files[' + index + '], ' + index + ')" title="Vista previa"><i class="fas fa-eye"></i></button>' +
                    '<button type="button" class="btn btn-sm btn-outline-danger ms-2" onclick="removeWhatsappFile(' + index + ')"><i class="fas fa-times"></i></button></div>';
            }
            preview.appendChild(fileItem);
        });
    }

    window.removeWhatsappFile = function (index) {
        var input = document.getElementById('imageInputWhatsapp');
        if (!input) return;
        var dt = new DataTransfer();
        var files = Array.from(input.files);
        if (index < 0 || index >= files.length) return;
        files.forEach(function (file, i) { if (i !== index) dt.items.add(file); });
        input.files = dt.files;
        if (input.files.length > 0) displayWhatsappFilePreview(input.files);
        else document.getElementById('whatsappFilePreview').innerHTML = '';
    };

    window.handleFileClick = function (index) {
        var input = document.getElementById('imageInputEmail');
        if (!input || !input.files || !input.files[index]) return;
        var file = input.files[index];
        alert('Archivo: ' + file.name + '\nTamaño: ' + formatFileSize(file.size) + '\nTipo: ' + file.type);
    };

    function sendMessage(form, channel) {
        if (channel === 'email') {
            var emailBodyDiv = form.querySelector('#emailBodyDiv, #emailBodyDivInline');
            var emailBodyInput = form.querySelector('#emailBodyInput, #emailBodyInputInline');
            var fileInputEmail = form.querySelector('#imageInputEmail, #imageInputEmailInline');
            if (emailBodyDiv && emailBodyInput) {
                var tempDiv = document.createElement('div');
                tempDiv.innerHTML = emailBodyDiv.innerHTML;
                tempDiv.querySelectorAll('img').forEach(function (img) { img.remove(); });
                tempDiv.querySelectorAll('div').forEach(function (div) {
                    if (div.innerHTML.includes('fa-file-pdf') || div.innerHTML.includes('fa-file-word') ||
                        div.innerHTML.includes('fa-file-excel') || div.innerHTML.includes('fa-file')) {
                        div.remove();
                    }
                });
                var textContent = tempDiv.textContent || tempDiv.innerText || '';
                var hasAttach = false;
                if (fileInputEmail) {
                    flushEmailAttachToInput(fileInputEmail);
                    hasAttach = !!(fileInputEmail._commFiles && fileInputEmail._commFiles.length) || fileInputEmail.files.length > 0;
                }
                if (textContent.trim() === '' && !hasAttach) {
                    alert('Por favor escribe un mensaje o adjunta archivos antes de enviar.');
                    return;
                }
                emailBodyInput.value = emailBodyDiv.innerHTML;
            }
        }

        var formData = new FormData(form);
        var btn = form.querySelector('button[type="submit"]');
        var originalText = btn.innerHTML;

        if (channel === 'email') {
            var fileInputEmailSend = form.querySelector('#imageInputEmail, #imageInputEmailInline');
            if (fileInputEmailSend) {
                flushEmailAttachToInput(fileInputEmailSend);
                if (fileInputEmailSend.files.length > 0) {
                    formData.delete('attachments');
                    Array.from(fileInputEmailSend.files).forEach(function (file) { formData.append('attachments', file); });
                }
            }
        }

        if (channel === 'whatsapp') {
            var fileInputWhatsapp = document.getElementById('imageInputWhatsapp');
            var voiceBlob = window.whatsappVoiceState && window.whatsappVoiceState.blob ? window.whatsappVoiceState.blob : null;
            var messageText = (form.querySelector('textarea[name="message"]') || {}).value || '';
            messageText = messageText.trim();
            var hasFiles = !!(fileInputWhatsapp && fileInputWhatsapp.files && fileInputWhatsapp.files.length > 0);
            if (!messageText && !hasFiles && !voiceBlob) {
                alert('Por favor escribe un mensaje, adjunta un archivo o graba un audio antes de enviar.');
                return;
            }
            formData.delete('attachments');
            if (hasFiles) {
                Array.from(fileInputWhatsapp.files).forEach(function (file) { formData.append('attachments', file); });
            }
            if (voiceBlob) {
                var rawMime = (voiceBlob.type || '').toLowerCase();
                var mime = rawMime || 'audio/ogg';
                var ext = 'ogg';
                if (mime.includes('webm')) ext = 'webm';
                else if (mime.includes('mpeg')) ext = 'mp3';
                else if (mime.includes('mp4')) ext = 'm4a';
                else if (mime.includes('opus')) ext = 'opus';
                var voiceFile = new File([voiceBlob], 'voice.' + ext, { type: mime });
                formData.append('attachments', voiceFile);
            }
            var toNumber = formData.get('to_number');
            if (!toNumber || String(toNumber).trim() === '') {
                alert('Error: El contacto no tiene un número de teléfono válido para WhatsApp.');
                return;
            }
        }

        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Enviando...';

        if (channel === 'email') {
            try {
                if (typeof window.commEmailDraftSave === 'function') {
                    window.commEmailDraftSave(form, { force: true, keepalive: true });
                }
                if (typeof window.commEmailDraftMarkSending === 'function') {
                    window.commEmailDraftMarkSending(form);
                }
                var modalElSend = getEmailComposeModal();
                if (modalElSend && typeof bootstrap !== 'undefined') {
                    var instSend = bootstrap.Modal.getInstance(modalElSend)
                        || bootstrap.Modal.getOrCreateInstance(modalElSend);
                    instSend.hide();
                }
            } catch (eHide) {}
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
                if (snippet.indexOf('<!DOCTYPE') === 0 || snippet.indexOf('<html') === 0) {
                    data = { error: 'El servidor respondio con una pagina HTML (codigo ' + response.status + ').' };
                } else {
                    data = { error: snippet || ('HTTP ' + response.status) };
                }
            }
            if (!response.ok) {
                var errorMsg = data.error || data.detail || ('Error al enviar mensaje (HTTP ' + response.status + ')');
                if (typeof errorMsg === 'object') {
                    try {
                        if (errorMsg.message) errorMsg = errorMsg.message;
                        else if (errorMsg.error && errorMsg.error.message) errorMsg = errorMsg.error.message;
                        else errorMsg = JSON.stringify(errorMsg);
                    } catch (e) {
                        errorMsg = 'Error desconocido';
                    }
                }
                throw new Error(errorMsg);
            }
            return data;
        }).then(function () {
            if (channel === 'email' && typeof window.commEmailDraftDiscard === 'function') {
                window.commEmailDraftDiscard(form);
            }
            if (channel === 'whatsapp') {
                var messageTextarea = form.querySelector('textarea[name="message"]');
                if (messageTextarea) messageTextarea.value = '';
                var waInput = document.getElementById('imageInputWhatsapp');
                if (waInput) waInput.value = '';
                var waPreview = document.getElementById('whatsappFilePreview');
                if (waPreview) waPreview.innerHTML = '';
                clearWhatsappVoiceNote();
            } else {
                var bodyDiv = form.querySelector('#emailBodyDiv, #emailBodyDivInline');
                var bodyInput = form.querySelector('#emailBodyInput, #emailBodyInputInline');
                if (bodyDiv) bodyDiv.innerHTML = '';
                if (bodyInput) bodyInput.value = '';
                var subjectInput = form.querySelector('input[name="subject"]');
                if (subjectInput) subjectInput.value = '';
                var emInput = form.querySelector('#imageInputEmail, #imageInputEmailInline');
                if (emInput) clearEmailAttachInput(emInput);
                var emPreview = form.querySelector('#emailFilePreview, #emailFilePreviewInline');
                if (emPreview) emPreview.innerHTML = '';
            }

            refreshMessages();

            btn.innerHTML = '<i class="fas fa-check"></i> Enviado';
            setTimeout(function () {
                btn.disabled = false;
                btn.innerHTML = originalText;
            }, 2000);
        }).catch(function (error) {
            console.error('Error:', error);
            alert('Error al enviar mensaje: ' + error.message);
            btn.disabled = false;
            btn.innerHTML = originalText;
            if (form) form.dataset.commDraftSending = '0';
        });
    }

    window.sendMessage = sendMessage;

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
        document.querySelectorAll('.modal-backdrop').forEach(function (b) { try { b.remove(); } catch (e5) {} });
        document.body.classList.remove('modal-open');
        document.body.style.removeProperty('padding-right');
        document.body.style.removeProperty('overflow');
    }

    window.openWhatsappTemplateModal = function () {
        var modalEl = document.getElementById('whatsappTemplateModal');
        if (!modalEl || typeof bootstrap === 'undefined') return;
        ensureBootstrapModalRoot(modalEl);
        cleanupOverlays(modalEl.id);
        var select = document.getElementById('waTemplateSelect');
        var paramsWrap = document.getElementById('waTemplateParams');
        var warn = document.getElementById('waTemplateWarn');
        if (warn) {
            warn.classList.add('d-none');
            warn.textContent = '';
        }
        if (paramsWrap) paramsWrap.innerHTML = '';
        if (select) select.value = '';
        bootstrap.Modal.getOrCreateInstance(modalEl).show();
    };

    function bindWhatsappTemplateCleanup() {
        var modalEl = document.getElementById('whatsappTemplateModal');
        if (!modalEl || typeof bootstrap === 'undefined' || modalEl.dataset.commCleanupBound) return;
        modalEl.dataset.commCleanupBound = '1';
        modalEl.addEventListener('hidden.bs.modal', function () {
            setTimeout(function () {
                document.querySelectorAll('.modal-backdrop').forEach(function (b) { try { b.remove(); } catch (e) {} });
                document.body.classList.remove('modal-open');
                document.body.style.removeProperty('padding-right');
                document.body.style.removeProperty('overflow');
            }, 0);
        });
    }

    window.updateWaTemplateDynamicPreview = function () {
        var preview = document.getElementById('waTemplateDynamicPreview');
        if (!preview) return;
        var tpl = (document.getElementById('waTemplateSelect') || {}).value || '';
        if (tpl === 'recordatorio_cuota') {
            var c = (document.querySelector('[name="wa_body_param_0"]') || {}).value || '';
            var m = (document.querySelector('[name="wa_body_param_1"]') || {}).value || '';
            var i = (document.querySelector('[name="wa_body_param_2"]') || {}).value || '';
            var d = (document.querySelector('[name="wa_body_param_3"]') || {}).value || '';
            preview.textContent = 'Hola ' + (c.trim() || '{{1}}') + ', le recordamos que su cuota del mes de ' + (m.trim() || '{{2}}') + ' por un importe de ' + (i.trim() || '{{3}}') + ' vence el dia ' + (d.trim() || '{{4}}') + '.';
            return;
        }
        if (tpl === 'saludo_personalizado') {
            var txt = (document.querySelector('[name="wa_body_param_0"]') || {}).value || '';
            preview.textContent = 'Hola ' + (txt.trim() || '{{1}}') + '\n\nSaludos.\nEstudio Carol G.';
        }
    };

    function initWaClientAutocomplete(input, suggest) {
        if (!input || !suggest || input.dataset.waClientSuggest) return;
        input.dataset.waClientSuggest = '1';
        var endpoint = cfg('clientsSearchUrl');
        var items = [];
        var activeIndex = -1;
        var lastQuery = '';
        var timer = null;
        function show() { suggest.classList.remove('d-none'); }
        function hide() { suggest.classList.add('d-none'); suggest.innerHTML = ''; activeIndex = -1; }
        function render() {
            suggest.innerHTML = '';
            if (!items.length) { hide(); return; }
            items.forEach(function (it, idx) {
                var row = document.createElement('div');
                row.className = 'comm-email-suggest-item' + (idx === activeIndex ? ' active' : '');
                var label = it && it.name ? String(it.name) : '';
                row.innerHTML = '<div class="comm-email-suggest-name">' + label + '</div>';
                row.addEventListener('mousedown', function (e) {
                    e.preventDefault();
                    input.value = label;
                    window.updateWaTemplateDynamicPreview();
                    hide();
                    try { input.focus(); } catch (e2) {}
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
            var q = (input.value || '').trim();
            if (!q) { hide(); return; }
            if (q === lastQuery && !suggest.classList.contains('d-none')) return;
            lastQuery = q;
            if (timer) clearTimeout(timer);
            timer = setTimeout(async function () {
                items = await fetchItems(q);
                activeIndex = -1;
                render();
            }, 220);
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
                if (activeIndex >= 0 && items[activeIndex]) {
                    e.preventDefault();
                    input.value = String(items[activeIndex].name || '');
                    window.updateWaTemplateDynamicPreview();
                    hide();
                }
            } else if (e.key === 'Escape') {
                hide();
            }
        });
        input.addEventListener('blur', function () { setTimeout(hide, 220); });
    }

    function bindTemplateSelect() {
        var select = document.getElementById('waTemplateSelect');
        if (!select || select.dataset.bound) return;
        select.dataset.bound = '1';
        select.addEventListener('change', function renderParams() {
            var opt = select.options[select.selectedIndex];
            var paramsWrap = document.getElementById('waTemplateParams');
            if (!paramsWrap) return;
            paramsWrap.innerHTML = '';
            if (!opt || !opt.value) return;
            var count = parseInt(opt.getAttribute('data-body-params') || '0', 10) || 0;
            if (count <= 0) return;
            var templateName = (opt.value || '').trim();
            var box = document.createElement('div');
            box.className = 'mb-2';
            box.innerHTML = '<label class="form-label fw-bold">Variables</label>';
            paramsWrap.appendChild(box);
            if (templateName === 'recordatorio_cuota') {
                paramsWrap.innerHTML += '<div class="mb-2"><label class="form-label fw-bold mb-1">Cliente</label><div class="position-relative">' +
                    '<input type="text" class="form-control" name="wa_body_param_0" id="waTemplateClientInput" placeholder="Buscar cliente..." autocomplete="off" spellcheck="false">' +
                    '<div id="waTemplateClientSuggest" class="comm-email-suggest d-none"></div></div></div>' +
                    '<div class="row g-2"><div class="col-12 col-md-4"><label class="form-label fw-bold mb-1">Mes</label><input type="text" class="form-control" name="wa_body_param_1" placeholder="Ej: junio"></div>' +
                    '<div class="col-12 col-md-4"><label class="form-label fw-bold mb-1">Importe</label><input type="text" class="form-control" name="wa_body_param_2" placeholder="Ej: $ 12.000"></div>' +
                    '<div class="col-12 col-md-4"><label class="form-label fw-bold mb-1">Dia</label><input type="text" class="form-control" name="wa_body_param_3" placeholder="Ej: 10"></div></div>' +
                    '<div class="mt-3"><div class="form-text">Vista previa</div><div class="border rounded p-2 small bg-light" id="waTemplateDynamicPreview"></div></div>';
                var clientInput = document.getElementById('waTemplateClientInput');
                if (clientInput && !clientInput.value) clientInput.value = cfg('displayName');
                var monthInput = document.querySelector('[name="wa_body_param_1"]');
                if (monthInput && !monthInput.value) {
                    try { monthInput.value = new Date().toLocaleString('es-AR', { month: 'long' }); } catch (e) {}
                }
                paramsWrap.querySelectorAll('input').forEach(function (inp) {
                    inp.addEventListener('input', window.updateWaTemplateDynamicPreview);
                });
                initWaClientAutocomplete(document.getElementById('waTemplateClientInput'), document.getElementById('waTemplateClientSuggest'));
                window.updateWaTemplateDynamicPreview();
                return;
            }
            if (templateName === 'saludo_personalizado') {
                paramsWrap.innerHTML += '<div class="mb-2"><label class="form-label fw-bold mb-1">Texto del usuario</label>' +
                    '<textarea class="form-control" rows="3" name="wa_body_param_0" placeholder="Ej: Gonzalo, queriamos avisarte que ya esta listo tu estudio"></textarea></div>' +
                    '<div class="mt-3"><div class="form-text">Vista previa</div><div class="border rounded p-2 small bg-light" id="waTemplateDynamicPreview" style="white-space: pre-wrap;"></div></div>';
                var txt = document.querySelector('[name="wa_body_param_0"]');
                if (txt) txt.addEventListener('input', window.updateWaTemplateDynamicPreview);
                window.updateWaTemplateDynamicPreview();
                return;
            }
            for (var i = 0; i < count; i++) {
                var row = document.createElement('div');
                row.className = 'mb-2';
                row.innerHTML = '<input type="text" class="form-control" name="wa_body_param_' + i + '" placeholder="Variable ' + (i + 1) + '">';
                paramsWrap.appendChild(row);
            }
        });
    }

    window.sendWhatsappTemplate = function () {
        var btn = document.getElementById('waTemplateSendBtn');
        var warn = document.getElementById('waTemplateWarn');
        var select = document.getElementById('waTemplateSelect');
        var modalEl = document.getElementById('whatsappTemplateModal');
        function showWarn(msg) {
            if (!warn) return;
            warn.textContent = msg;
            warn.classList.remove('d-none');
        }
        if (!select || !select.value) {
            showWarn('Selecciona una plantilla.');
            return;
        }
        var opt = select.options[select.selectedIndex];
        var templateName = select.value;
        var language = opt && opt.getAttribute('data-language') ? opt.getAttribute('data-language') : '';
        var toNumber = cfg('toNumber');
        if (!toNumber || !toNumber.trim()) {
            showWarn('El contacto no tiene un numero de telefono valido para WhatsApp.');
            return;
        }
        if (!language) {
            showWarn('La plantilla no tiene lenguaje configurado.');
            return;
        }
        var count = parseInt(opt.getAttribute('data-body-params') || '0', 10) || 0;
        var bodyParams = [];
        for (var i = 0; i < count; i++) {
            var input = document.querySelector('#waTemplateParams input[name="wa_body_param_' + i + '"]');
            var textarea = document.querySelector('#waTemplateParams textarea[name="wa_body_param_' + i + '"]');
            var value = input ? (input.value || '') : (textarea ? (textarea.value || '') : '');
            bodyParams.push(value);
        }
        if (count > 0 && bodyParams.some(function (p) { return !String(p || '').trim(); })) {
            showWarn('Completa todas las variables de la plantilla.');
            return;
        }
        var csrf = document.querySelector('input[name="csrfmiddlewaretoken"]') ? document.querySelector('input[name="csrfmiddlewaretoken"]').value : '';
        var formData = new FormData();
        if (csrf) formData.append('csrfmiddlewaretoken', csrf);
        formData.append('conversation_id', cfg('conversationId'));
        formData.append('to_number', toNumber);
        formData.append('template_name', templateName);
        formData.append('language_code', language);
        bodyParams.forEach(function (p) { formData.append('body_params', p); });
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Enviando...';
        }
        fetch(cfg('sendTemplateUrl'), {
            method: 'POST',
            body: formData,
            headers: { 'X-CSRFToken': csrf }
        }).then(async function (response) {
            var data = await response.json().catch(function () { return {}; });
            if (!response.ok) {
                var msg = data && data.error ? (typeof data.error === 'string' ? data.error : JSON.stringify(data.error)) : 'Error al enviar plantilla';
                throw new Error(msg);
            }
            return data;
        }).then(function () {
            if (modalEl && typeof bootstrap !== 'undefined') {
                bootstrap.Modal.getOrCreateInstance(modalEl).hide();
            }
            refreshMessages();
        }).catch(function (err) {
            showWarn(err.message);
        }).finally(function () {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-paper-plane me-1"></i> Enviar';
            }
        });
    };

    window.printMessage = function (messageId) {
            var messageElement = document.querySelector('[data-message-id="' + messageId + '"]');
            if (!messageElement) {
                alert('No se pudo encontrar el mensaje #' + messageId + ' para imprimir.');
                return;
            }
            
            var headerElement = messageElement.querySelector('.msg-header');
            var headerText = headerElement ? headerElement.textContent.trim() : 'Mensaje de Correo';
            
            // CORRECCIÓN: Clonamos todo el contenedor del mensaje para capturar texto + adjuntos
            var clone = messageElement.cloneNode(true);
            
            // Removemos los botones de acción del clon para que no se impriman a sí mismos
            var actionButtons = clone.querySelector('.msg-action-buttons') || clone.querySelector('.email-read-toolbar-actions');
            if (actionButtons) actionButtons.remove();
            
            // Ocultamos la cabecera invisible dentro del clon para manejarla nosotros
            var innerHeader = clone.querySelector('.msg-header');
            if (innerHeader) innerHeader.remove();

            var contentHTML = clone.innerHTML;
            
            var printWindow = window.open('', '_blank', 'width=800,height=600');
            if (!printWindow) {
                alert('Por favor, permite las ventanas emergentes.');
                return;
            }

            var printHTML = '<!DOCTYPE html><html><head><title>Mensaje #' + messageId + '</title>' +
                '<style>' +
                'body{font-family:Arial,sans-serif;margin:30px;line-height:1.5;color:#333;}' +
                '.header{font-weight:bold;margin-bottom:20px;padding:12px;background:#f8f9fa;border:1px solid #e0e0e0;border-radius:6px;font-size:14px;}' +
                '.content{margin-bottom:25px;font-size:15px;}' +
                'img{max-width:200px; height:auto; display:block; margin-top:10px; border-radius:4px; border:1px solid #ddd;}' +
                '.attachment-footer, .email-thread-attachment{margin-top:10px; padding:10px; background:#f9f9f9; border-radius:4px; display:inline-block; border:1px solid #eee;}' +
                '.footer{font-size:11px;color:#777;margin-top:30px;border-top:1px solid #eee;padding-top:10px;}' +
                '@media print{body{margin:15px;}}' +
                '</style>' +
                '</head><body>' +
                '<h2>Mensaje #' + messageId + '</h2>' +
                '<div class="header">' + headerText + '</div>' +
                '<div class="content">' + contentHTML + '</div>' + 
                '<div class="footer">Impreso el ' + new Date().toLocaleString() + '</div>' +
                '</body></html>';
            
            printWindow.document.write(printHTML);
            printWindow.document.close();
            
            printWindow.onload = function() {
                printWindow.print();
                printWindow.close();
            };
        };

      window.downloadMessage = function (messageId, messageType) {
            var messageElement = document.querySelector('[data-message-id="' + messageId + '"]');
            if (!messageElement) {
                alert('No se pudo encontrar el mensaje para descargar.');
                return;
            }
            
            var headerElement = messageElement.querySelector('.msg-header');
            var headerText = headerElement ? headerElement.textContent.trim() : 'Mensaje';
            
            // Clonamos exactamente igual para limpiar elementos basura
            var clone = messageElement.cloneNode(true);
            var actionButtons = clone.querySelector('.msg-action-buttons') || clone.querySelector('.email-read-toolbar-actions');
            if (actionButtons) actionButtons.remove();
            var innerHeader = clone.querySelector('.msg-header');
            if (innerHeader) innerHeader.remove();

            var fileContent = '';
            var fileExtension = 'html'; // Forzamos por defecto extensión web para asegurar diseño
            var mimeType = 'text/html;charset=utf-8';

            // DETERMINACIÓN ABSOLUTA: Si contiene clases de email en el documento, se procesa como HTML estructurado
            var hasEmailClasses = messageElement.querySelector('.email-body') || 
                                messageElement.querySelector('.email-read-body') || 
                                messageElement.querySelector('.email-thread-message') ||
                                messageElement.classList.contains('is-email');

            if (hasEmailClasses) {
                fileContent = '<!DOCTYPE html><html><head><title>Mensaje #' + messageId + '</title>' +
                    '<style>' +
                    'body{font-family:Arial,sans-serif;margin:30px;line-height:1.5;color:#333;}' +
                    '.header{font-weight:bold;margin-bottom:20px;padding:12px;background:#f8f9fa;border:1px solid #e0e0e0;border-radius:6px;font-size:14px;}' +
                    '.content{margin-bottom:25px;} ' +
                    'img{max-width:200px;height:auto;display:block;margin-top:10px;border-radius:4px;border:1px solid #ddd;}' +
                    '.attachment-footer, .email-thread-attachment{margin-top:10px; padding:10px; background:#f9f9f9; border-radius:4px; display:inline-block; border:1px solid #eee;}' +
                    '</style>' +
                    '</head><body>' +
                    '<h2>Mensaje #' + messageId + ' (EMAIL)</h2>' +
                    '<div class="header">' + headerText + ' <br><small>Descargado el: ' + new Date().toLocaleString() + '</small></div>' +
                    '<div class="content">' + clone.innerHTML + '</div>' + 
                    '</body></html>';
            } else {
                // Solo si es un chat plano estricto de WhatsApp sin estructuras complejas
                fileExtension = 'txt';
                mimeType = 'text/plain;charset=utf-8';
                var contentElement = messageElement.querySelector('.msg-bubble');
                fileContent = 'Mensaje #' + messageId + '\n' +
                            'Tipo: ' + (messageType || 'chat') + '\n' +
                            'Fecha de Descarga: ' + new Date().toLocaleString() + '\n' + 
                            '='.repeat(50) + '\n\n' +
                            headerText + '\n\n' +
                            'Contenido:\n' + (contentElement ? contentElement.innerText.trim() : '(Sin contenido)');
            }
            
            // Procesa y gatilla la descarga forzando los tipos correctos detectados
            try {
                var blob = new Blob([fileContent], { type: mimeType });
                var url = window.URL.createObjectURL(blob);
                var a = document.createElement('a');
                a.href = url;
                a.download = 'mensaje_' + messageId + '_' + (messageType || 'archivo') + '_' + new Date().getTime() + '.' + fileExtension;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
            } catch (error) {
                alert('Error al descargar el mensaje');
            }
        };




    window.openAttachmentPreview = function (fileUrl, fileName) {
        var modal = document.getElementById('attachmentPreviewModal');
        var fileNameElement = document.getElementById('attachmentFileName');
        var previewContent = document.getElementById('attachmentPreviewContent');
        var downloadLink = document.getElementById('attachmentDownloadLink');
        if (!modal || !fileNameElement || !previewContent || !downloadLink) return;
        fileNameElement.textContent = fileName;
        downloadLink.href = fileUrl;
        downloadLink.download = fileName;
        var fileExtension = fileName.split('.').pop().toLowerCase();
        var previewHTML = '';
        if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(fileExtension)) {
            previewHTML = '<img src="' + fileUrl + '" alt="' + fileName + '" style="max-width: 100%; max-height: 500px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">';
        } else if (['mp4', 'webm', 'ogg'].includes(fileExtension)) {
            previewHTML = '<video controls style="max-width: 100%; max-height: 500px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);"><source src="' + fileUrl + '">Tu navegador no soporta la reproduccion de video.</video>';
        } else if (['mp3', 'wav', 'ogg', 'm4a', 'opus'].includes(fileExtension)) {
            previewHTML = '<div class="text-center p-4"><i class="fas fa-file-audio" style="font-size: 4rem; color: #ff6b35; margin-bottom: 20px;"></i><h5 class="mb-3">' + fileName + '</h5><audio controls class="w-100"><source src="' + fileUrl + '">Tu navegador no soporta la reproduccion de audio.</audio></div>';
        } else if (['pdf'].includes(fileExtension) || (fileUrl && String(fileUrl).toLowerCase().indexOf('.pdf') !== -1)) {
            previewHTML =
                '<div class="text-start">' +
                '<embed src="' + fileUrl + '#toolbar=1" type="application/pdf" ' +
                'style="width:100%;height:min(70vh,560px);border:1px solid #dee2e6;border-radius:8px;background:#f8f9fa;">' +
                '<p class="text-muted small mt-2 mb-0">Si no se ve el PDF: ' +
                '<a href="' + fileUrl + '" target="_blank" rel="noopener">abrir en pestaña</a></p>' +
                '</div>';
        } else {
            previewHTML = '<div class="text-center p-4"><i class="fas fa-file" style="font-size: 4rem; color: #6c757d; margin-bottom: 20px;"></i><h5 class="mb-3">' + fileName + '</h5><p class="text-muted">Vista previa no disponible para este tipo de archivo. Haz clic en "Descargar" para ver el archivo.</p></div>';
        }
        previewContent.innerHTML = previewHTML;
        ensureBootstrapModalRoot(modal);
        bootstrap.Modal.getOrCreateInstance(modal).show();
    };

    window.closeAttachmentPreview = function () {
        var modal = document.getElementById('attachmentPreviewModal');
        if (!modal) return;
        var modalInstance = bootstrap.Modal.getInstance(modal);
        if (modalInstance) modalInstance.hide();
    };

    window.openUploadPreview = function (file, index, source) {
        if (!file) return;
        var modal = document.getElementById('uploadPreviewModal');
        var fileNameElement = document.getElementById('uploadPreviewFileName');
        var previewContent = document.getElementById('uploadPreviewContent');
        if (!modal || !fileNameElement || !previewContent) return;
        window.currentUploadFileIndex = index;
        window.currentUploadFileSource = source || null;
        fileNameElement.textContent = file.name;
        var fileExtension = file.name.split('.').pop().toLowerCase();
        var previewHTML = '';
        if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(fileExtension)) {
            previewHTML = '<img src="' + URL.createObjectURL(file) + '" alt="' + file.name + '" style="max-width: 100%; max-height: 500px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">';
        } else if (['mp4', 'webm', 'ogg'].includes(fileExtension)) {
            previewHTML = '<video controls style="max-width: 100%; max-height: 500px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);"><source src="' + URL.createObjectURL(file) + '">Tu navegador no soporta la reproduccion de video.</video>';
        } else if (['mp3', 'wav', 'ogg', 'm4a', 'opus'].includes(fileExtension)) {
            previewHTML = '<div class="text-center p-4"><i class="fas fa-file-audio" style="font-size: 4rem; color: #ff6b35; margin-bottom: 20px;"></i><h5 class="mb-3">' + file.name + '</h5><p class="text-muted mb-3">Tamaño: ' + formatFileSize(file.size) + '</p><audio controls class="w-100"><source src="' + URL.createObjectURL(file) + '">Tu navegador no soporta la reproduccion de audio.</audio></div>';
        } else if (['pdf'].includes(fileExtension) || (file.type && file.type.indexOf('pdf') !== -1)) {
            var pdfUrl = URL.createObjectURL(file);
            previewHTML =
                '<div class="text-start">' +
                '<embed src="' + pdfUrl + '#toolbar=1" type="application/pdf" ' +
                'style="width:100%;height:min(70vh,560px);border:1px solid #dee2e6;border-radius:8px;background:#f8f9fa;">' +
                '<p class="text-muted small mt-2 mb-0">Si no se ve el PDF, abrilo en una pestaña: ' +
                '<a href="' + pdfUrl + '" target="_blank" rel="noopener">abrir archivo</a></p>' +
                '</div>';
        } else {
            previewHTML = '<div class="text-center p-4"><i class="fas fa-file" style="font-size: 4rem; color: #6c757d; margin-bottom: 20px;"></i><h5 class="mb-3">' + file.name + '</h5><p class="text-muted mb-3">Tamaño: ' + formatFileSize(file.size) + '</p><p class="text-muted">Vista previa no disponible para este tipo de archivo. Este archivo se enviara correctamente.</p></div>';
        }
        previewContent.innerHTML = previewHTML;
        ensureBootstrapModalRoot(modal);
        modal.style.zIndex = '1100';
        modal.addEventListener('shown.bs.modal', function onUploadPreviewShown() {
            modal.removeEventListener('shown.bs.modal', onUploadPreviewShown);
            var backs = document.querySelectorAll('.modal-backdrop');
            if (backs.length) backs[backs.length - 1].classList.add('modal-backdrop-upload-preview');
        });
        bootstrap.Modal.getOrCreateInstance(modal).show();
    };

    window.closeUploadPreview = function () {
        var modal = document.getElementById('uploadPreviewModal');
        if (!modal) return;
        var modalInstance = bootstrap.Modal.getInstance(modal);
        if (modalInstance) modalInstance.hide();
    };

    window.removeUploadFile = function () {
        if (window.currentUploadFileIndex === undefined || window.currentUploadFileIndex === null) return;
        if (window.currentUploadFileSource === 'global') {
            if (typeof window.commRemoveGlobalAttach === 'function') {
                window.commRemoveGlobalAttach(window.currentUploadFileIndex);
            }
            window.currentUploadFileSource = null;
            window.closeUploadPreview();
            return;
        }
        var whatsappContainer = document.getElementById('channel-whatsapp');
        if (whatsappContainer && !whatsappContainer.classList.contains('d-none')) {
            window.removeWhatsappFile(window.currentUploadFileIndex);
        } else {
            window.removeEmailFile(window.currentUploadFileIndex);
        }
        window.closeUploadPreview();
    };

    function getLastInboundMeta(rootEl) {
        if (!rootEl) return { id: 0, kind: 'whatsapp' };
        var nodes = rootEl.querySelectorAll('.omni-msg-row.inbound[data-message-id]');
        var last = nodes.length ? nodes[nodes.length - 1] : null;
        var id = last ? parseInt(last.getAttribute('data-message-id') || '0', 10) : 0;
        var pageChannel = cfg('channel');
        if (pageChannel === 'multichannel') {
            var kind = last && last.classList.contains('is-email') ? 'email' : 'whatsapp';
            return { id: Number.isFinite(id) ? id : 0, kind: kind };
        }
        if (pageChannel === 'email') return { id: Number.isFinite(id) ? id : 0, kind: 'email' };
        return { id: Number.isFinite(id) ? id : 0, kind: 'whatsapp' };
    }

    function initPolling() {
        if (window.conversationPollInterval) {
            clearInterval(window.conversationPollInterval);
            window.conversationPollInterval = null;
        }
        if (cfg('channel') === 'email') return;
        setTimeout(function () {
            var chatArea = document.getElementById('chatMessagesArea');
            if (chatArea) chatArea.scrollTop = chatArea.scrollHeight;
        }, 100);
        window.conversationPollInterval = setInterval(function () {
            var chatArea = document.getElementById('chatMessagesArea');
            if (!chatArea) {
                clearInterval(window.conversationPollInterval);
                return;
            }
            var prevMeta = getLastInboundMeta(chatArea);
            var url = cfg('conversationDetailUrl');
            var openState = getDetailsOpenState(chatArea);
            var previousScrollTop = chatArea.scrollTop;
            var isAtBottom = chatArea.scrollHeight - chatArea.scrollTop <= chatArea.clientHeight + 100;
            fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
                .then(function (response) { return response.text(); })
                .then(function (html) {
                    var parser = new DOMParser();
                    var doc = parser.parseFromString(html, 'text/html');
                    var newContent = doc.getElementById('chatMessagesArea');
                    if (!newContent || !chatArea) return;
                    var nextMeta = getLastInboundMeta(newContent);
                    chatArea.innerHTML = newContent.innerHTML;
                    restoreDetailsOpenState(chatArea, openState);
                    if (isAtBottom) {
                        chatArea.scrollTop = chatArea.scrollHeight;
                    } else {
                        chatArea.scrollTop = Math.min(previousScrollTop, chatArea.scrollHeight - chatArea.clientHeight);
                    }
                    requestAnimationFrame(updateMoreMessagesIndicator);
                    setTimeout(updateMoreMessagesIndicator, 50);
                    if (nextMeta.id && nextMeta.id > prevMeta.id) {
                        if (window.commNotify && typeof window.commNotify.playDing === 'function') {
                            window.commNotify.playDing(nextMeta.kind);
                        }
                    }
                })
                .catch(function (err) { console.error('Polling error:', err); });
        }, 10000);
    }

    if (typeof window.chatSelectMode === 'undefined') window.chatSelectMode = false;
    if (!window.selectedChatMessageIds) window.selectedChatMessageIds = new Set();

    window.toggleChatSelectMode = function () {
        var chatArea = document.getElementById('chatMessagesArea');
        var btnForward = document.getElementById('forwardSelectedBtn');
        var btnToggle = document.getElementById('toggleSelectBtn');
        window.chatSelectMode = !window.chatSelectMode;
        if (chatArea) chatArea.classList.toggle('select-mode', window.chatSelectMode);
        if (!window.chatSelectMode) clearChatSelection();
        if (btnForward) btnForward.classList.toggle('d-none', !window.chatSelectMode);
        if (btnToggle) {
            btnToggle.classList.toggle('btn-outline-secondary', !window.chatSelectMode);
            btnToggle.classList.toggle('btn-secondary', window.chatSelectMode);
        }
    };

    window.onChatMessageClick = function (e, messageId) {
        if (!window.chatSelectMode) return;
        e.preventDefault();
        toggleChatMessageSelection(messageId);
    };

    window.toggleChatMessageSelection = function (messageId, forced) {
        if (!window.chatSelectMode) return;
        var id = String(messageId);
        var row = document.querySelector('[data-message-id="' + id + '"]');
        var checkbox = row ? row.querySelector('.msg-select input[type="checkbox"]') : null;
        var currentlySelected = window.selectedChatMessageIds.has(id);
        var shouldSelect = typeof forced === 'boolean' ? forced : !currentlySelected;
        if (shouldSelect) window.selectedChatMessageIds.add(id);
        else window.selectedChatMessageIds.delete(id);
        if (row) row.classList.toggle('selected', shouldSelect);
        if (checkbox) checkbox.checked = shouldSelect;
    };

    function clearChatSelection() {
        document.querySelectorAll('#chatMessagesArea [data-message-id].selected').forEach(function (r) {
            r.classList.remove('selected');
            var checkbox = r.querySelector('.msg-select input[type="checkbox"]');
            if (checkbox) checkbox.checked = false;
        });
        window.selectedChatMessageIds = new Set();
    }

    window.clearChatSelection = clearChatSelection;

    function initMoreMessagesIndicator() {
        var chatArea = document.getElementById('chatMessagesArea');
        var indicator = document.getElementById('moreMessagesIndicator');
        if (!chatArea || !indicator) return;
        chatArea.removeEventListener('scroll', updateMoreMessagesIndicator);
        chatArea.addEventListener('scroll', updateMoreMessagesIndicator);
        updateMoreMessagesIndicator();
    }

    window.openForwardSelectedMessages = function (conversationId) {
        if (!window.selectedChatMessageIds || window.selectedChatMessageIds.size === 0) {
            alert('Selecciona uno o mas mensajes para reenviar.');
            return;
        }
        var ids = Array.from(window.selectedChatMessageIds).join(',');
        var url = '/communications/conversation/' + conversationId + '/forward-messages-modal/?message_ids=' + encodeURIComponent(ids);
        fetch(url, { headers: { 'HX-Request': 'true' } })
            .then(function (r) { return r.text(); })
            .then(function (html) {
                var target = document.getElementById('modal-secondary-body');
                if (target) target.innerHTML = html;
                window.openModalSecondary();
            })
            .catch(function () { alert('No se pudo abrir el reenviado.'); });
    };

    window.submitForwardMessages = function (conversationId) {
        var recipientEl = document.getElementById('forwardRecipient');
        var idsEl = document.getElementById('forwardMessageIds');
        var csrfEl = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (!recipientEl || !idsEl) return;
        var formData = new FormData();
        formData.append('recipient_id', recipientEl.value);
        formData.append('message_ids', idsEl.value);
        formData.append('csrfmiddlewaretoken', csrfEl ? csrfEl.value : '');
        fetch('/communications/conversation/' + conversationId + '/forward-messages-send/', {
            method: 'POST',
            body: formData,
            headers: csrfEl ? { 'X-CSRFToken': csrfEl.value } : {}
        }).then(async function (r) {
            if (!r.ok) {
                var data = await r.json().catch(function () { return {}; });
                throw new Error(data.error || 'Error al reenviar');
            }
            window.closeModalSecondary();
            clearChatSelection();
            window.toggleChatSelectMode();
        }).catch(function (err) {
            alert(err.message);
        });
    };

    window.openConversationModal = function () {
        var originalChat = document.getElementById('chatMessagesArea');
        var modalArea = document.getElementById('modalMessagesArea');
        if (!originalChat || !modalArea) return;
        modalArea.innerHTML = originalChat.innerHTML;
        new bootstrap.Modal(document.getElementById('conversationModal')).show();
    };

    function bindFileInputs() {
        var waInput = document.getElementById('imageInputWhatsapp');
        if (waInput && !waInput.dataset.bound) {
            waInput.dataset.bound = '1';
            waInput.addEventListener('change', function () {
                if (this.files.length > 0) displayWhatsappFilePreview(this.files);
            });
        }
        function bindEmailFileInput(input, formContext) {
            if (!input || input.dataset.bound) return;
            input.dataset.bound = '1';
            if (!Array.isArray(input._commFiles)) input._commFiles = [];
            input.addEventListener('change', function () {
                var selected = Array.from(input.files || []);
                if (!selected.length) return;
                // Snapshot YA, después se vacía el input
                var copies = selected.slice();
                try { input.value = ''; } catch (e1) {}
                appendEmailFiles(input, copies, formContext);
            });
        }
        var composeModal = getEmailComposeModal();
        if (composeModal) {
            var modalInput = composeModal.querySelector('#imageInputEmail');
            bindEmailFileInput(modalInput, composeModal);
            if (modalInput) bindEmailDropAndPaste(composeModal, modalInput, composeModal);
        }
        var inlineForm = document.getElementById('emailFormInline');
        if (inlineForm) {
            var inlineInput = inlineForm.querySelector('#imageInputEmailInline');
            bindEmailFileInput(inlineInput, inlineForm);
            if (inlineInput) bindEmailDropAndPaste(inlineForm, inlineInput, inlineForm);
        }
    }

    function bindEmailForm(emailForm) {
        if (!emailForm || emailForm.dataset.bound) return;
        emailForm.dataset.bound = '1';
        emailForm.addEventListener('submit', function (e) {
            e.preventDefault();
            sendMessage(this, 'email');
        });
    }

    function bindForms() {
        var whatsappForm = document.getElementById('whatsappForm');
        var composeModal = getEmailComposeModal();
        var emailForm = composeModal ? composeModal.querySelector('#emailForm') : null;
        var emailFormInline = document.getElementById('emailFormInline');
        if (whatsappForm && !whatsappForm.dataset.bound) {
            whatsappForm.dataset.bound = '1';
            var waTextarea = whatsappForm.querySelector('textarea[name="message"]');
            if (waTextarea) {
                waTextarea.addEventListener('keydown', function (e) {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        whatsappForm.dispatchEvent(new Event('submit'));
                    }
                });
                waTextarea.addEventListener('paste', function (e) {
                    var items = (e.clipboardData || e.originalEvent.clipboardData).items;
                    for (var index in items) {
                        var item = items[index];
                        if (item.kind === 'file' && item.type.startsWith('image/')) {
                            var blob = item.getAsFile();
                            var file = new File([blob], 'screenshot_' + new Date().getTime() + '.png', { type: blob.type });
                            var input = document.getElementById('imageInputWhatsapp');
                            var dt = new DataTransfer();
                            Array.from(input.files).forEach(function (f) { dt.items.add(f); });
                            dt.items.add(file);
                            input.files = dt.files;
                            displayWhatsappFilePreview(input.files);
                        }
                    }
                });
            }
            whatsappForm.addEventListener('submit', function (e) {
                e.preventDefault();
                sendMessage(this, 'whatsapp');
            });
        }
        if (emailForm) bindEmailForm(emailForm);
        if (emailFormInline) bindEmailForm(emailFormInline);
    }

    function initConversationContent() {
        if (!isReady()) return;
        cleanupOrphanedEmailComposeModals();
        ensureWhatsappVoiceState();
        bindEmailComposeModal();
        bindFileInputs();
        bindForms();
        bindWhatsappTemplateCleanup();
        bindTemplateSelect();
        initMoreMessagesIndicator();
        initPolling();
    }
    window.__commInitConversationContent = initConversationContent;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initConversationContent);
    } else {
        initConversationContent();
    }

    document.body.addEventListener('htmx:afterSwap', function () {
        initConversationContent();
    });
})();
