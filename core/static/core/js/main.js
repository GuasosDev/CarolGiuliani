function openModal() {
    document.getElementById('modal').style.display = 'block';
}

function closeModal() {
    document.getElementById('modal').style.display = 'none';
    document.getElementById('modal-body').innerHTML = '';
}

// Close modal when clicking outside
window.onclick = function (event) {
    var modal = document.getElementById('modal');
    if (event.target == modal) {
        closeModal();
    }
}

// HTMX listeners to handle closing modal on success if needed, or simple redirect
// Handle refreshing list from generic forms
document.body.addEventListener('refreshList', function () {
    closeModal();
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
    location.reload();
});

// Fallback: If 204 is returned but event doesn't trigger (sometimes happens if parsed differently)
document.body.addEventListener('htmx:afterRequest', function (evt) {
    if (evt.detail.successful && evt.detail.xhr.status === 204) {
        closeModal();
        location.reload();
    }
});

// Hamburger menu toggle
document.addEventListener('DOMContentLoaded', function () {
    const navbarToggler = document.getElementById('navbar-toggler');
    const navLinks = document.getElementById('nav-links');

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
});
