/* ═══════════════════════════════════════════════════
   MIK AUDIO — Frontend Controller
   pywebview JS API bridge + UI logic
   ═══════════════════════════════════════════════════ */

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
    await loadDevices();
    bindEvents();
    await restoreSettings();
    console.log('Mik Audio UI initialized');
}

// ── Auto-save (debounced) ──
let _saveTimer = null;
function autoSave() {
    if (_saveTimer) clearTimeout(_saveTimer);
    _saveTimer = setTimeout(async () => {
        try { await api().save_settings(); } catch (e) { /* silent */ }
    }, 1000);
}

// ── Restore saved settings ──
async function restoreSettings() {
    try {
        const saved = await api().load_settings();
        if (!saved || !saved.ok) return;

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

            toast('Ayarlar geri yüklendi');
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
                empty.textContent = 'Ses çalan uygulama bulunamadı';
                dom.modalDeviceList.appendChild(empty);
            }

            const refresh = document.createElement('div');
            refresh.className = 'device-item';
            refresh.style.cssText = 'justify-content: center; opacity: 0.7; margin-top: 8px;';
            refresh.innerHTML = '<span class="device-item-name">🔄 Listeyi Yenile</span>';
            refresh.addEventListener('click', () => loadModalDevices('loopback'));
            dom.modalDeviceList.appendChild(refresh);
            return;
        }

        const devices = await api().get_input_devices();

        if (!devices || devices.length === 0) {
            dom.modalDeviceList.innerHTML = `
                <div class="empty-state" style="padding: 20px;">
                    <p>Cihaz bulunamadı</p>
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
            toast(`${device.name} eklendi`);
            autoSave();
        } else {
            toast(result?.error || 'Kaynak eklenemedi', 'error');
        }
    } catch (e) {
        toast('Kaynak eklenemedi: ' + e.message, 'error');
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
    toast('Kaynak kaldırıldı');
    autoSave();
}

// ── Render Sources ──
function renderSources() {
    const ids = Object.keys(state.sources);

    if (ids.length === 0) {
        dom.emptyState.style.display = '';
        dom.sourcesList.querySelectorAll('.source-card').forEach(el => el.remove());
        return;
    }

    dom.emptyState.style.display = 'none';

    dom.sourcesList.querySelectorAll('.source-card').forEach(el => {
        if (!state.sources[el.dataset.sourceId]) {
            el.remove();
        }
    });

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
            <div class="source-type">${isMic ? 'mikrofon' : 'uygulama sesi'}</div>
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
                toast('Motor durduruldu');
            }
        } else {
            if (!dom.outputSelect.value) {
                toast('Lütfen bir çıkış cihazı seçin', 'error');
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
                toast('Motor başlatıldı');
            } else {
                toast(result?.error || 'Motor başlatılamadı', 'error');
            }
        }
    } catch (e) {
        toast('Motor hatası: ' + e.message, 'error');
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

    dom.outputSelect.addEventListener('change', async () => {
        if (dom.outputSelect.value) {
            await api().set_output_device(parseInt(dom.outputSelect.value));
            toast('Çıkış cihazı ayarlandı');
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
            toast('Lütfen bir isim girin', 'error');
            return;
        }
        try {
            const result = await api().rename_audio_device(target, newName);
            if (result?.ok) {
                toast(`Cihaz ismi "${newName}" olarak değiştirildi`);
            } else {
                toast(result?.error || 'İsim değiştirilemedi', 'error');
            }
        } catch (e) {
            toast('Hata: ' + e.message, 'error');
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
