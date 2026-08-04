function openModal() {
    document.getElementById('modal').style.display = 'block';
}

function closeModal() {
    var modal = document.getElementById('modal');
    if (!modal) return;
    modal.removeAttribute('data-no-backdrop-close');
    modal.style.display = 'none';
    var body = document.getElementById('modal-body');
    if (body) body.innerHTML = '';
}

function openModalSecondary() {
    document.getElementById('modal-secondary').style.display = 'block';
}

function closeModalSecondary() {
    var modalSecondary = document.getElementById('modal-secondary');
    if (!modalSecondary) return;
    modalSecondary.removeAttribute('data-no-backdrop-close');
    modalSecondary.style.display = 'none';
    var body = document.getElementById('modal-secondary-body');
    if (body) body.innerHTML = '';
}

function modalBlocksOutsideClose(modalEl) {
    if (!modalEl) return false;
    if (modalEl.getAttribute('data-no-backdrop-close') === '1') return true;
    if (modalEl.querySelector('#emailForm, #emailFormGlobal, form[action*="send_email"], [data-comm-email-compose]')) return true;
    if (modalEl.querySelector('#clientEmailComposeTitle')) return true;
    var body = modalEl.querySelector('#modal-body, #modal-secondary-body') || modalEl;
    if (body && /Abriendo redacc/i.test(body.textContent || '')) return true;
    return false;
}

// Nunca cerrar al click afuera si hay un compose de correo abierto
window.onclick = function (event) {
    var modal = document.getElementById('modal');
    var modalSecondary = document.getElementById('modal-secondary');
    if (event.target === modal) {
        if (modalBlocksOutsideClose(modal)) return;
        closeModal();
    }
    if (event.target === modalSecondary) {
        if (modalBlocksOutsideClose(modalSecondary)) return;
        closeModalSecondary();
    }
};

document.body.addEventListener('htmx:afterSwap', function (event) {
    var target = event.detail && event.detail.target;
    if (!target) return;
    ['modal', 'modal-secondary'].forEach(function (id) {
        var m = document.getElementById(id);
        if (m && m.contains(target) && modalBlocksOutsideClose(m)) {
            m.setAttribute('data-no-backdrop-close', '1');
        }
    });
});

// HTMX listeners to handle closing modal on success if needed, or simple redirect
// Handle refreshing list from generic forms
document.body.addEventListener('refreshList', function () {
    closeModal();
    closeModalSecondary();
    // If datatable exists, reload it? Or just reload page?
    // Ideally reload datatable via ajax if possible, but full page reload is safer for now if not using ajax source
    if ($.fn.DataTable.isDataTable('#datatable')) {
        // For server-side rendering list, we need to visit page again or swap body?
        // Since we don't have exact url to swap list only easily without htmx-boost, let's reload
        location.reload();
    } else {
        location.reload();
    }
});

document.body.addEventListener('reloadPage', function () {
    closeModal();
    closeModalSecondary();
    location.reload();
});

// Fallback: If 204 is returned but event doesn't trigger (sometimes happens if parsed differently)
document.body.addEventListener('htmx:afterRequest', function (evt) {
    if (evt.detail.successful && evt.detail.xhr.status === 204) {
        var el = evt.detail.elt;
        if (el && (el.dataset.noReload === 'true' || (el.closest && el.closest('[data-no-reload="true"]')))) {
            return;
        }
        closeModal();
        closeModalSecondary();
        location.reload();
    }
});

// Hamburger menu toggle
document.addEventListener('DOMContentLoaded', function () {
    const navbarToggler = document.getElementById('navbar-toggler');
    const navLinks = document.getElementById('nav-links');
    const commSidebarToggle = document.querySelector('.comm-sidebar-toggle');
    const commSidebarBackdrop = document.querySelector('.comm-sidebar-backdrop');
    const commSidebar = document.querySelector('.comm-sidebar-nav');

    if (navbarToggler && navLinks) {
        navbarToggler.addEventListener('click', function () {
            navLinks.classList.toggle('active');
        });

        // Close menu when clicking on a link
        const links = navLinks.querySelectorAll('a');
        links.forEach(link => {
            link.addEventListener('click', function () {
                navLinks.classList.remove('active');
            });
        });
    }

    function closeCommSidebar() {
        if (!commSidebar) return;
        commSidebar.classList.remove('is-open');
        if (commSidebarToggle) commSidebarToggle.setAttribute('aria-expanded', 'false');
        if (commSidebarBackdrop) commSidebarBackdrop.classList.remove('is-visible');
        document.body.classList.remove('comm-sidebar-open');
    }

    if (commSidebarToggle && commSidebar) {
        commSidebarToggle.addEventListener('click', function () {
            const isOpen = commSidebar.classList.toggle('is-open');
            commSidebarToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
            if (commSidebarBackdrop) commSidebarBackdrop.classList.toggle('is-visible', isOpen);
            document.body.classList.toggle('comm-sidebar-open', isOpen);
        });
    }

    if (commSidebarBackdrop) {
        commSidebarBackdrop.addEventListener('click', closeCommSidebar);
    }
});
