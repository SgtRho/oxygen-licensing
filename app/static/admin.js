(() => {
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  let allLicenses = [];
  let currentFilter = 'all';
  let currentSearch = '';

  const MODULE_KEYS = [
    'starface',
    'server_reports',
    'server_report_backups',
    'warehouse',
    'advanced_documents',
    'tickets'
  ];

  // DOM Elements
  const loginSection = document.getElementById('loginSection');
  const dashboardSection = document.getElementById('dashboardSection');
  const headerActions = document.getElementById('headerActions');
  const loginForm = document.getElementById('loginForm');
  const loginError = document.getElementById('loginError');
  const logoutBtn = document.getElementById('logoutBtn');
  const licenseTableBody = document.getElementById('licenseTableBody');
  const searchInput = document.getElementById('searchInput');
  const statusFilter = document.getElementById('statusFilter');
  const newLicenseBtn = document.getElementById('newLicenseBtn');

  // Modal Elements
  const modal = document.getElementById('licenseModal');
  const modalCloseBtn = document.getElementById('modalCloseBtn');
  const modalCancelBtn = document.getElementById('modalCancelBtn');
  const modalForm = document.getElementById('licenseModalForm');
  const modalTitle = document.getElementById('modalTitle');
  const modalLicenseId = document.getElementById('modalLicenseId');
  const modalCustomer = document.getElementById('modalCustomer');
  const modalKey = document.getElementById('modalKey');
  const modalGenKeyBtn = document.getElementById('modalGenKeyBtn');
  const modalUuid = document.getElementById('modalUuid');
  const modalValidUntil = document.getElementById('modalValidUntil');
  const modalPerpetual = document.getElementById('modalPerpetual');
  const modalActive = document.getElementById('modalActive');
  const modalNotes = document.getElementById('modalNotes');
  const modalError = document.getElementById('modalError');

  // Stats Elements
  const statTotal = document.getElementById('statTotal');
  const statActive = document.getElementById('statActive');
  const statUnassigned = document.getElementById('statUnassigned');
  const statInactive = document.getElementById('statInactive');

  // Logs Elements
  const toggleLogsBtn = document.getElementById('toggleLogsBtn');
  const logsContainer = document.getElementById('logsContainer');
  const logsTableBody = document.getElementById('logsTableBody');

  // Helper fetch with JSON
  async function api(url, options = {}) {
    const res = await fetch(url, {
      ...options,
      headers: {
        'Accept': 'application/json',
        ...(options.headers || {})
      }
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data?.detail?.message || data?.message || data?.error || `HTTP ${res.status}`);
    }
    return data;
  }

  // --- Auth Check ---
  async function checkAuth() {
    try {
      const me = await api('/api/admin/me');
      if (me.authenticated) {
        showDashboard();
      } else {
        showLogin();
      }
    } catch {
      showLogin();
    }
  }

  function showLogin() {
    loginSection.style.display = 'flex';
    dashboardSection.style.display = 'none';
    headerActions.style.display = 'none';
    document.getElementById('adminPassword').value = '';
    document.getElementById('adminPassword').focus();
  }

  function showDashboard() {
    loginSection.style.display = 'none';
    dashboardSection.style.display = 'block';
    headerActions.style.display = 'flex';
    loadData();
  }

  // --- Login & Logout ---
  loginForm.onsubmit = async (e) => {
    e.preventDefault();
    loginError.style.display = 'none';
    const pwd = document.getElementById('adminPassword').value;
    const btn = document.getElementById('loginSubmitBtn');
    btn.disabled = true;
    btn.textContent = 'Anmeldung läuft …';
    try {
      await api('/api/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: pwd })
      });
      showDashboard();
    } catch (err) {
      loginError.textContent = err.message;
      loginError.style.display = 'block';
    } finally {
      btn.disabled = false;
      btn.textContent = 'Anmelden';
    }
  };

  logoutBtn.onclick = async () => {
    try {
      await api('/api/admin/logout', { method: 'POST' });
    } catch {}
    showLogin();
  };

  // --- Data Loading ---
  async function loadData() {
    await Promise.all([loadStats(), loadLicenses()]);
  }

  async function loadStats() {
    try {
      const stats = await api('/api/admin/stats');
      statTotal.textContent = stats.total;
      statActive.textContent = stats.active;
      statUnassigned.textContent = stats.unassignedUuid;
      statInactive.textContent = stats.inactive + stats.expired;
    } catch (err) {
      console.error('Stats error:', err);
    }
  }

  async function loadLicenses() {
    try {
      const params = new URLSearchParams();
      if (currentSearch) params.append('q', currentSearch);
      if (currentFilter && currentFilter !== 'all') params.append('status_filter', currentFilter);

      allLicenses = await api(`/api/admin/licenses?${params.toString()}`);
      renderLicenses(allLicenses);
    } catch (err) {
      licenseTableBody.innerHTML = `<tr><td colspan="8" class="text-center py-8" style="color:var(--bad)">Fehler beim Laden: ${esc(err.message)}</td></tr>`;
    }
  }

  function formatRelativeTime(isoString) {
    if (!isoString) return '<span style="color:var(--muted)">Noch nie</span>';
    try {
      const date = new Date(isoString);
      const now = new Date();
      const diffSec = Math.floor((now - date) / 1000);
      if (diffSec < 60) return 'gerade eben';
      if (diffSec < 3600) return `vor ${Math.floor(diffSec / 60)} Min.`;
      if (diffSec < 86400) return `vor ${Math.floor(diffSec / 3600)} Std.`;
      return date.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
    } catch {
      return isoString;
    }
  }

  // --- Rendering ---
  function renderLicenses(licenses) {
    if (!licenses || licenses.length === 0) {
      licenseTableBody.innerHTML = `
        <tr>
          <td colspan="8" class="text-center py-8">
            <p style="color:var(--muted);margin-bottom:12px;">Keine Lizenzen gefunden.</p>
            <button class="btn btn-primary btn-sm" onclick="document.getElementById('newLicenseBtn').click()">+ Neue Lizenz anlegen</button>
          </td>
        </tr>
      `;
      return;
    }

    licenseTableBody.innerHTML = licenses.map((lic) => {
      let badgeClass = 'badge-inactive';
      let badgeLabel = 'Deaktiviert';
      if (lic.status === 'active') {
        badgeClass = 'badge-active';
        badgeLabel = '🟢 Aktiv';
      } else if (lic.status === 'unassigned_uuid') {
        badgeClass = 'badge-unassigned';
        badgeLabel = '🟡 Wartet auf UUID';
      } else if (lic.status === 'expired') {
        badgeClass = 'badge-expired';
        badgeLabel = '🔴 Abgelaufen';
      }

      // Modules summary
      const activeMods = Object.entries(lic.modules || {})
        .filter(([k, v]) => v && k !== 'core')
        .map(([k]) => k);
      const modTags = ['<span class="tag tag-core">Core</span>']
        .concat(activeMods.map((m) => `<span class="tag">${esc(m)}</span>`))
        .join('');

      const uuidHtml = lic.instance_uuid
        ? `<span class="code-pill copyable" data-copy="${esc(lic.instance_uuid)}" title="Klicken zum Kopieren">📋 ${esc(lic.instance_uuid)}</span>`
        : `<button class="btn btn-ghost btn-sm assign-uuid-btn" data-id="${lic.id}">⚠️ UUID eintragen</button>`;

      return `
        <tr>
          <td><span class="badge ${badgeClass}">${badgeLabel}</span></td>
          <td>
            <b>${esc(lic.customer_name)}</b>
            ${lic.notes ? `<small style="display:block;color:var(--muted);">${esc(lic.notes)}</small>` : ''}
          </td>
          <td>
            <span class="code-pill copyable" data-copy="${esc(lic.license_key)}" title="Klicken zum Kopieren">
              🔑 ${esc(lic.license_key)}
            </span>
          </td>
          <td>${uuidHtml}</td>
          <td><div class="module-tags">${modTags}</div></td>
          <td>${lic.valid_until ? esc(lic.valid_until) : '<span style="color:var(--muted)">Unbegrenzt</span>'}</td>
          <td>${formatRelativeTime(lic.last_check_at)}</td>
          <td class="text-right">
            <div class="actions-cell">
              <button class="btn btn-ghost btn-sm edit-btn" data-id="${lic.id}" title="Bearbeiten">✏️</button>
              <button class="btn btn-ghost btn-sm delete-btn" data-id="${lic.id}" data-name="${esc(lic.customer_name)}" title="Löschen">🗑️</button>
            </div>
          </td>
        </tr>
      `;
    }).join('');

    bindTableEvents();
  }

  function bindTableEvents() {
    // Click-to-copy
    document.querySelectorAll('.copyable').forEach((el) => {
      el.onclick = () => {
        const text = el.dataset.copy;
        navigator.clipboard.writeText(text).then(() => {
          const orig = el.innerHTML;
          el.innerHTML = '✅ Kopiert!';
          setTimeout(() => { el.innerHTML = orig; }, 1800);
        });
      };
    });

    // Assign UUID quick button
    document.querySelectorAll('.assign-uuid-btn').forEach((btn) => {
      btn.onclick = () => {
        const id = Number(btn.dataset.id);
        openEditModal(id, true);
      };
    });

    // Edit button
    document.querySelectorAll('.edit-btn').forEach((btn) => {
      btn.onclick = () => {
        const id = Number(btn.dataset.id);
        openEditModal(id, false);
      };
    });

    // Delete button
    document.querySelectorAll('.delete-btn').forEach((btn) => {
      btn.onclick = async () => {
        const id = Number(btn.dataset.id);
        const name = btn.dataset.name;
        if (confirm(`Soll die Lizenz für "${name}" wirklich gelöscht werden?`)) {
          try {
            await api(`/api/admin/licenses/${id}`, { method: 'DELETE' });
            loadData();
          } catch (err) {
            alert(`Fehler beim Löschen: ${err.message}`);
          }
        }
      };
    });
  }

  // --- Search & Filter ---
  let searchDebounce;
  searchInput.oninput = () => {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(() => {
      currentSearch = searchInput.value.trim();
      loadLicenses();
    }, 250);
  };

  statusFilter.onchange = () => {
    currentFilter = statusFilter.value;
    loadLicenses();
  };

  // --- Modal: Create / Edit ---
  newLicenseBtn.onclick = () => {
    openCreateModal();
  };

  modalCloseBtn.onclick = closeModal;
  modalCancelBtn.onclick = closeModal;

  modalPerpetual.onchange = () => {
    if (modalPerpetual.checked) {
      modalValidUntil.value = '';
      modalValidUntil.disabled = true;
    } else {
      modalValidUntil.disabled = false;
    }
  };

  modalGenKeyBtn.onclick = async () => {
    try {
      const data = await api('/api/admin/licenses/generate-key', { method: 'POST' });
      modalKey.value = data.license_key;
    } catch (err) {
      alert('Fehler beim Generieren: ' + err.message);
    }
  };

  async function openCreateModal() {
    modalTitle.textContent = 'Neue Lizenz anlegen';
    modalLicenseId.value = '';
    modalCustomer.value = '';
    modalUuid.value = '';
    modalValidUntil.value = '';
    modalValidUntil.disabled = false;
    modalPerpetual.checked = false;
    modalActive.checked = true;
    modalNotes.value = '';
    modalError.style.display = 'none';

    // Default modules: all checked
    MODULE_KEYS.forEach((k) => {
      const el = document.getElementById(`mod_${k}`);
      if (el) el.checked = true;
    });

    // Pre-generate a key
    try {
      const data = await api('/api/admin/licenses/generate-key', { method: 'POST' });
      modalKey.value = data.license_key;
    } catch {
      modalKey.value = '';
    }

    modal.style.display = 'flex';
    modalCustomer.focus();
  }

  async function openEditModal(id, focusUuid = false) {
    modalError.style.display = 'none';
    try {
      const lic = await api(`/api/admin/licenses/${id}`);
      modalTitle.textContent = `Lizenz bearbeiten: ${lic.customer_name}`;
      modalLicenseId.value = lic.id;
      modalCustomer.value = lic.customer_name;
      modalKey.value = lic.license_key;
      modalUuid.value = lic.instance_uuid || '';
      modalNotes.value = lic.notes || '';
      modalActive.checked = lic.is_active;

      if (lic.valid_until) {
        modalValidUntil.value = lic.valid_until;
        modalValidUntil.disabled = false;
        modalPerpetual.checked = false;
      } else {
        modalValidUntil.value = '';
        modalValidUntil.disabled = true;
        modalPerpetual.checked = true;
      }

      const mods = lic.modules || {};
      MODULE_KEYS.forEach((k) => {
        const el = document.getElementById(`mod_${k}`);
        if (el) el.checked = Boolean(mods[k]);
      });

      modal.style.display = 'flex';
      if (focusUuid) {
        modalUuid.focus();
        modalUuid.select();
      } else {
        modalCustomer.focus();
      }
    } catch (err) {
      alert(`Fehler beim Laden der Lizenz: ${err.message}`);
    }
  }

  function closeModal() {
    modal.style.display = 'none';
  }

  modalForm.onsubmit = async (e) => {
    e.preventDefault();
    modalError.style.display = 'none';
    const id = modalLicenseId.value;
    const isEdit = Boolean(id);

    const modules = {};
    MODULE_KEYS.forEach((k) => {
      const el = document.getElementById(`mod_${k}`);
      if (el) modules[k] = el.checked;
    });

    const payload = {
      customer_name: modalCustomer.value.trim(),
      license_key: modalKey.value.trim().toUpperCase(),
      instance_uuid: modalUuid.value.trim().toLowerCase(),
      valid_until: modalPerpetual.checked ? null : (modalValidUntil.value || null),
      is_active: modalActive.checked,
      notes: modalNotes.value.trim(),
      modules: modules
    };

    const saveBtn = document.getElementById('modalSaveBtn');
    saveBtn.disabled = true;
    saveBtn.textContent = 'Speichere …';

    try {
      if (isEdit) {
        await api(`/api/admin/licenses/${id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      } else {
        await api('/api/admin/licenses', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      }
      closeModal();
      loadData();
    } catch (err) {
      modalError.textContent = err.message;
      modalError.style.display = 'block';
    } finally {
      saveBtn.disabled = false;
      saveBtn.textContent = 'Speichern';
    }
  };

  // --- Audit Logs ---
  toggleLogsBtn.onclick = async () => {
    if (logsContainer.style.display === 'none') {
      logsContainer.style.display = 'block';
      toggleLogsBtn.textContent = 'Verlauf ausblenden';
      await loadAuditLogs();
    } else {
      logsContainer.style.display = 'none';
      toggleLogsBtn.textContent = 'Verlauf einblenden';
    }
  };

  async function loadAuditLogs() {
    try {
      const logs = await api('/api/admin/audit-logs?limit=40');
      if (!logs || logs.length === 0) {
        logsTableBody.innerHTML = '<tr><td colspan="6" class="text-center py-4">Keine Protokolleinträge vorhanden.</td></tr>';
        return;
      }
      logsTableBody.innerHTML = logs.map((log) => `
        <tr>
          <td>${formatRelativeTime(log.created_at)}</td>
          <td><b>${esc(log.action)}</b></td>
          <td>${log.license_key ? `<span class="code-pill">${esc(log.license_key)}</span>` : '–'}</td>
          <td>${log.instance_uuid ? `<span class="code-pill">${esc(log.instance_uuid)}</span>` : '–'}</td>
          <td>${esc(log.ip_address || '–')}</td>
          <td>${esc(log.details || '–')}</td>
        </tr>
      `).join('');
    } catch (err) {
      logsTableBody.innerHTML = `<tr><td colspan="6" class="text-center py-4" style="color:var(--bad)">Fehler: ${esc(err.message)}</td></tr>`;
    }
  }

  // Initial check
  checkAuth();
})();
