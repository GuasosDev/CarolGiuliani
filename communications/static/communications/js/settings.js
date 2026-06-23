(function () {
    var slider = document.getElementById('settingsFontSizeSlider');
    var badge = document.getElementById('settingsFontSizeValue');
    var toggle = document.getElementById('settingsDarkModeToggle');

    try {
        var fs = localStorage.getItem('gd_font_size');
        if (fs && slider) {
            slider.value = fs;
            if (badge) badge.textContent = fs + 'px';
            document.documentElement.style.setProperty('--global-font-size', fs + 'px');
            var pv = document.getElementById('fontLivePreviewText');
            if (pv) pv.style.fontSize = fs + 'px';
        }
        var dm = localStorage.getItem('gd_dark_mode');
        if (dm !== null && toggle) {
            toggle.checked = (dm === 'true');
            document.body.classList.toggle('dark-mode', toggle.checked);
        }
    } catch (e) {}

    if (slider) {
        function applySize(v) {
            if (badge) badge.textContent = v + 'px';
            document.documentElement.style.setProperty('--global-font-size', v + 'px');
            var pv = document.getElementById('fontLivePreviewText');
            if (pv) pv.style.fontSize = v + 'px';
            try { localStorage.setItem('gd_font_size', v); } catch (e) {}
        }
        slider.addEventListener('input', function () { applySize(String(this.value)); });
        slider.addEventListener('change', function () { applySize(String(this.value)); });
    }

    if (toggle) {
        toggle.addEventListener('change', function () {
            document.body.classList.toggle('dark-mode', this.checked);
            try { localStorage.setItem('gd_dark_mode', this.checked ? 'true' : 'false'); } catch (e) {}
        });
    }

    var templatesTextarea = document.getElementById('waTemplatesTextarea');
    if (templatesTextarea && !templatesTextarea.value.trim()) {
        templatesTextarea.value = templatesTextarea.dataset.initialJson || '[]';
    }
})();
