const test = require('node:test');
const assert = require('node:assert/strict');
const Awareness = require('../public/js/pet-awareness.js');
test('disabled, hidden, private or busy observation never schedules a frame', () => {
  const ready = { enabled:true, hidden:false, privateView:false, busy:false, now:20000,lastStarted:0 };
  assert.equal(Awareness.canObserve(ready), true);
  for(const patch of [{enabled:false},{hidden:true},{privateView:true},{busy:true},{now:9000}]) assert.equal(Awareness.canObserve({...ready,...patch}),false);
});
test('stable screen pixels do not require another model call', () => {
  assert.equal(Awareness.frameChanged(new Uint8Array([0,0,0,255,10,10,10,255]),new Uint8Array([0,0,0,255,10,10,10,255])),false);
  assert.equal(Awareness.frameChanged(null,new Uint8Array([0,0,0,255])),true);
  assert.equal(Awareness.frameChanged(new Uint8Array(400),new Uint8Array(400).fill(200)),true);
});
test('screen observations are bounded plain text', () => {
  assert.equal(Awareness.cleanObservation('  Hello\nthere  '),'Hello there');
  assert.ok(Awareness.cleanObservation('a'.repeat(1000)).length <= 300);
});
