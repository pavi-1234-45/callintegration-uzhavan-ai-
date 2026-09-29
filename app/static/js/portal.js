/**
 * Uzhavan AI Voice Portal - Interactive Client Logic
 */

// Geolocation Handler
async function detectDeviceLocation() {
    const statusEl = document.getElementById('geo-status');
    const latInput = document.getElementById('latitude');
    const lonInput = document.getElementById('longitude');
    const districtInput = document.getElementById('district');
    const stateInput = document.getElementById('state');
    const talukInput = document.getElementById('taluk');
    const villageInput = document.getElementById('village');

    if (!navigator.geolocation) {
        if (statusEl) statusEl.innerHTML = '<span style="color:#ef4444">Geolocation is not supported by your browser.</span>';
        return;
    }

    if (statusEl) statusEl.innerHTML = '<span style="color:#38bdf8">📍 Fetching GPS satellite coordinates...</span>';

    navigator.geolocation.getCurrentPosition(
        async (position) => {
            const lat = position.coords.latitude;
            const lon = position.coords.longitude;
            latInput.value = lat.toFixed(6);
            lonInput.value = lon.toFixed(6);

            if (statusEl) statusEl.innerHTML = '<span style="color:#34d399">✅ GPS Locked (' + lat.toFixed(4) + ', ' + lon.toFixed(4) + '). Resolving location details...</span>';

            // Reverse Geocode
            try {
                const resp = await fetch(`/api/farmers/tools/reverse-geocode?lat=${lat}&lon=${lon}`);
                const data = await resp.json();
                if (data.success) {
                    if (data.district && districtInput) districtInput.value = data.district;
                    if (data.state && stateInput) stateInput.value = data.state;
                    if (data.taluk && talukInput) talukInput.value = data.taluk;
                    if (data.village && villageInput) villageInput.value = data.village;
                    if (statusEl) statusEl.innerHTML = `<span style="color:#34d399">✅ Verified Location: ${data.district}, ${data.state}</span>`;
                }
            } catch (err) {
                console.error("Geocode error", err);
            }
        },
        (error) => {
            if (statusEl) {
                statusEl.innerHTML = `<span style="color:#f59e0b">⚠️ Geolocation error: ${error.message}. You can enter coordinates manually or pick a district.</span>`;
            }
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    );
}

// Global Audio Player
let globalAudio = new Audio();

function playAudioUrl(url, btnElement) {
    if (!url) {
        alert("Audio URL is not available yet.");
        return;
    }
    if (globalAudio.src.includes(url) && !globalAudio.paused) {
        globalAudio.pause();
        if (btnElement) btnElement.innerHTML = '▶ Play Audio';
        return;
    }

    globalAudio.src = url;
    globalAudio.play();
    if (btnElement) {
        btnElement.innerHTML = '⏸ Pause';
        globalAudio.onended = () => {
            btnElement.innerHTML = '▶ Play Audio';
        };
    }
}

// Live Dashboard Stats Polling
async function refreshDashboardStats() {
    try {
        const res = await fetch('/api/dashboard/stats');
        if (!res.ok) return;
        const data = await res.json();

        const ids = [
            'total_farmers', 'voice_enabled_farmers', 'todays_alerts',
            'queued_calls', 'completed_calls', 'failed_calls',
            'no_answer_calls', 'active_retries'
        ];

        ids.forEach(id => {
            const el = document.getElementById(`stat-${id}`);
            if (el && data[id] !== undefined) {
                el.innerText = data[id];
            }
        });
    } catch (err) {
        console.error("Dashboard stats polling error:", err);
    }
}

// Modal helper
function openModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.classList.add('active');
}

function closeModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.classList.remove('active');
}
