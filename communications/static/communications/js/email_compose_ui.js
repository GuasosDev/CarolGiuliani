(function () {
    function qsa(root, selector) {
        return Array.prototype.slice.call((root || document).querySelectorAll(selector));
    }

    function setHidden(el, hidden) {
        if (!el) return;
        el.classList.toggle('d-none', !!hidden);
    }

    function initComposeForm(form) {
        if (!form || form.dataset.commEmailComposeUiBound === '1') return;
        form.dataset.commEmailComposeUiBound = '1';

        var rows = qsa(form, '[data-comm-email-row]');
        rows.forEach(function (row) {
            var type = row.dataset.commEmailRow;
            var input = row.querySelector('input');
            var toggle = form.querySelector('[data-comm-email-toggle="' + type + '"]');
            if (!input || !toggle) return;

            var hasValue = ((input.value || '').trim().length > 0);
            setHidden(row, !hasValue);
            setHidden(toggle, hasValue);

            toggle.addEventListener('click', function (e) {
                e.preventDefault();
                setHidden(row, false);
                setHidden(toggle, true);
                setTimeout(function () {
                    try {
                        input.focus();
                    } catch (err) {}
                }, 0);
            });

            input.addEventListener('input', function () {
                var nowHasValue = ((input.value || '').trim().length > 0);
                if (!nowHasValue) return;
                setHidden(toggle, true);
            });
        });
    }

    function init(root) {
        qsa(root || document, 'form.comm-email-compose-form').forEach(initComposeForm);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            init(document);
        });
    } else {
        init(document);
    }

    document.body.addEventListener('htmx:afterSwap', function (event) {
        init(event.target || document);
    });

    window.commInitEmailComposeUi = init;
})();

