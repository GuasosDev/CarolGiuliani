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

    function requestDetail(url, loadingMessage, errorTitle, errorMessage, retryCall) {
        renderLoadingState(loadingMessage);
        setDetailOpen(true);

        if (typeof htmx !== 'undefined') {
            htmx.ajax('GET', url, {
                target: '#conversation-detail-panel',
                swap: 'innerHTML'
            }).catch(function (error) {
                console.error('HTMX Error:', error);
                renderErrorState(errorTitle, errorMessage, retryCall);
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

        const path = window.location.pathname + window.location.search;
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

    document.body.addEventListener('commRefreshConversationList', refreshConversationList);

    document.body.addEventListener('htmx:afterSwap', function (event) {
        if (!event.detail || !event.detail.target) {
            return;
        }

        if (event.detail.target.id === 'dashboard-conversations-container') {
            restoreSelectionFromUrl(false);
            return;
        }

        if (event.detail.target.id === 'conversation-detail-panel') {
            setDetailOpen(true);
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

