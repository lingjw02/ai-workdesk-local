const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../public/js/dashboard.js'), 'utf8');
async function render(overrides = {}) {
  const root = { innerHTML: '', setAttribute() {}, removeAttribute() {}, querySelectorAll: () => [] };
  const api = { listTasks: async () => [], listWorkers: async () => [], listConversations: async () => [], listApprovals: async () => [], getModelRouter: async () => ({ providers: {} }), ...overrides };
  const context = { window: {}, Api: api, document: { getElementById: id => id === 'dashRoot' ? root : { addEventListener() {} } }, console, Date };
  vm.runInNewContext(source, context);
  await context.window.Dashboard.render();
  return root.innerHTML;
}
test('task summaries use exact terminal states and recognize real attention states', async () => {
  const html = await render({ listTasks: async () => ['DONE', 'completed', 'WORKING', 'QA_1', 'ERROR', 'CLARIFICATION_REQUIRED', 'PAUSED', 'CANCELLED', 'UNDONE'].map((state, i) => ({state, task_id: String(i), request_text: state})) });
  assert.match(html, /data-count="completed">2</);
  assert.match(html, /data-count="active">2</);
  assert.match(html, /data-count="attention">3</);
});
test('pending approvals are case insensitive and deduplicated against waiting tasks', async () => {
  const html = await render({ listTasks: async () => [{ task_id: 't1', state: 'WAITING_FOR_APPROVAL' }], listApprovals: async () => [{ taskId: 't1', status: 'PENDING' }, { status: 'pending' }, { status: 'APPROVED' }] });
  assert.match(html, /data-count="attention">2</);
});
test('engine READY, CLARIFYING and WAITING_INPUT states receive meaningful classification', async () => {
  const html = await render({ listTasks: async () => [{ state: 'READY', request: 'Ready task' }, { state: 'CLARIFYING', request: 'Clarification task' }, { state: 'WAITING_INPUT', request: 'Input task' }] });
  assert.match(html, /data-count="active">1</);
  assert.match(html, /data-count="attention">2</);
  assert.match(html, /Clarification task/);
});
test('one rejected or malformed API response remains unavailable while other work renders', async () => {
  const html = await render({ listTasks: async () => { throw Error('offline'); }, listWorkers: async () => ({ detail: 'failure' }), listConversations: async () => [{ id: 'c1', title: 'Saved conversation' }] });
  assert.match(html, /Tasks unavailable/);
  assert.match(html, /Workers unavailable/);
  assert.match(html, /Saved conversation/);
  assert.doesNotMatch(html, /No tasks yet/);
});
test('provider configuration never implies online health and text is escaped', async () => {
  const html = await render({ getModelRouter: async () => ({ providers: { local_configured: true } }), listTasks: async () => [{ state: 'WORKING', request_text: '<img src=x onerror=alert(1)>' }] });
  assert.match(html, /Configured/);
  assert.doesNotMatch(html, /online/i);
  assert.match(html, /&lt;img/);
});


