(function () {
    function initTransferSuccess() {
        document.querySelectorAll('[data-transfer-success]').forEach(function (el) {
            if (el.dataset.transferSuccessBound === '1') return;
            el.dataset.transferSuccessBound = '1';
            var delayMs = parseInt(el.dataset.delayMs || '1000', 10);
            setTimeout(function () {
                try {
                    if (typeof window.closeModal === 'function') {
                        window.closeModal();
                    }
                } catch (e) {}
                window.location.reload();
            }, Number.isFinite(delayMs) ? delayMs : 1000);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTransferSuccess);
    } else {
        initTransferSuccess();
    }

    document.body.addEventListener('htmx:afterSwap', initTransferSuccess);
})();
