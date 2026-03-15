/* ═══════════════════════════════════════════════════
   COMMONMIK — Frontend Controller
   pywebview JS API bridge + UI logic
   ═══════════════════════════════════════════════════ */

// ── i18n ──
const LANGS = {
    en: {
        status_idle: 'Idle',
        status_active: 'Active',
        output_title: 'Virtual Microphone Output',
        output_desc: 'Mixed audio is sent here. Select this device as microphone in Discord.',
        select_device: 'Select device...',
        sources_title: 'Audio Sources',
        add_source: 'Add Source',
        empty_title: 'No audio sources added',
        empty_hint: 'Add a microphone or app audio to get started',
        btn_start: 'Start',
        btn_stop: 'Stop',
        modal_add_source: 'Add Source',
        tab_microphone: 'Microphone',
        tab_app_audio: 'App Audio',
        settings_title: 'Settings',
        setting_device_name: 'Virtual Device Name',
        setting_device_desc: 'Microphone name shown in Windows',
        btn_apply: 'Apply',
        setting_target: 'Target Device',
        setting_target_desc: 'Virtual audio device to rename',
        // Dynamic strings
        type_microphone: 'microphone',
        type_app: 'app audio',
        toast_added: '{name} added',
        toast_removed: 'Source removed',
        toast_output_set: 'Output device set',
        toast_engine_started: 'Engine started',
        toast_engine_stopped: 'Engine stopped',
        toast_settings_restored: 'Settings restored',
        toast_select_output: 'Please select an output device',
        toast_source_failed: 'Could not add source',
        toast_enter_name: 'Please enter a name',
        toast_renamed: 'Device renamed to "{name}"',
        toast_rename_failed: 'Could not rename device',
        no_apps_found: 'No audio apps found',
        refresh_list: '🔄 Refresh List',
        no_device_found: 'No device found',
    },
    tr: {
        status_idle: 'Bekleniyor',
        status_active: 'Aktif',
        output_title: 'Sanal Mikrofon Çıkışı',
        output_desc: 'Karıştırılmış ses buraya yazılır. Discord\'da bu cihazı mikrofon olarak seçin.',
        select_device: 'Cihaz seçin...',
        sources_title: 'Ses Kaynakları',
        add_source: 'Kaynak Ekle',
        empty_title: 'Henüz ses kaynağı eklenmedi',
        empty_hint: 'Mikrofon veya uygulama sesi ekleyerek başlayın',
        btn_start: 'Başlat',
        btn_stop: 'Durdur',
        modal_add_source: 'Kaynak Ekle',
        tab_microphone: 'Mikrofon',
        tab_app_audio: 'Uygulama Sesi',
        settings_title: 'Ayarlar',
        setting_device_name: 'Sanal Cihaz İsmi',
        setting_device_desc: 'Windows\'ta görünecek mikrofon ismi',
        btn_apply: 'Uygula',
        setting_target: 'Hedef Cihaz',
        setting_target_desc: 'İsmi değiştirilecek sanal ses cihazı',
        type_microphone: 'mikrofon',
        type_app: 'uygulama sesi',
        toast_added: '{name} eklendi',
        toast_removed: 'Kaynak kaldırıldı',
        toast_output_set: 'Çıkış cihazı ayarlandı',
        toast_engine_started: 'Motor başlatıldı',
        toast_engine_stopped: 'Motor durduruldu',
        toast_settings_restored: 'Ayarlar geri yüklendi',
        toast_select_output: 'Lütfen bir çıkış cihazı seçin',
        toast_source_failed: 'Kaynak eklenemedi',
        toast_enter_name: 'Lütfen bir isim girin',
        toast_renamed: 'Cihaz ismi "{name}" olarak değiştirildi',
        toast_rename_failed: 'İsim değiştirilemedi',
        no_apps_found: 'Ses çalan uygulama bulunamadı',
        refresh_list: '🔄 Listeyi Yenile',
        no_device_found: 'Cihaz bulunamadı',
    },
};

let currentLang = localStorage.getItem('mik_lang') || 'en';

function t(key, params = {}) {
    let str = LANGS[currentLang]?.[key] || LANGS.en[key] || key;
    for (const [k, v] of Object.entries(params)) {
        str = str.replace(`{${k}}`, v);
    }
    return str;
}

function applyI18n() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.dataset.i18n;
        const text = t(key);
        if (el.tagName === 'OPTION') {
            el.textContent = text;
        } else if (el.tagName === 'INPUT') {
            el.placeholder = text;
        } else {
            el.textContent = text;
        }
    });
    document.getElementById('langLabel').textContent = currentLang.toUpperCase();
}

function toggleLang() {
    currentLang = currentLang === 'en' ? 'tr' : 'en';
    localStorage.setItem('mik_lang', currentLang);
    applyI18n();
    // Update dynamic engine button text
    const btnSpan = dom.btnToggleEngine.querySelector('span');
    if (btnSpan) {
        btnSpan.textContent = state.engineRunning ? t('btn_stop') : t('btn_start');
    }
    // Update status text
    const statusText = dom.statusIndicator.querySelector('.status-text');
    if (statusText) {
        statusText.textContent = state.engineRunning ? t('status_active') : t('status_idle');
    }
    // Re-render source cards with new language
    renderSources(true);
    autoSave();
}

// ── State ──
const state = {
    engineRunning: false,
    sources: {},
    selectedSourceType: 'microphone',
    levelPollInterval: null,
};

// ── DOM References ──
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const dom = {
    outputSelect: $('#outputDeviceSelect'),
    sourcesList: $('#sourcesList'),
    emptyState: $('#emptyState'),
    btnAddSource: $('#btnAddSource'),
    btnToggleEngine: $('#btnToggleEngine'),
    btnSettings: $('#btnSettings'),
    statusIndicator: $('#statusIndicator'),
    masterVolume: $('#masterVolume'),
    masterVolumeValue: $('#masterVolumeValue'),
    masterPeakFill: $('#masterPeakFill'),
    addSourceModal: $('#addSourceModal'),
    settingsModal: $('#settingsModal'),
    modalDeviceList: $('#modalDeviceList'),
    btnCloseModal: $('#btnCloseModal'),
    btnCloseSettings: $('#btnCloseSettings'),
    btnRenameDevice: $('#btnRenameDevice'),
    deviceNameInput: $('#deviceNameInput'),
    renameTargetSelect: $('#renameTargetSelect'),
};

// ── API helper — waits for pywebview ready ──
function api() {
    return window.pywebview.api;
}

// ── Toast Notifications ──
function toast(message, type = 'success') {
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = message;
    container.appendChild(el);

    setTimeout(() => {
        el.classList.add('removing');
        setTimeout(() => el.remove(), 300);
    }, 3000);
}

// ── Initialize ──
async function init() {
    applyI18n();
    await loadDevices();
    bindEvents();
    await restoreSettings();
    console.log('CommonMik UI initialized');
}

// ── Auto-save (debounced) ──
let _saveTimer = null;
function autoSave() {
    if (_saveTimer) clearTimeout(_saveTimer);
    _saveTimer = setTimeout(async () => {
        try {
            await api().save_settings();
            // Save lang preference alongside
            try { await api().save_lang(currentLang); } catch(e) {}
        } catch (e) { /* silent */ }
    }, 1000);
}

// ── Restore saved settings ──
async function restoreSettings() {
    try {
        const saved = await api().load_settings();
        if (!saved || !saved.ok) return;

        // Dil tercihi
        if (saved.lang) {
            currentLang = saved.lang;
            localStorage.setItem('mik_lang', currentLang);
            applyI18n();
        }

        // Çıkış cihazı
        if (saved.output_device_index !== null) {
            dom.outputSelect.value = saved.output_device_index;
            await api().set_output_device(saved.output_device_index);
        }

        // Master volume
        if (saved.master_volume !== undefined) {
            const pct = Math.round(saved.master_volume * 100);
            dom.masterVolume.value = pct;
            dom.masterVolumeValue.textContent = `${pct}%`;
            await api().set_master_volume(saved.master_volume);
        }

        // Kaynakları ekle
        let addedAny = false;
        for (const src of (saved.sources || [])) {
            if (!src.found) continue;

            let result;
            if (src.type === 'microphone') {
                result = await api().add_microphone(src.device_index, src.name);
            } else if (src.type === 'loopback' && src.pid) {
                result = await api().add_loopback(-1, src.name, src.pid);
            }

            if (result && result.ok) {
                state.sources[result.id] = {
                    id: result.id,
                    name: src.name,
                    type: src.type,
                    volume: src.volume,
                    muted: src.muted,
                };

                await api().set_volume(result.id, src.volume);
                if (src.muted) {
                    await api().set_mute(result.id, true);
                }
                addedAny = true;
            }
        }

        if (addedAny) {
            renderSources();

            for (const [id, src] of Object.entries(state.sources)) {
                const slider = document.querySelector(`[data-volume="${id}"]`);
                const label = document.querySelector(`[data-volume-label="${id}"]`);
                if (slider) {
                    slider.value = Math.round(src.volume * 100);
                    if (label) label.textContent = `${slider.value}%`;
                }
                if (src.muted) {
                    const btn = document.querySelector(`[data-mute="${id}"]`);
                    if (btn) {
                        btn.classList.add('muted');
                        btn.innerHTML = `
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
                                <line x1="23" y1="9" x2="17" y2="15"/>
                                <line x1="17" y1="9" x2="23" y2="15"/>
                            </svg>`;
                    }
                }
            }

            toast(t('toast_settings_restored'));
        }
    } catch (e) {
        console.error('restoreSettings error:', e);
    }
}

// ── Load Devices ──
async function loadDevices() {
    try {
        const outputs = await api().get_output_devices();

        if (outputs && outputs.length > 0) {
            dom.outputSelect.innerHTML = '<option value="">Cihaz seçin...</option>';
            outputs.forEach(dev => {
                const opt = document.createElement('option');
                opt.value = dev.index;
                const apiTag = dev.api ? ` [${dev.api}]` : '';
                const rate = dev.sample_rate ? ` ${Math.round(dev.sample_rate/1000)}kHz` : '';
                opt.textContent = `${dev.name}${rate}${apiTag}`;
                if (dev.api === 'WASAPI' && dev.name.toLowerCase().includes('cable input')) {
                    opt.selected = true;
                }
                dom.outputSelect.appendChild(opt);
            });

            if (dom.outputSelect.value) {
                await api().set_output_device(parseInt(dom.outputSelect.value));
            }
        }
    } catch (e) {
        console.error('loadDevices error:', e);
    }
}

// ── Load Input Devices for Modal ──
async function loadModalDevices(type) {
    try {
        dom.modalDeviceList.innerHTML = '';

        if (type === 'loopback') {
            const apps = await api().get_audio_apps();
            if (apps && apps.length > 0) {
                apps.forEach(app => {
                    const item = document.createElement('div');
                    item.className = 'device-item';
                    item.innerHTML = `
                        <span class="device-item-name">🎵 ${app.name}</span>
                        <span class="device-item-channels">PID:${app.pid}</span>
                    `;
                    item.addEventListener('click', () => addSource('loopback', {
                        index: -1,
                        name: app.name,
                        channels: 2,
                        pid: app.pid,
                    }));
                    dom.modalDeviceList.appendChild(item);
                });
            } else {
                const empty = document.createElement('div');
                empty.style.cssText = 'padding: 20px; text-align: center; color: var(--text-muted); font-size: 0.85rem;';
                empty.textContent = t('no_apps_found');
                dom.modalDeviceList.appendChild(empty);
            }

            const refresh = document.createElement('div');
            refresh.className = 'device-item';
            refresh.style.cssText = 'justify-content: center; opacity: 0.7; margin-top: 8px;';
            refresh.innerHTML = `<span class="device-item-name">${t('refresh_list')}</span>`;
            refresh.addEventListener('click', () => loadModalDevices('loopback'));
            dom.modalDeviceList.appendChild(refresh);
            return;
        }

        const devices = await api().get_input_devices();

        if (!devices || devices.length === 0) {
            dom.modalDeviceList.innerHTML = `
                <div class="empty-state" style="padding: 20px;">
                    <p>${t('no_device_found')}</p>
                </div>`;
            return;
        }

        devices.forEach(dev => {
            const item = document.createElement('div');
            item.className = 'device-item';
            item.innerHTML = `
                <span class="device-item-name">${dev.name}</span>
                <span class="device-item-channels">${dev.api ? dev.api : ''} ${Math.round(dev.sample_rate/1000)}kHz</span>
            `;
            item.addEventListener('click', () => addSource(type, dev));
            dom.modalDeviceList.appendChild(item);
        });
    } catch (e) {
        console.error('loadModalDevices error:', e);
    }
}

// ── Add Source ──
async function addSource(type, device) {
    try {
        let result;
        if (type === 'microphone') {
            result = await api().add_microphone(device.index, device.name);
        } else {
            result = await api().add_loopback(device.index, device.name, device.pid || null);
        }

        if (result && result.ok) {
            state.sources[result.id] = {
                id: result.id,
                name: device.name,
                type: type,
                volume: 1.0,
                muted: false,
            };
            renderSources();
            closeModal('addSourceModal');
            toast(t('toast_added', {name: device.name}));
            autoSave();
        } else {
            toast(result?.error || t('toast_source_failed'), 'error');
        }
    } catch (e) {
        toast(t('toast_source_failed') + ': ' + e.message, 'error');
    }
}

// ── Remove Source ──
async function removeSource(sourceId) {
    const card = document.querySelector(`[data-source-id="${sourceId}"]`);
    if (card) {
        card.classList.add('removing');
        await new Promise(r => setTimeout(r, 300));
    }

    await api().remove_source(sourceId);
    delete state.sources[sourceId];
    renderSources();
    toast(t('toast_removed'));
    autoSave();
}

// ── Render Sources ──
function renderSources(forceRebuild = false) {
    const ids = Object.keys(state.sources);

    if (ids.length === 0) {
        dom.emptyState.style.display = '';
        dom.sourcesList.querySelectorAll('.source-card').forEach(el => el.remove());
        return;
    }

    dom.emptyState.style.display = 'none';

    if (forceRebuild) {
        dom.sourcesList.querySelectorAll('.source-card').forEach(el => el.remove());
    } else {
        dom.sourcesList.querySelectorAll('.source-card').forEach(el => {
            if (!state.sources[el.dataset.sourceId]) {
                el.remove();
            }
        });
    }

    ids.forEach(id => {
        let card = dom.sourcesList.querySelector(`[data-source-id="${id}"]`);
        if (!card) {
            card = createSourceCard(state.sources[id]);
            dom.sourcesList.appendChild(card);
        }
    });
}

function createSourceCard(source) {
    const card = document.createElement('div');
    card.className = 'source-card';
    card.dataset.sourceId = source.id;

    const isMic = source.type === 'microphone';
    const iconClass = isMic ? '' : 'loopback';
    const iconSvg = isMic
        ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
             <rect x="8" y="2" width="8" height="14" rx="4"/>
             <path d="M4 12a8 8 0 0016 0"/>
             <line x1="12" y1="20" x2="12" y2="24"/>
           </svg>`
        : `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
             <path d="M3 18v-6a9 9 0 0118 0v6"/>
             <path d="M21 19a2 2 0 01-2 2h-1a2 2 0 01-2-2v-3a2 2 0 012-2h3z
                      M3 19a2 2 0 002 2h1a2 2 0 002-2v-3a2 2 0 00-2-2H3z"/>
           </svg>`;

    card.innerHTML = `
        <div class="source-icon ${iconClass}">${iconSvg}</div>
        <div class="source-info">
            <div class="source-name">${source.name}</div>
            <div class="source-type">${isMic ? t('type_microphone') : t('type_app')}</div>
        </div>
        <div class="source-meter">
            <div class="meter-bar">
                <div class="meter-fill" data-meter="${source.id}"></div>
            </div>
        </div>
        <div class="source-volume">
            <input type="range" class="slider" min="0" max="200" value="100"
                   data-volume="${source.id}" />
            <span class="volume-value" data-volume-label="${source.id}">100%</span>
        </div>
        <div class="source-actions">
            <button class="btn-mute" data-mute="${source.id}" title="Sustur">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
                    <path d="M15.54 8.46a5 5 0 010 7.07"/>
                    <path d="M19.07 4.93a10 10 0 010 14.14"/>
                </svg>
            </button>
            <button class="btn-remove" data-remove="${source.id}" title="Kaldır">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
            </button>
        </div>
    `;

    // Volume slider
    const slider = card.querySelector(`[data-volume="${source.id}"]`);
    const label = card.querySelector(`[data-volume-label="${source.id}"]`);
    slider.addEventListener('input', async () => {
        const vol = parseInt(slider.value) / 100;
        label.textContent = `${slider.value}%`;
        state.sources[source.id].volume = vol;
        await api().set_volume(source.id, vol);
        autoSave();
    });

    // Mute button
    card.querySelector(`[data-mute="${source.id}"]`).addEventListener('click', async () => {
        const src = state.sources[source.id];
        src.muted = !src.muted;
        const btn = card.querySelector(`[data-mute="${source.id}"]`);
        btn.classList.toggle('muted', src.muted);

        if (src.muted) {
            btn.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
                    <line x1="23" y1="9" x2="17" y2="15"/>
                    <line x1="17" y1="9" x2="23" y2="15"/>
                </svg>`;
        } else {
            btn.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
                    <path d="M15.54 8.46a5 5 0 010 7.07"/>
                    <path d="M19.07 4.93a10 10 0 010 14.14"/>
                </svg>`;
        }

        await api().set_mute(source.id, src.muted);
        autoSave();
    });

    // Remove button
    card.querySelector(`[data-remove="${source.id}"]`).addEventListener('click', () => {
        removeSource(source.id);
    });

    return card;
}

// ── Level Polling ──
function startLevelPolling() {
    if (state.levelPollInterval) return;

    state.levelPollInterval = setInterval(async () => {
        if (!state.engineRunning) return;

        try {
            const levels = await api().get_levels();
            if (!levels) return;

            Object.entries(levels).forEach(([id, data]) => {
                if (id === 'master') {
                    const peak = Math.min(data.peak * 100, 100);
                    dom.masterPeakFill.style.width = `${peak}%`;
                    return;
                }

                const meter = document.querySelector(`[data-meter="${id}"]`);
                if (meter) {
                    const peak = Math.min(data.peak * 100, 100);
                    meter.style.width = `${peak}%`;
                }
            });
        } catch (e) {
            // Polling error — ignore
        }
    }, 50);
}

function stopLevelPolling() {
    if (state.levelPollInterval) {
        clearInterval(state.levelPollInterval);
        state.levelPollInterval = null;
    }

    document.querySelectorAll('.meter-fill, .peak-fill').forEach(el => {
        el.style.width = '0%';
    });
}

// ── Engine Toggle ──
async function toggleEngine() {
    try {
        if (state.engineRunning) {
            const result = await api().stop_engine();
            if (result?.ok) {
                state.engineRunning = false;
                dom.btnToggleEngine.classList.remove('active');
                dom.btnToggleEngine.querySelector('span').textContent = 'Başlat';
                dom.statusIndicator.classList.remove('active');
                dom.statusIndicator.querySelector('.status-text').textContent = 'Bekleniyor';
                stopLevelPolling();
                toast(t('toast_engine_stopped'));
            }
        } else {
            if (!dom.outputSelect.value) {
                toast(t('toast_select_output'), 'error');
                return;
            }

            const result = await api().start_engine();
            if (result?.ok) {
                state.engineRunning = true;
                dom.btnToggleEngine.classList.add('active');
                dom.btnToggleEngine.querySelector('span').textContent = 'Durdur';
                dom.statusIndicator.classList.add('active');
                dom.statusIndicator.querySelector('.status-text').textContent = 'Aktif';
                startLevelPolling();
                toast(t('toast_engine_started'));
            } else {
                toast(result?.error || t('toast_source_failed'), 'error');
            }
        }
    } catch (e) {
        toast(e.message, 'error');
    }
}

// ── Modals ──
function openModal(id) {
    document.getElementById(id).classList.add('visible');
}

function closeModal(id) {
    document.getElementById(id).classList.remove('visible');
}

// ── Event Bindings ──
function bindEvents() {
    dom.btnToggleEngine.addEventListener('click', toggleEngine);
    document.getElementById('btnLang').addEventListener('click', toggleLang);

    dom.outputSelect.addEventListener('change', async () => {
        if (dom.outputSelect.value) {
            await api().set_output_device(parseInt(dom.outputSelect.value));
            toast(t('toast_output_set'));
            autoSave();
        }
    });

    dom.masterVolume.addEventListener('input', async () => {
        const vol = parseInt(dom.masterVolume.value) / 100;
        dom.masterVolumeValue.textContent = `${dom.masterVolume.value}%`;
        await api().set_master_volume(vol);
        autoSave();
    });

    dom.btnAddSource.addEventListener('click', () => {
        openModal('addSourceModal');
        loadModalDevices(state.selectedSourceType);
    });

    dom.btnCloseModal.addEventListener('click', () => closeModal('addSourceModal'));

    document.querySelectorAll('.source-type-tabs .tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.source-type-tabs .tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            state.selectedSourceType = tab.dataset.type;
            loadModalDevices(tab.dataset.type);
        });
    });

    dom.btnSettings.addEventListener('click', () => openModal('settingsModal'));
    dom.btnCloseSettings.addEventListener('click', () => closeModal('settingsModal'));

    dom.btnRenameDevice.addEventListener('click', async () => {
        const newName = dom.deviceNameInput.value.trim();
        const target = dom.renameTargetSelect.value;
        if (!newName) {
            toast(t('toast_enter_name'), 'error');
            return;
        }
        try {
            const result = await api().rename_audio_device(target, newName);
            if (result?.ok) {
                toast(t('toast_renamed', {name: newName}));
            } else {
                toast(result?.error || t('toast_rename_failed'), 'error');
            }
        } catch (e) {
            toast(e.message, 'error');
        }
    });

    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                overlay.classList.remove('visible');
            }
        });
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal-overlay.visible').forEach(m => {
                m.classList.remove('visible');
            });
        }
    });
}

// ── Wait for pywebview ──
window.addEventListener('pywebviewready', () => {
    setTimeout(init, 100);
});
