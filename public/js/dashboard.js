/* EMILIA LAB — action-focused home. Each source retains its own availability. */
(function () {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const norm = value => String(value || '').trim().toUpperCase();
  const done = new Set(['DONE', 'COMPLETED']);
  const active = new Set(['CREATED','ANALYZING','PLANNING','ASSIGNED','WORKING','QA_1','QA_2','IN_QA','REWORK','FINALIZING','QUEUED','RUNNING','READY']);
  const attention = new Set(['WAITING_APPROVAL','WAITING_FOR_APPROVAL','CLARIFICATION_REQUIRED','PAUSED','ERROR','FAILED','BLOCKED','CLARIFYING','WAITING_INPUT']);
  const labels = {CLARIFYING:'Needs clarification',WAITING_INPUT:'Needs your input',READY:'Ready to run',WAITING_APPROVAL:'Approval needed',WAITING_FOR_APPROVAL:'Approval needed',CLARIFICATION_REQUIRED:'Needs your input',QA_1:'QA review',QA_2:'Final QA',IN_QA:'QA review',ERROR:'Needs recovery',FAILED:'Failed'};
  const taskId = task => task.task_id || task.taskId;
  const taskTitle = task => task.request || task.request_text || task.title || 'Untitled task';
  const timestamp = item => { const value = item.updated_ts || item.updated_at || item.created_ts || item.created_at; return typeof value === 'number' ? (value < 1e12 ? value * 1000 : value) : Date.parse(value) || 0; };
  const recent = items => [...items].sort((a,b) => timestamp(b) - timestamp(a));
  function dateLabel(item) { const ts = timestamp(item); return ts ? new Date(ts).toLocaleDateString(undefined, {month:'short',day:'numeric'}) : ''; }
  function chip(state) {
    const key = norm(state);
    const tone = done.has(key) ? 'done' : attention.has(key) ? 'attention' : active.has(key) ? 'active' : 'neutral';
    const label = labels[key] || (key ? key.toLowerCase().replace(/_/g, ' ') : 'State unknown');
    return `<span class="studio-dash-chip is-${tone}">${esc(label)}</span>`;
  }
  async function collect() {
    const entries = [['tasks','listTasks'],['workers','listWorkers'],['conversations','listConversations'],['approvals','listApprovals'],['router','getModelRouter']];
    const results = await Promise.allSettled(entries.map(async ([key, method]) => {
      const result = await Api[method]();
      if (key === 'router' ? !result || typeof result !== 'object' || !result.providers || typeof result.providers !== 'object' : !Array.isArray(result)) throw Error('Invalid response');
      return result;
    }));
    return Object.fromEntries(entries.map(([key], i) => [key, { available: results[i].status === 'fulfilled', value: results[i].status === 'fulfilled' ? results[i].value : key === 'router' ? {} : [] }]));
  }
  const empty = (title, body) => `<div class="studio-dash-empty"><strong>${esc(title)}</strong><p>${esc(body)}</p></div>`;
  const unavailable = name => empty(`${name} unavailable`, 'This section could not be loaded. Refresh to try again.');
  const nav = (id, label) => `<button type="button" class="studio-dash-link" data-nav="${id}">${label}<span aria-hidden="true"> ↗</span></button>`;
  function taskRow(task, label) {
    return `<button type="button" class="studio-dash-row" data-task="${esc(taskId(task) || '')}" data-conversation="${esc(task.conversation_id || '')}"><span class="studio-dash-row-main"><span class="studio-dash-row-title">${esc(taskTitle(task))}</span><span class="studio-dash-row-meta">${esc(label || dateLabel(task) || 'Open task details')}</span></span>${chip(task.state)}<span class="studio-dash-arrow" aria-hidden="true">↗</span></button>`;
  }
  let generation = 0;
  async function render() {
    const root = $('dashRoot');
    if (!root) return;
    const request = ++generation;
    const focused = document.activeElement;
    const restoreRefresh = focused && focused.id === 'dashRefresh';
    root.setAttribute('aria-busy','true');
    if (!root.innerHTML.trim()) root.innerHTML = '<div class="studio-dash-loading" role="status">Loading your workspace…</div>';
    const refresh = $('dashRefresh');
    if (refresh) { refresh.disabled = true; refresh.textContent = 'Refreshing…'; }
    const d = await collect();
    if (request !== generation) return;
    const tasks = recent(d.tasks.value);
    const pending = d.approvals.value.filter(a => norm(a.status || 'PENDING') === 'PENDING');
    const approvalTaskIds = new Set(pending.map(taskId).filter(Boolean));
    const needsAttention = tasks.filter(t => attention.has(norm(t.state)) && !approvalTaskIds.has(taskId(t)));
    const count = pending.length + needsAttention.length;
    const shownCount = Math.min(pending.length, 4) + Math.min(needsAttention.length, 5 - Math.min(pending.length, 4));
    const incomplete = !d.tasks.available || !d.approvals.available;
    const providers = d.router.value.providers || {};
    const configured = [['Local', 'local_configured'],['OpenRouter','openrouter_configured'],['ChatAnywhere','chatanywhere_configured']].filter(([,key]) => providers[key]);
    root.innerHTML = `<div class="studio-dash">
      <header class="studio-dash-head"><div><h1>Your work, in view.</h1><p class="studio-dash-intro">Pick up where you left off, or give Main Brain a new goal.</p></div><div class="studio-dash-head-actions"><button type="button" class="studio-dash-button" id="dashRefresh" data-refresh aria-label="Refresh dashboard">Refresh</button><button type="button" class="studio-dash-button is-primary" data-nav="newChatItem"><span aria-hidden="true">＋</span> New task</button></div></header>
      <div class="studio-dash-layout"><div class="studio-dash-main">
        <section class="studio-dash-section studio-dash-attention" aria-labelledby="dashAttentionTitle"><div class="studio-dash-section-head"><div><h2 id="dashAttentionTitle">Needs your attention <span class="studio-dash-count" data-count="attention">${count}</span></h2></div>${nav('navTasksBtn','View tasks')}</div>
          ${incomplete ? '<p class="studio-dash-notice" role="status">Attention list is incomplete. Some work could not be loaded.</p>' : ''}
          ${!d.approvals.available ? unavailable('Approvals') : ''}
          ${pending.slice(0,4).map((a, i) => `<button type="button" class="studio-dash-row" data-approval-index="${i}"><span class="studio-dash-row-main"><span class="studio-dash-row-title">${esc(a.action || 'Review requested permission')}</span><span class="studio-dash-row-meta">${esc(a.reason || a.tool || 'Review the action before approving')}</span></span>${chip('WAITING_FOR_APPROVAL')}</button>`).join('')}
          ${needsAttention.slice(0, Math.max(0,5 - Math.min(pending.length,4))).map(t => taskRow(t)).join('')}
          ${!count && !incomplete ? empty('You’re clear to focus.', 'No approvals or blocked tasks need your attention. Start something new or return to recent work.') : ''}
          ${count > shownCount ? `<p class="studio-dash-footnote">${count - shownCount} more items in Tasks</p>` : ''}
        </section>
        <section class="studio-dash-section" aria-labelledby="dashRecentTitle"><div class="studio-dash-section-head"><h2 id="dashRecentTitle">Recent work</h2>${nav('navTasksBtn','All tasks')}</div>
          ${d.tasks.available ? `<div class="studio-dash-task-summary"><span><strong data-count="active">${tasks.filter(t => active.has(norm(t.state))).length}</strong> in progress</span><span><strong data-count="completed">${tasks.filter(t => done.has(norm(t.state))).length}</strong> completed</span><span>From ${tasks.length} loaded tasks</span></div>${tasks.slice(0,6).map(t => taskRow(t)).join('') || empty('No tasks yet.', 'Choose New task and describe what you want to accomplish.')}` : unavailable('Tasks')}
        </section>
        <section class="studio-dash-section" aria-labelledby="dashConversationsTitle"><div class="studio-dash-section-head"><h2 id="dashConversationsTitle">Continue a conversation</h2></div>${d.conversations.available ? recent(d.conversations.value).slice(0,3).map(c => `<button type="button" class="studio-dash-row" data-chat="${esc(c.id || c.conversation_id || '')}"><span class="studio-dash-conv-icon" aria-hidden="true">↳</span><span class="studio-dash-row-main"><span class="studio-dash-row-title">${esc(c.title || 'Untitled conversation')}</span><span class="studio-dash-row-meta">${esc(dateLabel(c) || 'Continue with Main Brain')}</span></span><span class="studio-dash-arrow" aria-hidden="true">↗</span></button>`).join('') || empty('A fresh page.', 'Your conversations will appear here when you start working with Main Brain.') : unavailable('Conversations')}</section>
      </div><aside class="studio-dash-aside" aria-label="Workspace resources">
        <section class="studio-dash-companion"><img src="/assets/emilia_portrait.jpg" alt="" width="76" height="96"><div><h2>A little space.<br>A lot of possibility.</h2><p>One goal at a time.</p></div></section>
        <section class="studio-dash-section"><div class="studio-dash-section-head"><h2>Your team</h2>${nav('navWorkersBtn','Manage')}</div>${d.workers.available ? `<p class="studio-dash-description">${d.workers.value.length} registered workers</p><div class="studio-dash-workers">${d.workers.value.slice(0,5).map(w => `<div class="studio-dash-worker"><span class="studio-dash-avatar" aria-hidden="true">${esc((w.name || w.worker_id || '?').slice(0,2).toUpperCase())}</span><span>${esc(w.name || w.worker_id || 'Worker')}</span></div>`).join('')}</div>${!d.workers.value.length ? empty('Build your team.', 'Add a worker to define a role and its capabilities.') : ''}${d.workers.value.length > 5 ? `<p class="studio-dash-footnote">+${d.workers.value.length - 5} more in your registry</p>` : ''}` : unavailable('Workers')}</section>
        <section class="studio-dash-section"><div class="studio-dash-section-head"><h2>Model providers</h2>${nav('navSettingsBtn','Settings')}</div>${d.router.available ? configured.map(([name]) => `<div class="studio-dash-provider"><span>${name}</span><span class="studio-dash-configured">Configured</span></div>`).join('') || empty('Connect a model.', 'Add a local or cloud provider in Settings to get started.') : unavailable('Model providers')}<p class="studio-dash-footnote">Configuration only. Connection health has not been checked.</p></section>
        <div class="studio-dash-resource-links">${nav('navProjectsBtn','Projects')}${nav('navVaultBtn','Vault notes')}${nav('navCodeBtn','Workspace files')}</div>
      </aside></div>
      <footer class="studio-dash-footer"><span>${Object.values(d).some(x => !x.available) ? 'Some sections unavailable' : 'Workspace snapshot'}</span><span>Updated ${esc(new Date().toLocaleTimeString(undefined,{hour:'2-digit',minute:'2-digit'}))}</span></footer>
    </div>`;
    root.removeAttribute('aria-busy');
    root.querySelectorAll('[data-refresh]').forEach(b => b.addEventListener('click', render));
    root.querySelectorAll('[data-nav]').forEach(b => b.addEventListener('click', () => { const target = $(b.dataset.nav); if (target) target.click(); }));
    root.querySelectorAll('[data-task]').forEach(b => b.addEventListener('click', async () => {
      await App.openTasksView();
      if (b.dataset.task) await Views.openTaskDetail(b.dataset.task);
    }));
    root.querySelectorAll('[data-approval-index]').forEach(b => b.addEventListener('click', () => {
      const approval = pending[Number(b.dataset.approvalIndex)];
      const requestId = approval.requestId || approval.request_id;
      const dialog = document.createElement('dialog');
      dialog.className = 'studio-approval-dialog';
      dialog.setAttribute('aria-label', 'Review requested permission');
      dialog.innerHTML = `<h2>Review permission</h2><p>${esc(approval.reason || 'A worker is requesting an action.')}</p><dl><dt>Action</dt><dd>${esc(approval.action || 'Not specified')}</dd><dt>Tool</dt><dd>${esc(approval.tool || 'Not specified')}</dd><dt>Worker</dt><dd>${esc(approval.workerId || approval.actor_id || approval.actorId || 'Not specified')}</dd></dl><p class="studio-approval-error" role="status"></p><div class="modal-actions"><button class="btn-secondary" data-close>Close</button><button class="btn-danger" data-decision="false" ${requestId ? '' : 'disabled'}>Deny</button><button class="btn-primary" data-decision="true" ${requestId ? '' : 'disabled'}>Approve action</button></div>`;
      document.body.appendChild(dialog);
      const parameters = document.createElement('pre');
      parameters.className = 'studio-approval-params';
      parameters.textContent = JSON.stringify(approval.params || {}, null, 2);
      parameters.setAttribute('aria-label', 'Requested action parameters');
      dialog.querySelector('.modal-actions').before(parameters);
      dialog.querySelector('[data-close]').onclick = () => dialog.close();
      dialog.addEventListener('close', () => { dialog.remove(); b.focus(); });
      dialog.querySelectorAll('[data-decision]').forEach(button => button.addEventListener('click', async () => {
        dialog.querySelectorAll('button').forEach(el => el.disabled = true);
        try {
          const response = await Api.resolveApproval(requestId, button.dataset.decision === 'true');
          if (response.error || response.detail || response.ok === false) throw Error(response.error || response.detail || 'Approval could not be saved.');
          dialog.close();
          await render();
        } catch (error) {
          dialog.querySelector('.studio-approval-error').textContent = 'Could not save your decision. Try again.';
          dialog.querySelectorAll('button').forEach(el => el.disabled = false);
        }
      }));
      dialog.showModal();
    }));
    root.querySelectorAll('[data-chat]').forEach(b => b.addEventListener('click', () => { if (b.dataset.chat) App.openChat(b.dataset.chat); }));
    if (restoreRefresh && $('dashRefresh')) $('dashRefresh').focus();
  }
  window.Dashboard = { render };
})();


