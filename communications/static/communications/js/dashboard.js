(function () {
    const dashboard = document.querySelector('[data-comm-dashboard]');
    if (!dashboard) {
        return;
    }

    const listPanel = document.getElementById('conversation-list-panel');
    const detailPanel = document.getElementById('conversation-detail-panel');
    const splitter = document.getElementById('conversation-splitter');
    const backButton = document.getElementById('conversation-detail-back');
    const emptyDetailMarkup = detailPanel ? detailPanel.innerHTML : '';

    const minWidth = 240;
    const maxWidth = 520;
    const storageKey = 'communications.conversationListWidth';
    const mobileMedia = window.matchMedia('(max-width: 767.98px)');

    function isMobile() {
        return mobileMedia.matches;
    }

    function getCurrentListContainer() {
        return document.getElementById('dashboard-conversations-container');
    }

    function setDetailOpen(isOpen) {
        dashboard.classList.toggle('is-detail-open', Boolean(isOpen));

        if (Boolean(isOpen) && isMobile()) {
            window.requestAnimationFrame(function () {
                const mainPanel = document.querySelector('.comm-main-panel');
                if (mainPanel) {
                    mainPanel.scrollTop = 0;
                }
                if (detailPanel) {
                    detailPanel.scrollTop = 0;
                    detailPanel.scrollIntoView({ block: 'start', behavior: 'auto' });
                }
                window.scrollTo({ top: 0, behavior: 'auto' });
            });
        }

    }

    function resetDetailPanel() {
        if (!detailPanel) {
            return;
        }
        detailPanel.innerHTML = emptyDetailMarkup;
    }

    function clearSelection() {
        document.querySelectorAll('.conversation-item').forEach(function (el) {
            el.classList.remove('active', 'bg-light');
        });
    }

    function updateHeaderTitle(element, fallbackLabel) {
        const headerTitle = document.getElementById('dashboard-header-title');
        if (!headerTitle) {
            return;
        }

        const nameFromData = element ? element.getAttribute('data-contact-name') : '';
        if (nameFromData && nameFromData.trim()) {
            headerTitle.textContent = nameFromData.trim();
            return;
        }

        if (fallbackLabel) {
            headerTitle.textContent = fallbackLabel;
        }
    }

    function selectConversation(element, id) {
        try {
            clearSelection();

            if (!element && id) {
                element = document.querySelector('.conversation-item[data-id="' + id + '"]');
            }

            if (element) {
                element.classList.add('active', 'bg-light');
                updateHeaderTitle(element, 'Conversacion');
            }

            const url = new URL(window.location);
            url.searchParams.delete('email_message');
            url.searchParams.set('conversation', id);
            window.history.pushState({}, '', url);
            setDetailOpen(true);
        } catch (error) {
            console.error('Error in selectConversation:', error);
        }
    }

    function selectEmailMessage(element, id) {
        try {
            clearSelection();

            if (!element && id) {
                element = document.querySelector('.conversation-item[data-id="' + id + '"]');
            }

            if (element) {
                element.classList.add('active', 'bg-light');
                updateHeaderTitle(element, 'Email');
            }

            const url = new URL(window.location);
            url.searchParams.delete('conversation');
            url.searchParams.set('email_message', id);
            window.history.pushState({}, '', url);
            setDetailOpen(true);
        } catch (error) {
            console.error('Error in selectEmailMessage:', error);
        }
    }

    function renderLoadingState(message) {
        if (!detailPanel) {
            return;
        }

        detailPanel.innerHTML = [
            '<div class="d-flex flex-column align-items-center justify-content-center h-100 text-muted">',
            '<div class="spinner-border text-primary mb-3" role="status"></div>',
            '<p>' + message + '</p>',
            '</div>'
        ].join('');
    }

    function renderErrorState(title, message, retryCall) {
        if (!detailPanel) {
            return;
        }

        detailPanel.innerHTML = [
            '<div class="alert alert-danger m-4">',
            '<h4>' + title + '</h4>',
            '<p>' + message + '</p>',
            '<button class="btn btn-sm btn-outline-danger mt-3" onclick="' + retryCall + '">Reintentar</button>',
            '</div>'
        ].join('');
    }

    function csrfToken() {
        var m = document.cookie.match('(^|;) ?csrftoken=([^;]*)(;|$)');
        return m ? m[2] : '';
    }

    function clearUnreadStyles(el) {
        if (!el) return;
        el.classList.remove('has-unread');
        el.querySelectorAll('.comm-unread-pill').forEach(function (pill) {
            try { pill.remove(); } catch (e) {}
        });
        el.querySelectorAll('.comm-conv-name.is-unread').forEach(function (nameEl) {
            nameEl.classList.remove('is-unread');
        });
        // Fecha / preview vienen con fw-bold/fw-semibold en el HTML; hay que normalizarlos
        el.querySelectorAll('.fw-bold, .fw-semibold').forEach(function (node) {
            node.classList.remove('fw-bold', 'fw-semibold', 'text-dark');
            if (!node.classList.contains('text-muted') && !node.classList.contains('text-secondary')) {
                node.classList.add('text-muted');
            }
        });
    }

    function markListItemReadVisual(conversationId) {
        var el = null;
        if (conversationId) {
            el = document.querySelector('.conversation-item[data-id="' + conversationId + '"]');
        }
        if (!el) {
            el = document.querySelector('.conversation-item.active');
        }
        if (!el) {
            try {
                var fromUrl = new URLSearchParams(window.location.search).get('conversation');
                if (fromUrl) {
                    el = document.querySelector('.conversation-item[data-id="' + fromUrl + '"]');
                }
            } catch (e) {}
        }
        clearUnreadStyles(el);
    }

    function postMarkConversationRead(id) {
        if (!id) return;
        fetch('/communications/conversation/' + id + '/mark-read/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'X-CSRFToken': csrfToken(),
                'HX-Request': 'true'
            }
        }).then(function (r) {
            if (!r.ok) return;
            markListItemReadVisual(id);
            refreshConversationList();
        }).catch(function () {});
    }

    function requestDetail(url, loadingMessage, errorTitle, errorMessage, retryCall) {
        renderLoadingState(loadingMessage);
        setDetailOpen(true);

        var isConversationDetail = url.indexOf('/communications/conversation/') !== -1;

        if (typeof htmx !== 'undefined') {
            // htmx.ajax no siempre devuelve Promise; no usar .catch directo
            var settled = false;
            function cleanup() {
                document.body.removeEventListener('htmx:afterSwap', onOk);
                document.body.removeEventListener('htmx:afterSettle', onOk);
                document.body.removeEventListener('htmx:responseError', onHtmxError);
                document.body.removeEventListener('htmx:sendError', onHtmxError);
            }
            function onHtmxError(event) {
                if (settled) return;
                var detail = event && event.detail;
                var xhr = detail && detail.xhr;
                var path = (detail && (detail.pathInfo && detail.pathInfo.requestPath)) || (xhr && xhr.responseURL) || '';
                if (path && path.indexOf(url.split('?')[0]) === -1 && url.indexOf(path) === -1) {
                    return;
                }
                settled = true;
                cleanup();
                console.error('HTMX Error:', detail || event);
                renderErrorState(errorTitle, errorMessage, retryCall);
            }
            function onOk(event) {
                if (!event.detail || !event.detail.target || event.detail.target.id !== 'conversation-detail-panel') {
                    return;
                }
                if (settled) return;
                settled = true;
                cleanup();
                if (isConversationDetail) {
                    markListItemReadVisual();
                    // Diferir un tick: el servidor ya marcó leído en esta respuesta
                    window.setTimeout(function () {
                        markListItemReadVisual();
                        refreshConversationList();
                    }, 50);
                }
            }
            // Registrar ANTES de ajax: si no, afterSwap puede dispararse sin listener
            document.body.addEventListener('htmx:afterSwap', onOk);
            document.body.addEventListener('htmx:afterSettle', onOk);
            document.body.addEventListener('htmx:responseError', onHtmxError);
            document.body.addEventListener('htmx:sendError', onHtmxError);
            htmx.ajax('GET', url, {
                target: '#conversation-detail-panel',
                swap: 'innerHTML'
            });
            return;
        }

        fetch(url, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'HX-Request': 'true'
            }
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.text();
            })
            .then(function (html) {
                if (detailPanel) {
                    detailPanel.innerHTML = html;
                }
                if (isConversationDetail) {
                    markListItemReadVisual();
                    refreshConversationList();
                }
            })
            .catch(function (error) {
                renderErrorState(errorTitle, 'No se pudo cargar el detalle. ' + error.message, retryCall);
            });
    }

    function loadConversation(element, id) {
        if (window.conversationPollInterval) {
            clearInterval(window.conversationPollInterval);
            window.conversationPollInterval = null;
        }

        selectConversation(element, id);
        var item = element || document.querySelector('.conversation-item[data-id="' + id + '"]');
        clearUnreadStyles(item);
        // Marca leído ya (no depender solo del GET del detalle + refresh)
        postMarkConversationRead(id);
        requestDetail(
            '/communications/conversation/' + id + '/?partial=true',
            'Cargando conversacion...',
            'Error al cargar el chat',
            'No se pudo cargar la conversacion. Por favor intenta nuevamente.',
            "loadConversation(null, '" + id + "')"
        );
    }

    function loadEmailMessage(element, id) {
        // Marcar la conversación seleccionada
        if (element) {
            document.querySelectorAll('.conversation-item.active')
                .forEach(el => el.classList.remove('active'));

            element.classList.add('active');
        }

        if (window.conversationPollInterval) {
            clearInterval(window.conversationPollInterval);
            window.conversationPollInterval = null;
        }

        selectEmailMessage(element, id);

        requestDetail(
            '/communications/email-message/' + id + '/?partial=true',
            'Cargando email...',
            'Error al cargar el email',
            'No se pudo cargar el email. Por favor intenta nuevamente.',
            "loadEmailMessage(null, '" + id + "')"
        );
    }

    function refreshConversationList() {
        const container = getCurrentListContainer();
        if (!container || typeof htmx === 'undefined') {
            return;
        }

        var path = window.location.pathname + window.location.search;
        var sep = path.indexOf('?') === -1 ? '?' : '&';
        path = path + sep + '_ts=' + Date.now();
        htmx.ajax('GET', path, {
            source: container,
            target: '#dashboard-conversations-container',
            swap: 'outerHTML',
            select: '#dashboard-conversations-container'
        });
    }

    function restoreSelectionFromUrl(autoLoad) {
        const params = new URLSearchParams(window.location.search);
        const conversationId = params.get('conversation');
        const emailMessageId = params.get('email_message');

        if (conversationId) {
            const el = document.querySelector('.conversation-item[data-id="' + conversationId + '"]');
            if (autoLoad && el) {
                el.click();
            } else if (autoLoad) {
                loadConversation(null, conversationId);
            } else if (el) {
                el.classList.add('active', 'bg-light');
                setDetailOpen(true);
            }
            return;
        }

        if (emailMessageId) {
            const el = document.querySelector('.conversation-item[data-id="' + emailMessageId + '"]');
            if (autoLoad && el) {
                el.click();
            } else if (autoLoad) {
                loadEmailMessage(null, emailMessageId);
            } else if (el) {
                el.classList.add('active', 'bg-light');
                setDetailOpen(true);
            }
            return;
        }

        clearSelection();
        setDetailOpen(false);
        resetDetailPanel();
    }

    function closeMobileDetail() {
        const url = new URL(window.location);
        url.searchParams.delete('conversation');
        url.searchParams.delete('email_message');
        window.history.pushState({}, '', url);
        clearSelection();
        resetDetailPanel();
        setDetailOpen(false);
    }

    function initSplitter() {
        if (!listPanel || !splitter) {
            return;
        }

        const savedWidth = Number(window.localStorage.getItem(storageKey));
        if (!Number.isNaN(savedWidth) && savedWidth >= minWidth && savedWidth <= maxWidth && !isMobile()) {
            listPanel.style.width = savedWidth + 'px';
        }

        let startX = 0;
        let startWidth = 0;
        let dragging = false;

        splitter.addEventListener('pointerdown', function (event) {
            if (isMobile()) {
                return;
            }

            dragging = true;
            startX = event.clientX;
            startWidth = listPanel.getBoundingClientRect().width;
            document.body.classList.add('comm-resizing');
            splitter.setPointerCapture(event.pointerId);
            event.preventDefault();
        });

        splitter.addEventListener('pointermove', function (event) {
            if (!dragging) {
                return;
            }

            const delta = event.clientX - startX;
            const nextWidth = Math.min(maxWidth, Math.max(minWidth, Math.round(startWidth + delta)));
            listPanel.style.width = nextWidth + 'px';
        });

        function stopDragging(event) {
            if (!dragging) {
                return;
            }

            dragging = false;
            document.body.classList.remove('comm-resizing');
            window.localStorage.setItem(storageKey, String(Math.round(listPanel.getBoundingClientRect().width)));
            if (event && event.pointerId != null) {
                splitter.releasePointerCapture(event.pointerId);
            }
        }

        splitter.addEventListener('pointerup', stopDragging);
        splitter.addEventListener('pointercancel', stopDragging);
    }

    function handleViewportChange() {
        if (!isMobile()) {
            dashboard.classList.remove('is-detail-open');
            return;
        }

        const params = new URLSearchParams(window.location.search);
        const hasSelection = Boolean(params.get('conversation') || params.get('email_message'));
        setDetailOpen(hasSelection);
    }

    function closeConversationDetail() {
        clearSelection();
        resetDetailPanel();
        setDetailOpen(false);
        try {
            var url = new URL(window.location.href);
            url.searchParams.delete('conversation');
            var next = url.pathname + (url.searchParams.toString() ? '?' + url.searchParams.toString() : '');
            window.history.replaceState({}, '', next);
        } catch (e) {}
    }

    document.body.addEventListener('commRefreshConversationList', refreshConversationList);
    document.body.addEventListener('commCloseConversationDetail', closeConversationDetail);

    document.body.addEventListener('htmx:afterSwap', function (event) {
        if (!event.detail || !event.detail.target) {
            return;
        }

        if (event.detail.target.id === 'dashboard-conversations-container') {
            restoreSelectionFromUrl(false);
            // Por si el HTML vino con "no leído" viejo: el chat abierto ya está leído
            markListItemReadVisual();
            return;
        }

        if (event.detail.target.id === 'conversation-detail-panel') {
            setDetailOpen(true);
            markListItemReadVisual();
            // HX-Trigger del detalle también dispara refresh; blindaje visual extra
            window.setTimeout(function () { markListItemReadVisual(); }, 80);
        }
    });

    document.addEventListener('DOMContentLoaded', function () {
        restoreSelectionFromUrl(true);
        handleViewportChange();
    });

    if (backButton) {
        backButton.addEventListener('click', closeMobileDetail);
    }

    if (typeof mobileMedia.addEventListener === 'function') {
        mobileMedia.addEventListener('change', handleViewportChange);
    }

    window.addEventListener('popstate', function () {
        restoreSelectionFromUrl(false);
        handleViewportChange();
    });

    initSplitter();
    handleViewportChange();

    window.loadConversation = loadConversation;
    window.loadEmailMessage = loadEmailMessage;
    window.selectConversation = selectConversation;
    window.selectEmailMessage = selectEmailMessage;
})();

