const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const modulePath = path.join(__dirname, '../public/js/pet-state.js');
const Pet = fs.existsSync(modulePath) ? require(modulePath) : {};
const noon = new Date(2026, 8, 16, 12).getTime();

test('loads without browser globals and exposes the browser global', () => {
  assert.equal(typeof Pet.create, 'function');
  const context = {};
  vm.runInNewContext(fs.readFileSync(modulePath, 'utf8'), context);
  assert.equal(typeof context.PetState.reduce, 'function');
});
test('sanitizes corrupt saves and drops untrusted identity and markup', () => {
  const state = Pet.create({mode:'hack',visible:'no',xp:Infinity,energy:-4,affection:999,
    position:{x:NaN,y:-90},outfit:{top:'none',bottom:'<script>',hair:'red'},identity:'other',lastRewardAt:Infinity}, noon);
  assert.equal(state.mode,'roam'); assert.equal(state.visible,true);
  assert.equal(state.xp,0); assert.equal(state.energy,0); assert.equal(state.affection,100);
  assert.equal(state.position.y,0); assert.ok(Number.isFinite(state.position.x));
  assert.equal(state.outfit.top,'default'); assert.equal(state.outfit.bottom,'default');
  assert.equal(state.identity,undefined); assert.equal(state.outfit.hair,undefined);
  assert.doesNotThrow(() => JSON.stringify(state));
  for (const bad of [null,[],false,'bad',42]) assert.equal(Pet.create(bad,noon).mode,'roam');
});
test('rewards first interaction at epoch zero and blocks repeated input rewards', () => {
  const initial = Pet.create(undefined,0);
  const first = Pet.reduce(initial,{type:'pet'},0);
  assert.ok(first.xp > 0); assert.equal(initial.xp,0);
  const repeated = Pet.reduce(first,{type:'play'},1);
  assert.equal(repeated.xp,first.xp);
  assert.ok(Pet.reduce(repeated,{type:'play'},30000).xp > first.xp);
});
test('daily reward cap persists through reload and resumes next day without absence penalty', () => {
  let state = Pet.create(undefined,noon);
  for(let i=0;i<200;i++) state=Pet.reduce(state,{type:'pet'},noon+i*30000);
  assert.equal(state.xp,120);
  state=Pet.create(JSON.parse(JSON.stringify(state)),noon+7000000);
  assert.equal(Pet.reduce(state,{type:'pet'},noon+7000000).xp,120);
  const later=Pet.create(state,noon+86400000*20);
  assert.equal(later.energy,state.energy); assert.equal(later.affection,state.affection);
  assert.ok(Pet.reduce(later,{type:'pet'},noon+86400000*20).xp>120);
});
test('feeding obeys its own cooldown and growth remains bounded', () => {
  const a=Pet.reduce(Pet.create({energy:20},noon),{type:'feed'},noon);
  const b=Pet.reduce(a,{type:'feed'},noon+30000);
  assert.equal(b.energy,a.energy); assert.equal(b.xp,a.xp);
  assert.ok(Pet.reduce(b,{type:'feed'},noon+60000).energy>a.energy);
  assert.equal(Pet.level(Pet.create({xp:-10},noon)),1);
  assert.ok(Pet.level(Pet.create({xp:1e30},noon))<=100);
});
test('wardrobe changes persist independently and cannot change identity', () => {
  const original=Pet.create(undefined,noon);
  const changed=Pet.reduce(original,{type:'outfit/set',slot:'top',item:'kimono'},noon);
  assert.equal(original.outfit.top,'default'); assert.equal(changed.outfit.top,'kimono');
  assert.equal(changed.outfit.bottom,'default');
  assert.deepEqual(Pet.create(JSON.parse(JSON.stringify(changed)),noon).outfit,changed.outfit);
  assert.deepEqual(Pet.reduce(changed,{type:'outfit/set',slot:'hair',item:'maid'},noon),changed);
  assert.equal(Pet.reduce(changed,{type:'outfit/set',slot:'top',item:'none'},noon).outfit.top,'default');
});
test('mode, visibility, position and activities use validated immutable transitions', () => {
  let state=Pet.create(undefined,noon);
  state=Pet.reduce(state,{type:'mode/set',mode:'bongo'},noon);
  state=Pet.reduce(state,{type:'visible/set',visible:false},noon);
  state=Pet.reduce(state,{type:'position/set',x:50,y:90},noon);
  state=Pet.reduce(state,{type:'activity/set',activity:'tea'},noon);
  assert.equal(state.mode,'bongo'); assert.equal(state.visible,false);
  assert.deepEqual(state.position,{x:50,y:90}); assert.equal(state.activity,'tea');
  assert.deepEqual(Pet.reduce(state,{type:'activity/set',activity:'typing'},noon),state);
});
test('bongo only reflects real focused input and releases on blur', () => {
  assert.equal(Pet.bongoPose(), 'idle');
  assert.equal(Pet.bongoPose({focused:true}), 'idle');
  assert.equal(Pet.bongoPose({focused:true,left:true}), 'left');
  assert.equal(Pet.bongoPose({focused:true,right:true}), 'right');
  assert.equal(Pet.bongoPose({focused:true,mouse:true}), 'right');
  assert.equal(Pet.bongoPose({focused:true,left:true,right:true}), 'both');
  assert.equal(Pet.bongoPose({focused:false,left:true,right:true,mouse:true}), 'idle');
});
test('time influences idle activity without synthesizing typing', () => {
  const night=new Date(2026,8,16,2).getTime();
  assert.equal(Pet.daypart(night),'night'); assert.equal(Pet.daypart(noon),'afternoon');
  assert.equal(Pet.chooseIdle(night,()=>0),'sleep');
  assert.notEqual(Pet.chooseIdle(noon,()=>0),'sleep');
  for(const r of [0,.2,.5,.8,.999]) assert.ok(['idle','walk','tea','magic','phone','greet','sleep'].includes(Pet.chooseIdle(noon,()=>r)));
});
test('passwords and private/settings ancestors are excluded without DOM globals', () => {
  assert.equal(Pet.isPrivateInput(null),false);
  assert.equal(Pet.isPrivateInput({tagName:'INPUT',type:'password'}),true);
  assert.equal(Pet.isPrivateInput({tagName:'TEXTAREA',closest:()=>null}),false);
  assert.equal(Pet.isPrivateInput({closest:selector=>selector.includes('data-private')?{}:null}),true);
  assert.equal(Pet.isPrivateInput({closest:selector=>selector.includes('#view-settings')?{}:null}),true);
});
