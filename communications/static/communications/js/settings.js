(function () {
    var slider = document.getElementById('settingsFontSizeSlider');
    var badge = document.getElementById('settingsFontSizeValue');
    var toggle = document.getElementById('settingsDarkModeToggle');
    var VOLUME_KEY = 'gd_notify_volume';
    var SOUND_KEY = 'gd_notify_sound';
    var DEFAULT_VOLUME_PCT = 70;
    var DEFAULT_SOUND = 'ping';

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

    /* ── Sonido / volumen de notificación WhatsApp ── */
    var volSlider = document.getElementById('settingsNotifyVolumeSlider');
    var volBadge = document.getElementById('settingsNotifyVolumeValue');
    var volTest = document.getElementById('settingsNotifyVolumeTest');
    var soundSelect = document.getElementById('settingsNotifySoundSelect');

    function clampPct(n) {
        n = parseInt(n, 10);
        if (isNaN(n)) return DEFAULT_VOLUME_PCT;
        return Math.max(0, Math.min(100, n));
    }

    function readVolumePct() {
        if (window.commNotify && typeof window.commNotify.getVolume === 'function') {
            return clampPct(window.commNotify.getVolume());
        }
        try {
            var raw = localStorage.getItem(VOLUME_KEY);
            if (raw == null || raw === '') return DEFAULT_VOLUME_PCT;
            return clampPct(raw);
        } catch (e) {
            return DEFAULT_VOLUME_PCT;
        }
    }

    function writeVolumePct(pct) {
        pct = clampPct(pct);
        if (window.commNotify && typeof window.commNotify.setVolume === 'function') {
            window.commNotify.setVolume(pct);
        } else {
            try { localStorage.setItem(VOLUME_KEY, String(pct)); } catch (e) {}
        }
        return pct;
    }

    function readSoundId() {
        if (window.commNotify && typeof window.commNotify.getSound === 'function') {
            return window.commNotify.getSound();
        }
        try {
            return localStorage.getItem(SOUND_KEY) || DEFAULT_SOUND;
        } catch (e) {
            return DEFAULT_SOUND;
        }
    }

    function writeSoundId(id) {
        id = String(id || DEFAULT_SOUND);
        if (window.commNotify && typeof window.commNotify.setSound === 'function') {
            return window.commNotify.setSound(id);
        }
        try { localStorage.setItem(SOUND_KEY, id); } catch (e) {}
        return id;
    }

    function syncVolumeUi(pct) {
        pct = clampPct(pct);
        if (volSlider) volSlider.value = String(pct);
        if (volBadge) volBadge.textContent = pct + '%';
    }

    function previewWhatsappDing() {
        if (window.commNotify && typeof window.commNotify.playDing === 'function') {
            if (typeof window.commNotify.unlockAudio === 'function') window.commNotify.unlockAudio();
            window.commNotify.playDing('whatsapp', { force: true });
        }
    }

    if (soundSelect) {
        var currentSound = readSoundId();
        soundSelect.value = currentSound;
        if (soundSelect.value !== currentSound) soundSelect.value = DEFAULT_SOUND;
        soundSelect.addEventListener('change', function () {
            writeSoundId(this.value);
            previewWhatsappDing();
        });
    }

    if (volSlider) {
        syncVolumeUi(readVolumePct());
        volSlider.addEventListener('input', function () {
            var pct = writeVolumePct(this.value);
            syncVolumeUi(pct);
        });
        volSlider.addEventListener('change', function () {
            var pct = writeVolumePct(this.value);
            syncVolumeUi(pct);
            previewWhatsappDing();
        });
    }
    if (volTest) {
        volTest.addEventListener('click', function () {
            previewWhatsappDing();
        });
    }
})();
