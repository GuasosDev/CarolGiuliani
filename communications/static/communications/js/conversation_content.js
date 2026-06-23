(function () {
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

    window.commMailOpenCompose = function (mode, options) {
        var modalEl = document.getElementById('emailComposeModal');
        if (!modalEl || typeof bootstrap === 'undefined') return;
        options = options || {};
        mode = mode || 'reply';
        var form = document.getElementById('emailForm');
        var to = document.getElementById('emailToInput');
        var subj = document.getElementById('emailSubjectInput');
        var body = document.getElementById('emailBodyDiv');
        var convInput = document.getElementById('emailConversationIdInput');
        var title = document.getElementById('emailComposeModalLabel');
        var ccIn = document.getElementById('emailCcInput');
        var bccIn = document.getElementById('emailBccInput');
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
            var srcInNew = document.getElementById('emailSourceEmailMessageIdInput');
            if (srcInNew) srcInNew.value = '';
            if (ccIn) ccIn.value = '';
            if (bccIn) bccIn.value = '';
            setTitle('fas fa-pen', 'Redactar correo');
        } else if (mode === 'forward') {
            if (to) to.value = '';
            if (subj) subj.value = replySubject ? ('Fwd: ' + replySubject) : 'Fwd: ';
            if (body) body.innerHTML = '<p></p><p>---------- Mensaje reenviado ----------</p>';
            if (convInput) {
                convInput.value = '';
                convInput.removeAttribute('name');
            }
            var srcId = form && form.getAttribute('data-forward-email-message-id') ? String(form.getAttribute('data-forward-email-message-id')).trim() : '';
            var srcIn = document.getElementById('emailSourceEmailMessageIdInput');
            if (srcIn) srcIn.value = srcId;
            if (ccIn) ccIn.value = '';
            if (bccIn) bccIn.value = '';
            setTitle('fas fa-share', 'Reenviar correo');
        } else if (mode === 'reply-all') {
            if (to) to.value = replyTo;
            if (subj) subj.value = replySubject ? ('Re: ' + replySubject) : 'Re: ';
            if (body) body.innerHTML = '';
            if (convInput) {
                convInput.setAttribute('name', 'conversation_id');
                convInput.value = convIdDefault;
            }
            var srcInAll = document.getElementById('emailSourceEmailMessageIdInput');
            if (srcInAll) srcInAll.value = '';
            if (ccIn) ccIn.value = replyCc;
            if (bccIn) bccIn.value = '';
            setTitle('fas fa-reply-all', 'Responder a todos');
        } else {
            if (to) to.value = replyTo;
            if (subj) subj.value = replySubject ? ('Re: ' + replySubject) : 'Re: ';
            if (body) body.innerHTML = '';
            if (convInput) {
                convInput.setAttribute('name', 'conversation_id');
                convInput.value = convIdDefault;
            }
            var srcInReply = document.getElementById('emailSourceEmailMessageIdInput');
            if (srcInReply) srcInReply.value = '';
            if (ccIn) ccIn.value = '';
            if (bccIn) bccIn.value = '';
            setTitle('fas fa-reply', 'Responder');
        }
        bootstrap.Modal.getOrCreateInstance(modalEl).show();
    };

    function tryOpenComposeFromQuery() {
        try {
            var u = new URL(window.location.href);
            var c = u.searchParams.get('compose');
            if (c !== '1' && c !== 'new') return;
            if (!document.getElementById('emailForm')) return;
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
        var modalEl = document.getElementById('emailComposeModal');
        if (!modalEl || modalEl.dataset.commBound) return;
        modalEl.dataset.commBound = '1';
        modalEl.addEventListener('hidden.bs.modal', function () {
            var convIn = document.getElementById('emailConversationIdInput');
            var frm = document.getElementById('emailForm');
            if (convIn && frm) {
                convIn.setAttribute('name', 'conversation_id');
                var defId = frm.getAttribute('data-conversation-id');
                convIn.value = defId != null ? String(defId) : '';
            }
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
            var emailBodyDiv = document.getElementById('emailBodyDiv');
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
        var emailInput = document.getElementById('imageInputEmail');
        var whatsappInput = document.getElementById('imageInputWhatsapp');
        if (whatsappContainer && !whatsappContainer.classList.contains('d-none') && whatsappInput) {
            whatsappInput.click();
        } else if (emailInput) {
            emailInput.click();
        }
    };

    function displayEmailFilePreview(files) {
        var preview = document.getElementById('emailFilePreview');
        if (!preview) return;
        preview.innerHTML = '';
        Array.from(files).forEach(function (file, index) {
            var fileItem = document.createElement('div');
            fileItem.className = 'd-flex align-items-center justify-content-between p-2 bg-light rounded mb-1';
            fileItem.style.cursor = 'pointer';
            fileItem.draggable = true;
            var size = formatFileSize(file.size);
            if (file.type.startsWith('image/')) {
                var reader = new FileReader();
                reader.onload = function (e) {
                    fileItem.innerHTML = '<div class="d-flex align-items-center flex-grow-1" onclick="handleFileClick(' + index + ')">' +
                        '<img src="' + e.target.result + '" style="width: 40px; height: 40px; object-fit: cover; border-radius: 4px;" class="me-2">' +
                        '<div><div class="small fw-bold">' + file.name + '</div><div class="text-muted" style="font-size: 0.7rem;">' + size + '</div></div></div>' +
                        '<div class="d-flex gap-1">' +
                        '<button type="button" class="btn btn-sm btn-outline-primary" onclick="event.preventDefault(); openUploadPreview(document.getElementById(\'imageInputEmail\').files[' + index + '], ' + index + ')" title="Vista previa"><i class="fas fa-eye"></i></button>' +
                        '<button type="button" class="btn btn-sm btn-outline-danger" onclick="removeEmailFile(' + index + ')"><i class="fas fa-times"></i></button>' +
                        '</div>';
                };
                reader.readAsDataURL(file);
            } else {
                var icon = 'fas fa-file text-secondary';
                if (file.type.includes('pdf')) icon = 'fas fa-file-pdf text-danger';
                else if (file.type.includes('word') || file.type.includes('document')) icon = 'fas fa-file-word text-primary';
                else if (file.type.includes('excel') || file.type.includes('spreadsheet')) icon = 'fas fa-file-excel text-success';
                fileItem.innerHTML = '<div class="d-flex align-items-center flex-grow-1" onclick="handleFileClick(' + index + ')">' +
                    '<i class="' + icon + ' me-2"></i><div><div class="small fw-bold">' + file.name + '</div><div class="text-muted" style="font-size: 0.7rem;">' + size + '</div></div></div>' +
                    '<div class="d-flex gap-1">' +
                    '<button type="button" class="btn btn-sm btn-outline-primary" onclick="event.preventDefault(); openUploadPreview(document.getElementById(\'imageInputEmail\').files[' + index + '], ' + index + ')" title="Vista previa"><i class="fas fa-eye"></i></button>' +
                    '<button type="button" class="btn btn-sm btn-outline-danger" onclick="removeEmailFile(' + index + ')"><i class="fas fa-times"></i></button>' +
                    '</div>';
            }
            fileItem.addEventListener('dragstart', function (e) {
                e.dataTransfer.effectAllowed = 'copy';
                e.dataTransfer.setData('text/plain', file.name);
            });
            preview.appendChild(fileItem);
        });
    }

    window.removeEmailFile = function (index) {
        var input = document.getElementById('imageInputEmail');
        if (!input) return;
        var dt = new DataTransfer();
        var files = Array.from(input.files);
        if (index < 0 || index >= files.length) return;
        files.forEach(function (file, i) { if (i !== index) dt.items.add(file); });
        input.files = dt.files;
        if (input.files.length > 0) displayEmailFilePreview(input.files);
        else document.getElementById('emailFilePreview').innerHTML = '';
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
            var emailBodyDiv = document.getElementById('emailBodyDiv');
            var emailBodyInput = document.getElementById('emailBodyInput');
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
                if (textContent.trim() === '' && document.getElementById('imageInputEmail').files.length === 0) {
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
            var fileInputEmail = document.getElementById('imageInputEmail');
            if (fileInputEmail && fileInputEmail.files.length > 0) {
                formData.delete('attachments');
                Array.from(fileInputEmail.files).forEach(function (file) { formData.append('attachments', file); });
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
            if (channel === 'whatsapp') {
                var messageTextarea = form.querySelector('textarea[name="message"]');
                if (messageTextarea) messageTextarea.value = '';
                var waInput = document.getElementById('imageInputWhatsapp');
                if (waInput) waInput.value = '';
                var waPreview = document.getElementById('whatsappFilePreview');
                if (waPreview) waPreview.innerHTML = '';
                clearWhatsappVoiceNote();
            } else {
                var bodyDiv = document.getElementById('emailBodyDiv');
                var bodyInput = document.getElementById('emailBodyInput');
                if (bodyDiv) bodyDiv.innerHTML = '';
                if (bodyInput) bodyInput.value = '';
                var subjectInput = form.querySelector('input[name="subject"]');
                if (subjectInput) subjectInput.value = '';
                var emInput = document.getElementById('imageInputEmail');
                if (emInput) emInput.value = '';
                var emPreview = document.getElementById('emailFilePreview');
                if (emPreview) emPreview.innerHTML = '';
            }

            refreshMessages();

            if (channel === 'email') {
                try {
                    var modalEl = document.getElementById('emailComposeModal');
                    if (modalEl && typeof bootstrap !== 'undefined') {
                        var inst = bootstrap.Modal.getInstance(modalEl) || bootstrap.Modal.getOrCreateInstance(modalEl);
                        inst.hide();
                    }
                } catch (e) {}
            }

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
            alert('No se pudo encontrar el mensaje para imprimir');
            return;
        }
        var headerElement = messageElement.querySelector('.msg-header');
        var contentElement = messageElement.querySelector('.msg-bubble');
        var headerText = headerElement ? headerElement.textContent.trim() : '';
        var contentText = '';
        if (contentElement) {
            var tempDiv = document.createElement('div');
            tempDiv.innerHTML = contentElement.innerHTML;
            contentText = (tempDiv.textContent || tempDiv.innerText || '').trim();
        }
        var printWindow = window.open('', '_blank', 'width=800,height=600');
        var printHTML = '<!DOCTYPE html><html><head><title>Mensaje #' + messageId + '</title>' +
            '<style>body{font-family:Arial,sans-serif;margin:20px;line-height:1.5}.header{font-weight:bold;margin-bottom:15px;padding:10px;background:#f5f5f5;border-radius:5px}.content{margin-bottom:20px;white-space:pre-wrap}.footer{font-size:12px;color:#666;margin-top:20px}@media print{body{margin:15px}}</style>' +
            '</head><body><h2>Mensaje #' + messageId + '</h2><div class="header">' + headerText + '</div><div class="content">' + contentText + '</div><div class="footer">Impreso el ' + new Date().toLocaleString() + '</div></body></html>';
        printWindow.document.write(printHTML);
        printWindow.document.close();
        printWindow.print();
    };

    window.downloadMessage = function (messageId, messageType) {
        var messageElement = document.querySelector('[data-message-id="' + messageId + '"]');
        if (!messageElement) {
            alert('No se pudo encontrar el mensaje para descargar');
            return;
        }
        var headerElement = messageElement.querySelector('.msg-header');
        var contentElement = messageElement.querySelector('.msg-bubble');
        var messageText = 'Mensaje #' + messageId + '\nTipo: ' + messageType + '\nFecha: ' + new Date().toLocaleString() + '\n' + '='.repeat(50) + '\n\n';
        if (headerElement) messageText += headerElement.textContent.trim() + '\n\n';
        if (contentElement) {
            var tempDiv = document.createElement('div');
            tempDiv.innerHTML = contentElement.innerHTML;
            messageText += (tempDiv.textContent || tempDiv.innerText || '').trim();
        }
        try {
            var blob = new Blob([messageText], { type: 'text/plain;charset=utf-8' });
            var url = window.URL.createObjectURL(blob);
            var a = document.createElement('a');
            a.href = url;
            a.download = 'mensaje_' + messageId + '_' + messageType + '_' + new Date().getTime() + '.txt';
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
        } else if (['pdf'].includes(fileExtension)) {
            previewHTML = '<div class="text-center p-4"><i class="fas fa-file-pdf" style="font-size: 4rem; color: #dc3545; margin-bottom: 20px;"></i><h5 class="mb-3">' + fileName + '</h5><p class="text-muted">Vista previa de PDF no disponible. Haz clic en "Descargar" para ver el archivo completo.</p></div>';
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

    window.openUploadPreview = function (file, index) {
        if (!file) return;
        var modal = document.getElementById('uploadPreviewModal');
        var fileNameElement = document.getElementById('uploadPreviewFileName');
        var previewContent = document.getElementById('uploadPreviewContent');
        if (!modal || !fileNameElement || !previewContent) return;
        window.currentUploadFileIndex = index;
        fileNameElement.textContent = file.name;
        var fileExtension = file.name.split('.').pop().toLowerCase();
        var previewHTML = '';
        if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(fileExtension)) {
            previewHTML = '<img src="' + URL.createObjectURL(file) + '" alt="' + file.name + '" style="max-width: 100%; max-height: 500px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">';
        } else if (['mp4', 'webm', 'ogg'].includes(fileExtension)) {
            previewHTML = '<video controls style="max-width: 100%; max-height: 500px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);"><source src="' + URL.createObjectURL(file) + '">Tu navegador no soporta la reproduccion de video.</video>';
        } else if (['mp3', 'wav', 'ogg', 'm4a', 'opus'].includes(fileExtension)) {
            previewHTML = '<div class="text-center p-4"><i class="fas fa-file-audio" style="font-size: 4rem; color: #ff6b35; margin-bottom: 20px;"></i><h5 class="mb-3">' + file.name + '</h5><p class="text-muted mb-3">Tamaño: ' + formatFileSize(file.size) + '</p><audio controls class="w-100"><source src="' + URL.createObjectURL(file) + '">Tu navegador no soporta la reproduccion de audio.</audio></div>';
        } else if (['pdf'].includes(fileExtension)) {
            previewHTML = '<div class="text-center p-4"><i class="fas fa-file-pdf" style="font-size: 4rem; color: #dc3545; margin-bottom: 20px;"></i><h5 class="mb-3">' + file.name + '</h5><p class="text-muted mb-3">Tamaño: ' + formatFileSize(file.size) + '</p><p class="text-muted">Vista previa de PDF no disponible. Este archivo se enviara correctamente.</p></div>';
        } else {
            previewHTML = '<div class="text-center p-4"><i class="fas fa-file" style="font-size: 4rem; color: #6c757d; margin-bottom: 20px;"></i><h5 class="mb-3">' + file.name + '</h5><p class="text-muted mb-3">Tamaño: ' + formatFileSize(file.size) + '</p><p class="text-muted">Vista previa no disponible para este tipo de archivo. Este archivo se enviara correctamente.</p></div>';
        }
        previewContent.innerHTML = previewHTML;
        ensureBootstrapModalRoot(modal);
        bootstrap.Modal.getOrCreateInstance(modal).show();
    };

    window.closeUploadPreview = function () {
        var modal = document.getElementById('uploadPreviewModal');
        if (!modal) return;
        var modalInstance = bootstrap.Modal.getInstance(modal);
        if (modalInstance) modalInstance.hide();
    };

    window.removeUploadFile = function () {
        if (window.currentUploadFileIndex === undefined) return;
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
        var emailInput = document.getElementById('imageInputEmail');
        if (emailInput && !emailInput.dataset.bound) {
            emailInput.dataset.bound = '1';
            emailInput.addEventListener('change', function () {
                if (this.files.length > 0) displayEmailFilePreview(this.files);
            });
        }
    }

    function bindForms() {
        var whatsappForm = document.getElementById('whatsappForm');
        var emailForm = document.getElementById('emailForm');
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
        if (emailForm && !emailForm.dataset.bound) {
            emailForm.dataset.bound = '1';
            var emailBodyDiv = document.getElementById('emailBodyDiv');
            if (emailBodyDiv) {
                emailBodyDiv.addEventListener('paste', function (e) {
                    var items = (e.clipboardData || e.originalEvent.clipboardData).items;
                    for (var index in items) {
                        var item = items[index];
                        if (item.kind === 'file' && item.type.startsWith('image/')) {
                            var blob = item.getAsFile();
                            var file = new File([blob], 'screenshot_' + new Date().getTime() + '.png', { type: blob.type });
                            var input = document.getElementById('imageInputEmail');
                            var dt = new DataTransfer();
                            Array.from(input.files).forEach(function (f) { dt.items.add(f); });
                            dt.items.add(file);
                            input.files = dt.files;
                            displayEmailFilePreview(input.files);
                        }
                    }
                });
            }
            emailForm.addEventListener('submit', function (e) {
                e.preventDefault();
                sendMessage(this, 'email');
            });
        }
    }

    function initConversationContent() {
        if (!isReady()) return;
        ensureWhatsappVoiceState();
        bindEmailComposeModal();
        bindFileInputs();
        bindForms();
        bindWhatsappTemplateCleanup();
        bindTemplateSelect();
        initMoreMessagesIndicator();
        initPolling();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initConversationContent);
    } else {
        initConversationContent();
    }

    document.body.addEventListener('htmx:afterSwap', function () {
        initConversationContent();
    });
})();
