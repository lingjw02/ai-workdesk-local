/* Shared navigation, keyboard access and workspace affordances. */
(() => {
  const $ = id => document.getElementById(id);
  const escape = value => String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const nav = [
    ['Home', 'navDashBtn'], ['New chat', 'newChatItem'], ['Projects', 'navProjectsBtn'],
    ['Tasks', 'navTasksBtn'], ['Workers', 'navWorkersBtn'], ['Project managers', 'navPmsBtn'],
    ['Team memory', 'navKnowledgeBtn'], ['Office suite', 'navSuiteBtn'], ['Code studio', 'navCodeBtn'],
    ['Media', 'navMediaBtn'], ['Companion', 'navCompanionBtn'], ['Vault notes', 'navVaultBtn'], ['Timer & alarms', 'navTimerBtn'],
    ['Calculator', 'navCalcBtn'], ['Remote devices', 'navRemoteBtn'], ['Activity', 'navAuditBtn'], ['Settings', 'navSettingsBtn']
  ];
  const viewNav = { companion: 'navCompanionBtn', dashboard: 'navDashBtn', chat: 'newChatItem', projects: 'navProjectsBtn', tasks: 'navTasksBtn', workers: 'navWorkersBtn', pms: 'navPmsBtn', suite: 'navSuiteBtn', code: 'navCodeBtn', media: 'navMediaBtn', vault: 'navVaultBtn', timer: 'navTimerBtn', calc: 'navCalcBtn', remote: 'navRemoteBtn', audit: 'navAuditBtn', settings: 'navSettingsBtn' };
  let commands = [];
  let selected = 0;
  let priorFocus;

  function setMobileNav(open) {
    document.body.classList.toggle('nav-open', open);
    $('mobileMenu').setAttribute('aria-expanded', String(open));
    $('sidebarBackdrop').hidden = !open;
    $('mobileMenu').setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
    syncSidebarAccess();
    if (open) {
      document.body.classList.remove('sidebar-collapsed');
      $('sidebar').classList.remove('collapsed');
      $('newProjectBtn').focus();
    }
  }

  function syncSidebarAccess() {
    const hidden = matchMedia('(max-width: 760px)').matches && !document.body.classList.contains('nav-open');
    $('sidebar').inert = hidden;
    $('sidebar').setAttribute('aria-hidden', String(hidden));
  }

  function renderCommands() {
    const query = $('commandInput').value.trim().toLowerCase();
    commands = nav.map(([label, id]) => ({ label, kind: 'Page', action: () => $(id)?.click() }));
    document.querySelectorAll('#chatList [data-chat]').forEach(el => {
      const label = el.querySelector('.label')?.textContent || 'Untitled conversation';
      commands.push({ label, kind: 'Chat', action: () => App.openChat(el.dataset.chat) });
    });
    commands = commands.filter(item => item.label.toLowerCase().includes(query));
    selected = 0;
    $('commandResults').innerHTML = commands.map((item, i) => `<button class="command-result${i === 0 ? ' selected' : ''}" data-command="${i}"><svg class="ico-svg" aria-hidden="true"><use href="#${item.kind === 'Chat' ? 'i-message' : 'i-compass'}"/></svg><span>${escape(item.label)}</span><small>${item.kind}</small></button>`).join('') || '<div class="placeholder">No matches. Try a page name such as Tasks or Vault.</div>';
  }

  function openCommands() {
    priorFocus = document.activeElement;
    $('commandInput').value = '';
    renderCommands();
    $('commandDialog').showModal();
    $('commandInput').focus();
  }

  function runCommand(index) {
    const command = commands[index];
    if (!command) return;
    $('commandDialog').close();
    command.action();
  }

  function updateConnection() {
    const connected = Api.ws?.readyState === WebSocket.OPEN;
    const status = $('studioConnection');
    const value = String(connected);
    if (status.dataset.connected !== value) {
      status.dataset.connected = value;
      status.lastElementChild.textContent = connected ? 'Server connected' : 'Reconnecting';
      status.title = connected ? 'Live connection to the local WorkDesk server. Model availability is shown separately in Settings.' : 'The local server connection is unavailable. Check that the server is running.';
    }
  }

  function enhanceGeneratedControls(root = document) {
    root.querySelectorAll('.side-item[data-chat], .side-item[data-project], .wf-desk[data-worker], .task-row[data-task], .pm-task-row[data-task]').forEach(el => {
      if (el.tagName !== 'BUTTON' && !el.hasAttribute('tabindex')) {
        el.tabIndex = 0;
        el.setAttribute('role', 'button');
        el.setAttribute('aria-label', el.querySelector('.label')?.textContent || el.textContent.trim());
      }
    });
    root.querySelectorAll('.ss-tab, .chat-tab, .wf-mode-btn, .cm-btn, .pill').forEach(el => {
      el.setAttribute('aria-pressed', String(el.classList.contains('active')));
    });
    root.querySelectorAll('.side-item').forEach(el => {
      const label = el.querySelector('.label')?.textContent.trim();
      if (label) el.setAttribute('title', label);
      if (el.classList.contains('active')) el.setAttribute('aria-current', 'page');
      else el.removeAttribute('aria-current');
    });
  }

  function init() {
    syncSidebarAccess();
    matchMedia('(max-width: 760px)').addEventListener('change', syncSidebarAccess);
    $('commandOpen').addEventListener('click', openCommands);
    $('commandClose').addEventListener('click', () => $('commandDialog').close());
    $('commandDialog').addEventListener('close', () => priorFocus?.focus());
    $('commandDialog').addEventListener('click', e => {
      if (e.target === $('commandDialog')) {
        const box = e.target.getBoundingClientRect();
        if (e.clientX < box.left || e.clientX > box.right || e.clientY < box.top || e.clientY > box.bottom) e.target.close();
      }
    });
    $('commandInput').addEventListener('input', renderCommands);
    $('commandResults').addEventListener('click', e => {
      const button = e.target.closest('[data-command]');
      if (button) runCommand(Number(button.dataset.command));
    });
    $('commandInput').addEventListener('keydown', e => {
      if (e.key === 'Enter') { e.preventDefault(); runCommand(selected); }
      if (['ArrowDown', 'ArrowUp'].includes(e.key) && commands.length) {
        e.preventDefault();
        selected = (selected + (e.key === 'ArrowDown' ? 1 : -1) + commands.length) % commands.length;
        $('commandResults').querySelectorAll('[data-command]').forEach((el, i) => el.classList.toggle('selected', i === selected));
        $('commandResults').querySelector(`[data-command="${selected}"]`)?.scrollIntoView({ block: 'nearest' });
      }
    });
    document.addEventListener('keydown', e => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); if (!$('commandDialog').open) openCommands(); }
      if (e.key === 'Escape' && document.body.classList.contains('nav-open')) { setMobileNav(false); $('mobileMenu').focus(); }
      if (['Enter', ' '].includes(e.key) && e.target.matches('[role="button"]:not(button)')) { e.preventDefault(); e.target.click(); }
      if (e.key === 'Tab' && document.body.classList.contains('nav-open')) {
        const elements = [...$('sidebar').querySelectorAll('button, summary, [tabindex="0"]')].filter(el => el.getClientRects().length && !el.disabled);
        const first = elements[0], last = elements.at(-1);
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
      }
    });
    $('mobileMenu').addEventListener('click', () => setMobileNav(!document.body.classList.contains('nav-open')));
    $('sidebarBackdrop').addEventListener('click', () => { setMobileNav(false); $('mobileMenu').focus(); });
    $('collapseBtn').addEventListener('click', () => {
      const collapsed = $('sidebar').classList.contains('collapsed');
      document.body.classList.toggle('sidebar-collapsed', collapsed);
      $('collapseBtn').setAttribute('aria-label', collapsed ? 'Expand navigation' : 'Collapse navigation');
    });
    $('sidebar').addEventListener('click', e => {
      if (e.target.closest('.side-item, #newProjectBtn')) setMobileNav(false);
    });
    document.addEventListener('studio:view', e => {
      const id = viewNav[e.detail];
      document.querySelectorAll('.side-item').forEach(el => el.classList.toggle('active', el.id === id));
      if (matchMedia('(max-width: 760px)').matches) setMobileNav(false);
      requestAnimationFrame(() => enhanceGeneratedControls());
    });
    document.querySelectorAll('[data-studio-pane]').forEach(button => button.addEventListener('click', () => {
      $('view-chat').dataset.mobilePane = button.dataset.studioPane;
      document.querySelectorAll('[data-studio-pane]').forEach(el => {
        const active = el === button;
        el.classList.toggle('active', active);
        el.setAttribute('aria-pressed', String(active));
      });
    }));
    document.querySelectorAll('.ss-tab').forEach(button => button.addEventListener('click', () => {
      if (!$('sessionSidebar').classList.contains('ss-open')) Views.toggleSessionSidebar();
    }));
    const divider = document.querySelector('.wf-resizer');
    divider.tabIndex = 0;
    divider.setAttribute('role', 'separator');
    divider.setAttribute('aria-label', 'Resize team panel');
    divider.setAttribute('aria-orientation', 'vertical');
    divider.setAttribute('aria-valuemin', '220');
    divider.setAttribute('aria-valuemax', '480');
    divider.setAttribute('aria-valuenow', '300');
    divider.addEventListener('keydown', e => {
      if (!['ArrowLeft', 'ArrowRight'].includes(e.key)) return;
      e.preventDefault();
      const pane = $('chatWorkflow');
      const width = Math.max(220, Math.min(480, pane.getBoundingClientRect().width + (e.key === 'ArrowRight' ? 20 : -20)));
      pane.style.flex = `0 0 ${width}px`;
      divider.setAttribute('aria-valuenow', String(width));
    });
    let pending = false;
    new MutationObserver(() => {
      if (!pending) { pending = true; requestAnimationFrame(() => { pending = false; enhanceGeneratedControls(); }); }
    }).observe($('main'), { childList: true, subtree: true });
    new MutationObserver(() => enhanceGeneratedControls($('sidebar'))).observe($('sidebar'), { childList: true, subtree: true });
    document.addEventListener('click', () => requestAnimationFrame(() => enhanceGeneratedControls()));
    enhanceGeneratedControls();
    updateConnection();
    setInterval(updateConnection, 2000);
  }
  document.addEventListener('DOMContentLoaded', init);
})();
