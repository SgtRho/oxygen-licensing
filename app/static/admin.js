(() => {
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  let allLicenses = [];
  let currentFilter = 'all';
  let currentSearch = '';
  let pendingSetupCredentials = null;

  const MODULE_KEYS = [
    'starface',
    'server_reports',
    'server_report_backups',
    'warehouse',
    'advanced_documents',
    'tickets',
    'projects'
  ];

  const MODULE_LABELS = {
    starface: 'STARFACE',
    server_reports: 'Serverberichte',
    server_report_backups: 'Backups',
    warehouse: 'Lager',
    advanced_documents: 'Erw. Belege',
    tickets: 'Tickets',
    projects: 'Projekte'
  };

  // DOM Elements
  const loginSection = document.getElementById('loginSection');
  const loginCardCredentials = document.getElementById('loginCardCredentials');
  const loginCardTotpSetup = document.getElementById('loginCardTotpSetup');
  const dashboardSection = document.getElementById('dashboardSection');
  const headerActions = document.getElementById('headerActions');
  const userEmailBadge = document.getElementById('userEmailBadge');

  const loginForm = document.getElementById('loginForm');
  const adminEmailInput = document.getElementById('adminEmail');
  const adminPasswordInput = document.getElementById('adminPassword');
  const adminTotpInput = document.getElementById('adminTotp');
  const loginError = document.getElementById('loginError');
  const loginSubmitBtn = document.getElementById('loginSubmitBtn');
  const initialSetupNotice = document.getElementById('initialSetupNotice');
  const loginHeadTitle = document.getElementById('loginHeadTitle');
  const loginHeadSubtitle = document.getElementById('loginHeadSubtitle');
  const totpGroup = document.getElementById('totpGroup');

  // TOTP Setup Elements
  const qrCanvas = document.getElementById('qrCanvas');
  const setupSecretText = document.getElementById('setupSecretText');
  const copySecretBtn = document.getElementById('copySecretBtn');
  const otpauthAppLink = document.getElementById('otpauthAppLink');
  const totpSetupForm = document.getElementById('totpSetupForm');
  const setupTotpCode = document.getElementById('setupTotpCode');
  const setupError = document.getElementById('setupError');
  const cancelTotpSetupBtn = document.getElementById('cancelTotpSetupBtn');

  // Account Modal Elements
  const accountSettingsBtn = document.getElementById('accountSettingsBtn');
  const accountModal = document.getElementById('accountModal');
  const accountCloseBtn = document.getElementById('accountCloseBtn');
  const accountCancelBtn = document.getElementById('accountCancelBtn');
  const accountModalForm = document.getElementById('accountModalForm');
  const accNewEmail = document.getElementById('accNewEmail');
  const accNewPassword = document.getElementById('accNewPassword');
  const accCurrentPassword = document.getElementById('accCurrentPassword');
  const accTotpCode = document.getElementById('accTotpCode');
  const accountError = document.getElementById('accountError');
  const accountSuccess = document.getElementById('accountSuccess');

  // Dashboard & Table Elements
  const logoutBtn = document.getElementById('logoutBtn');
  const licenseTableBody = document.getElementById('licenseTableBody');
  const searchInput = document.getElementById('searchInput');
  const statusFilter = document.getElementById('statusFilter');
  const newLicenseBtn = document.getElementById('newLicenseBtn');

  // License Modal Elements
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
        showDashboard(me.email);
      } else {
        showLogin();
      }
    } catch {
      showLogin();
    }
  }

  async function showLogin() {
    loginSection.style.display = 'flex';
    loginCardCredentials.style.display = 'block';
    loginCardTotpSetup.style.display = 'none';
    dashboardSection.style.display = 'none';
    headerActions.style.display = 'none';
    adminPasswordInput.value = '';
    adminTotpInput.value = '';
    loginError.style.display = 'none';

    try {
      const status = await api('/api/admin/auth-status');
      if (status?.needs_initial_setup) {
        if (initialSetupNotice) initialSetupNotice.style.display = 'block';
        if (totpGroup) totpGroup.style.display = 'none';
        if (loginHeadTitle) loginHeadTitle.textContent = 'Administrator-Ersteinrichtung';
        if (loginHeadSubtitle) loginHeadSubtitle.textContent = 'Melden Sie sich mit Ihren .env-Daten an, um 2FA einzurichten.';
        loginSubmitBtn.textContent = 'Weiter zur 2FA-Einrichtung (QR-Code) →';
        if (status.admin_email && !adminEmailInput.value) {
          adminEmailInput.value = status.admin_email;
        }
      } else {
        if (initialSetupNotice) initialSetupNotice.style.display = 'none';
        if (totpGroup) totpGroup.style.display = 'block';
        if (loginHeadTitle) loginHeadTitle.textContent = 'Administrator-Anmeldung';
        if (loginHeadSubtitle) loginHeadSubtitle.textContent = 'Geben Sie Ihre Zugangsdaten und Ihren 2FA-Code ein.';
        loginSubmitBtn.textContent = 'Anmelden';
      }
    } catch {
      if (totpGroup) totpGroup.style.display = 'block';
    }

    if (adminEmailInput.value) {
      adminPasswordInput.focus();
    } else {
      adminEmailInput.focus();
    }
  }

  function showDashboard(email) {
    loginSection.style.display = 'none';
    dashboardSection.style.display = 'block';
    headerActions.style.display = 'flex';
    if (email && userEmailBadge) {
      userEmailBadge.textContent = `👤 ${email}`;
      accNewEmail.value = email;
    }
    loadData();
  }

  // --- Login Form Submit ---
  loginForm.onsubmit = async (e) => {
    e.preventDefault();
    loginError.style.display = 'none';
    const email = adminEmailInput.value.trim();
    const pwd = adminPasswordInput.value;
    const totp = adminTotpInput.value.trim();

    const isInitialSetup = totpGroup && totpGroup.style.display === 'none';
    loginSubmitBtn.disabled = true;
    loginSubmitBtn.textContent = isInitialSetup ? 'Prüfe Zugangsdaten …' : 'Anmeldung läuft …';

    try {
      const res = await api('/api/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: email,
          password: pwd,
          totp_code: totp || null
        })
      });

      if (res.require_totp_setup) {
        // First-time login: show TOTP Setup card with QR code
        pendingSetupCredentials = { email, password: pwd };
        showTotpSetup(res.totp_secret, res.otpauth_url);
        return;
      }

      if (res.require_totp) {
        // User has TOTP enabled, but didn't provide code: show input
        if (totpGroup) totpGroup.style.display = 'block';
        adminTotpInput.focus();
        loginError.textContent = 'Bitte geben Sie den 6-stelligen Authenticator-Code (TOTP) ein.';
        loginError.style.display = 'block';
        return;
      }

      if (res.ok) {
        showDashboard(res.email || email);
      }
    } catch (err) {
      loginError.textContent = err.message;
      loginError.style.display = 'block';
    } finally {
      loginSubmitBtn.disabled = false;
      loginSubmitBtn.textContent = isInitialSetup ? 'Weiter zur 2FA-Einrichtung (QR-Code) →' : 'Anmelden';
    }
  };

  // --- TOTP Setup Flow ---
  function showTotpSetup(secret, otpauthUrl) {
    loginCardCredentials.style.display = 'none';
    loginCardTotpSetup.style.display = 'block';
    setupError.style.display = 'none';
    setupTotpCode.value = '';

    // Format secret with spaces for readability: e.g. JBSW Y3DP EHPK 3PXP ...
    const formattedSecret = secret.match(/.{1,4}/g)?.join(' ') || secret;
    setupSecretText.textContent = formattedSecret;
    otpauthAppLink.href = otpauthUrl;

    copySecretBtn.onclick = () => {
      navigator.clipboard.writeText(secret).then(() => {
        const orig = copySecretBtn.textContent;
        copySecretBtn.textContent = 'Kopiert!';
        setTimeout(() => { copySecretBtn.textContent = orig; }, 1800);
      });
    };

    drawQRCode(qrCanvas, otpauthUrl);
    setupTotpCode.focus();
  }

  cancelTotpSetupBtn.onclick = () => {
    pendingSetupCredentials = null;
    showLogin();
  };

  totpSetupForm.onsubmit = async (e) => {
    e.preventDefault();
    if (!pendingSetupCredentials) {
      showLogin();
      return;
    }
    setupError.style.display = 'none';
    const code = setupTotpCode.value.trim();
    const btn = document.getElementById('confirmTotpBtn');
    btn.disabled = true;
    btn.textContent = 'Prüfe …';

    try {
      const res = await api('/api/admin/confirm-totp-setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: pendingSetupCredentials.email,
          password: pendingSetupCredentials.password,
          totp_code: code
        })
      });

      if (res.ok) {
        pendingSetupCredentials = null;
        showDashboard(res.email);
      }
    } catch (err) {
      setupError.textContent = err.message;
      setupError.style.display = 'block';
    } finally {
      btn.disabled = false;
      btn.textContent = '2FA aktivieren';
    }
  };

  // --- Logout ---
  logoutBtn.onclick = async () => {
    try {
      await api('/api/admin/logout', { method: 'POST' });
    } catch {}
    showLogin();
  };

  // --- Account Settings Modal ---
  accountSettingsBtn.onclick = () => {
    accountError.style.display = 'none';
    accountSuccess.style.display = 'none';
    accNewPassword.value = '';
    accCurrentPassword.value = '';
    accTotpCode.value = '';
    accountModal.style.display = 'flex';
  };

  accountCloseBtn.onclick = () => { accountModal.style.display = 'none'; };
  accountCancelBtn.onclick = () => { accountModal.style.display = 'none'; };

  accountModalForm.onsubmit = async (e) => {
    e.preventDefault();
    accountError.style.display = 'none';
    accountSuccess.style.display = 'none';

    const payload = {
      current_password: accCurrentPassword.value,
      new_email: accNewEmail.value.trim() || null,
      new_password: accNewPassword.value || null,
      totp_code: accTotpCode.value.trim()
    };

    const saveBtn = document.getElementById('accountSaveBtn');
    saveBtn.disabled = true;
    saveBtn.textContent = 'Speichere …';

    try {
      const res = await api('/api/admin/change-credentials', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      accountSuccess.textContent = res.message || 'Erfolgreich aktualisiert.';
      accountSuccess.style.display = 'block';
      if (payload.new_email) {
        userEmailBadge.textContent = `👤 ${payload.new_email}`;
      }
      setTimeout(() => {
        accountModal.style.display = 'none';
      }, 1500);
    } catch (err) {
      accountError.textContent = err.message;
      accountError.style.display = 'block';
    } finally {
      saveBtn.disabled = false;
      saveBtn.textContent = 'Änderungen speichern';
    }
  };

  // --- Dashboard Data Loading ---
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

      const activeMods = Object.entries(lic.modules || {})
        .filter(([k, v]) => v && k !== 'core')
        .map(([k]) => k);
      const modTags = ['<span class="tag tag-core">Core</span>']
        .concat(activeMods.map((m) => `<span class="tag tag-${esc(m)}">${esc(MODULE_LABELS[m] || m)}</span>`))
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

    document.querySelectorAll('.assign-uuid-btn').forEach((btn) => {
      btn.onclick = () => {
        const id = Number(btn.dataset.id);
        openEditModal(id, true);
      };
    });

    document.querySelectorAll('.edit-btn').forEach((btn) => {
      btn.onclick = () => {
        const id = Number(btn.dataset.id);
        openEditModal(id, false);
      };
    });

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

  // --- Modal: Create / Edit License ---
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

    document.querySelectorAll('.modules-grid input[type="checkbox"]').forEach((el) => {
      el.checked = true;
    });

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
      document.querySelectorAll('.modules-grid input[type="checkbox"]').forEach((el) => {
        const key = el.id.replace(/^mod_/, '');
        el.checked = Boolean(mods[key]);
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
    document.querySelectorAll('.modules-grid input[type="checkbox"]').forEach((el) => {
      const key = el.id.replace(/^mod_/, '');
      if (key) modules[key] = el.checked;
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

  // ============================================================
  // Offline Local QR Code Rendering (QRious)
  // ============================================================
  function drawQRCode(canvas, text) {
    if (window.QRious) {
      new window.QRious({
        element: canvas,
        value: text,
        size: 180,
        level: 'M'
      });
      return;
    }
    // Safe offline fallback
    const ctx = canvas.getContext('2d');
    const size = canvas.width;
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, size, size);
    ctx.fillStyle = '#0f172a';
    ctx.font = '12px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('Manuelle Eingabe', size / 2, size / 2 - 10);
    ctx.fillText('Schlüssel kopieren', size / 2, size / 2 + 10);
  }

  // Initial check
  checkAuth();
})();
