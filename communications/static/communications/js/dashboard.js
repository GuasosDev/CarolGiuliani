(function () {
    const dashboard = document.querySelector('[data-comm-dashboard]');
    if (!dashboard) {
        return;
    }

    // #region debug-point A:debug-report
    function debugReport(hypothesisId, msg, data) {
        fetch('http://127.0.0.1:7777/event', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                sessionId: 'console-errors-menu-swap',
                runId: 'pre-fix',
                hypothesisId: hypothesisId,
                location: 'communications/static/communications/js/dashboard.js',
                msg: '[DEBUG] ' + msg,
                data: data || {},
                ts: Date.now()
            })
        }).catch(function () {});
    }
    // #endregion

    const listPanel = document.getElementById('conversation-list-panel');
    const detailPanel = document.getElementById('conversation-detail-panel');
    const splitter = document.getElementById('conversation-splitter');
    const backButton = document.getElementById('conversation-detail-back');
    const emptyDetailMarkup = detailPanel ? detailPanel.innerHTML : '';

    const minWidth = 240;
    const maxWidth = 520;
    const storageKey = 'communications.conversationListWidth';
    const mobileMedia = window.matchMedia('(max-width: 767.98px)');

    // #region debug-point B:init-state
    debugReport('B', 'dashboard-init', {
        hasDashboard: Boolean(dashboard),
        hasListPanel: Boolean(listPanel),
        hasDetailPanel: Boolean(detailPanel),
        hasSplitter: Boolean(splitter),
        hasBackButton: Boolean(backButton),
        width: window.innerWidth,
        height: window.innerHeight,
        isMobile: mobileMedia.matches
    });
    // #endregion

    // #region debug-point C:window-error
    window.addEventListener('error', function (event) {
        debugReport('C', 'window-error', {
            message: event.message,
            filename: event.filename,
            lineno: event.lineno,
            colno: event.colno
        });
    });
    // #endregion

    // #region debug-point D:unhandled-rejection
    window.addEventListener('unhandledrejection', function (event) {
        debugReport('D', 'unhandled-rejection', {
            reason: String(event.reason)
        });
    });
    // #endregion

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

        // #region debug-point F:detail-open-state
        debugReport('F', 'detail-open-state', {
            isOpen: Boolean(isOpen),
            shellClasses: dashboard.className,
            isMobile: mobileMedia.matches
        });
        // #endregion
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

        // #region debug-point G:request-detail
        debugReport('G', 'request-detail', {
            url: url,
            loadingMessage: loadingMessage,
            isMobile: mobileMedia.matches
        });
        // #endregion

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

        // #region debug-point H:load-conversation
        debugReport('H', 'load-conversation', {
            id: id,
            isMobile: mobileMedia.matches
        });
        // #endregion

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
        if (window.conversationPollInterval) {
            clearInterval(window.conversationPollInterval);
            window.conversationPollInterval = null;
        }

        // #region debug-point I:load-email-message
        debugReport('I', 'load-email-message', {
            id: id,
            isMobile: mobileMedia.matches
        });
        // #endregion

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

            // #region debug-point J:detail-after-swap
            window.setTimeout(function () {
                const panel = document.getElementById('conversation-detail-panel');
                const wrap = document.querySelector('.comm-detail-panel-wrap');
                const panelStyle = panel ? window.getComputedStyle(panel) : null;
                const wrapStyle = wrap ? window.getComputedStyle(wrap) : null;
                debugReport('J', 'detail-after-swap', {
                    childCount: panel ? panel.children.length : 0,
                    panelDisplay: panelStyle ? panelStyle.display : null,
                    panelOverflowX: panelStyle ? panelStyle.overflowX : null,
                    panelOverflowY: panelStyle ? panelStyle.overflowY : null,
                    panelWidth: panel ? panel.getBoundingClientRect().width : null,
                    panelHeight: panel ? panel.getBoundingClientRect().height : null,
                    wrapDisplay: wrapStyle ? wrapStyle.display : null,
                    wrapWidth: wrap ? wrap.getBoundingClientRect().width : null,
                    wrapHeight: wrap ? wrap.getBoundingClientRect().height : null,
                    isMobile: mobileMedia.matches
                });
            }, 120);
            // #endregion
        }
    });

    document.addEventListener('DOMContentLoaded', function () {
        restoreSelectionFromUrl(true);
        handleViewportChange();

        // #region debug-point E:sidebar-layout
        window.setTimeout(function () {
            const sidebar = document.querySelector('.comm-sidebar-nav');
            const labels = Array.prototype.map.call(document.querySelectorAll('.comm-sidebar-nav .sidebar-icon-btn span:not(.sidebar-badge)'), function (node) {
                return (node.textContent || '').trim();
            });
            const sidebarStyle = sidebar ? window.getComputedStyle(sidebar) : null;
            debugReport('E', 'sidebar-layout', {
                labels: labels,
                childCount: sidebar ? sidebar.children.length : 0,
                position: sidebarStyle ? sidebarStyle.position : null,
                flexDirection: sidebarStyle ? sidebarStyle.flexDirection : null,
                overflowX: sidebarStyle ? sidebarStyle.overflowX : null,
                overflowY: sidebarStyle ? sidebarStyle.overflowY : null,
                bottom: sidebarStyle ? sidebarStyle.bottom : null,
                left: sidebarStyle ? sidebarStyle.left : null,
                right: sidebarStyle ? sidebarStyle.right : null,
                isMobile: mobileMedia.matches
            });
        }, 150);
        // #endregion
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
