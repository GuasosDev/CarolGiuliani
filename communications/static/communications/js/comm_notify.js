(function () {
    if (window.commNotify) return;

    var VOLUME_KEY = 'gd_notify_volume';
    var SOUND_KEY = 'gd_notify_sound';
    var DEFAULT_VOLUME_PCT = 70;
    var DEFAULT_SOUND = 'ping';

    var SOUND_OPTIONS = [
        { id: 'ping', label: 'Ping claro' },
        { id: 'doble', label: 'Doble golpe' },
        { id: 'timbre', label: 'Timbre oficina' },
        { id: 'alarma', label: 'Alarma rápida' },
        { id: 'sirena', label: 'Sirena estridente ★' }
    ];

    var state = {
        enabled: false,
        ctx: null,
        lastPlayAt: 0
    };

    function clampPct(n) {
        n = parseInt(n, 10);
        if (isNaN(n)) return DEFAULT_VOLUME_PCT;
        return Math.max(0, Math.min(100, n));
    }

    function getVolumePct() {
        try {
            var raw = localStorage.getItem(VOLUME_KEY);
            if (raw == null || raw === '') return DEFAULT_VOLUME_PCT;
            return clampPct(raw);
        } catch (e) {
            return DEFAULT_VOLUME_PCT;
        }
    }

    function setVolumePct(pct) {
        pct = clampPct(pct);
        try { localStorage.setItem(VOLUME_KEY, String(pct)); } catch (e) {}
        return pct;
    }

    function normalizeSoundId(id) {
        id = String(id || '').trim();
        // Compat con ids viejos del selector anterior
        if (id === 'suave' || id === 'campana' || id === 'pop') id = 'ping';
        if (id === 'alerta') id = 'alarma';
        if (id === 'estridente') id = 'sirena';
        for (var i = 0; i < SOUND_OPTIONS.length; i++) {
            if (SOUND_OPTIONS[i].id === id) return id;
        }
        return DEFAULT_SOUND;
    }

    function getSoundId() {
        try {
            return normalizeSoundId(localStorage.getItem(SOUND_KEY) || DEFAULT_SOUND);
        } catch (e) {
            return DEFAULT_SOUND;
        }
    }

    function setSoundId(id) {
        id = normalizeSoundId(id);
        try { localStorage.setItem(SOUND_KEY, id); } catch (e) {}
        return id;
    }

    function pctToGain(pct) {
        pct = clampPct(pct);
        if (pct <= 0) return 0;
        return 0.08 + (pct / 100) * 0.84;
    }

    function getAudioContext() {
        if (state.ctx) return state.ctx;
        var AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx) return null;
        state.ctx = new AudioCtx();
        return state.ctx;
    }

    function tone(ctx, freq, startAt, durationSec, volume, waveType) {
        if (!volume || volume <= 0) return;
        var peak = Math.min(Math.max(volume, 0.001), 0.95);
        var osc = ctx.createOscillator();
        var gain = ctx.createGain();
        osc.type = waveType || 'square';
        osc.frequency.setValueAtTime(freq, startAt);
        gain.gain.setValueAtTime(0.0001, startAt);
        gain.gain.linearRampToValueAtTime(peak, startAt + 0.008);
        gain.gain.exponentialRampToValueAtTime(0.0001, startAt + Math.max(durationSec, 0.04));
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(startAt);
        osc.stop(startAt + durationSec + 0.05);
    }

    /** Nota “con cuerpo”: square + sawtooth a la vez. */
    function punch(ctx, freq, startAt, durationSec, volume) {
        tone(ctx, freq, startAt, durationSec, volume, 'square');
        tone(ctx, freq * 1.01, startAt, durationSec, volume * 0.65, 'sawtooth');
    }

    function sweep(ctx, f0, f1, startAt, durationSec, volume, waveType) {
        if (!volume || volume <= 0) return;
        var peak = Math.min(Math.max(volume, 0.001), 0.95);
        var osc = ctx.createOscillator();
        var gain = ctx.createGain();
        osc.type = waveType || 'square';
        osc.frequency.setValueAtTime(f0, startAt);
        osc.frequency.linearRampToValueAtTime(f1, startAt + durationSec);
        gain.gain.setValueAtTime(0.0001, startAt);
        gain.gain.linearRampToValueAtTime(peak, startAt + 0.02);
        gain.gain.setValueAtTime(peak, startAt + durationSec * 0.75);
        gain.gain.exponentialRampToValueAtTime(0.0001, startAt + durationSec);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(startAt);
        osc.stop(startAt + durationSec + 0.04);
    }

    function playTone(soundId, ctx, t, vol) {
        soundId = normalizeSoundId(soundId);
        var v = Math.min(vol, 0.95);

        if (soundId === 'doble') {
            // Dos golpes secos, tipo “toc-toc” fuerte
            punch(ctx, 880, t, 0.08, v);
            punch(ctx, 880, t + 0.14, 0.10, v);
            return;
        }
        if (soundId === 'timbre') {
            // Timbre metálico repetido (oficina)
            punch(ctx, 1500, t, 0.06, v);
            punch(ctx, 1500, t + 0.09, 0.06, v);
            punch(ctx, 1500, t + 0.18, 0.06, v);
            punch(ctx, 1500, t + 0.27, 0.08, v);
            tone(ctx, 300, t, 0.08, v * 0.45, 'square');
            return;
        }
        if (soundId === 'alarma') {
            // Ráfaga de beeps cortos y agudos
            var i;
            for (i = 0; i < 6; i++) {
                punch(ctx, i % 2 === 0 ? 1800 : 2400, t + i * 0.085, 0.055, v);
            }
            return;
        }
        if (soundId === 'sirena') {
            // Sirena up/down + beeps: el más “molesto” a propósito
            sweep(ctx, 900, 2200, t, 0.28, v, 'square');
            sweep(ctx, 900, 2200, t, 0.28, v * 0.55, 'sawtooth');
            sweep(ctx, 2200, 900, t + 0.28, 0.28, v, 'square');
            sweep(ctx, 2200, 900, t + 0.28, 0.28, v * 0.55, 'sawtooth');
            punch(ctx, 2000, t + 0.58, 0.07, v);
            punch(ctx, 2400, t + 0.68, 0.07, v);
            punch(ctx, 2000, t + 0.78, 0.10, v);
            return;
        }
        // ping: un corte claro, no melódico
        punch(ctx, 1200, t, 0.09, v);
        punch(ctx, 1600, t + 0.10, 0.11, v);
    }

    function unlockAudio() {
        state.enabled = true;
        var ctx = getAudioContext();
        if (ctx && ctx.state === 'suspended') {
            ctx.resume().catch(function () {});
        }
        document.removeEventListener('pointerdown', unlockAudio, true);
        document.removeEventListener('keydown', unlockAudio, true);
    }

    document.addEventListener('pointerdown', unlockAudio, true);
    document.addEventListener('keydown', unlockAudio, true);

    function playDing(kind, opts) {
        opts = opts || {};
        var nowMs = Date.now();
        if (!opts.force && nowMs - state.lastPlayAt < 800) return false;
        state.lastPlayAt = nowMs;
        var ctx = getAudioContext();
        if (!ctx) return false;
        if (ctx.state === 'suspended') ctx.resume().catch(function () {});
        var t = ctx.currentTime + 0.01;
        var base = pctToGain(getVolumePct());
        if (base <= 0) return false;

        if (kind === 'whatsapp' || kind === 'notify' || !kind) {
            playTone(opts.soundId || getSoundId(), ctx, t, base);
            return true;
        }
        if (kind === 'email') {
            punch(ctx, 1000, t, 0.09, base);
            punch(ctx, 700, t + 0.12, 0.12, base);
            return true;
        }
        if (kind === 'internal') {
            punch(ctx, 1100, t, 0.06, base);
            punch(ctx, 1100, t + 0.10, 0.06, base);
            punch(ctx, 1100, t + 0.20, 0.08, base);
            return true;
        }
        playTone(kind, ctx, t, base);
        return true;
    }

    window.commNotify = {
        playDing: playDing,
        unlockAudio: unlockAudio,
        isEnabled: function () { return state.enabled; },
        getVolume: getVolumePct,
        setVolume: setVolumePct,
        getSound: getSoundId,
        setSound: setSoundId,
        listSounds: function () { return SOUND_OPTIONS.slice(); },
        VOLUME_KEY: VOLUME_KEY,
        SOUND_KEY: SOUND_KEY
    };
})();
