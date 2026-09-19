/* Serializable companion state. now is epoch milliseconds (optional: Date.now()).
 * Actions carry top-level fields: mode/set {mode}, visible/set {visible},
 * position/set {x,y} in pixels, outfit/set {slot,item}, activity/set {activity}.
 * feed, pet, play need only {type}. Rewards share a 30s cooldown; feed also
 * has a 60s cooldown. rewardDay/dailyXp persist the 120 XP local-calendar-day cap.
 * null timestamps mean never interacted, allowing an initial action at epoch 0.
 */
(function (root, factory) {
    if (typeof module === 'object' && module.exports) module.exports = factory();
    else root.PetState = factory();
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    'use strict';
    const slots = ['top', 'bottom', 'socks', 'shoes', 'headwear', 'glasses', 'earrings'];
    const items = ['default', 'casual', 'ice_queen', 'kimono', 'maid', 'swimsuit', 'base', 'none'];
    const activities = ['idle', 'walk', 'tea', 'magic', 'phone', 'greet', 'sleep', 'dragged'];
    const object = value => value && typeof value === 'object' && !Array.isArray(value) ? value : {};
    const number = (value, fallback, min, max) => typeof value === 'number' && Number.isFinite(value) ? Math.min(max, Math.max(min, value)) : fallback;
    const time = now => number(now instanceof Date ? now.getTime() : now, Date.now(), 0, 8640000000000000);
    function dateKey(now) {
        const date = new Date(now);
        return date.getFullYear() + '-' + (date.getMonth() + 1) + '-' + date.getDate();
    }
    function outfitItem(slot, item) {
        const fallback = slots.indexOf(slot) < 4 ? 'default' : 'none';
        if (!items.includes(item)) return fallback;
        return (slot === 'top' || slot === 'bottom') && item === 'none' ? 'default' : item;
    }
    function create(saved, now) {
        const current = time(now), source = object(saved), position = object(source.position);
        const outfit = {}, supplied = object(source.outfit), today = dateKey(current);
        slots.forEach(slot => { outfit[slot] = outfitItem(slot, supplied[slot]); });
        const timestamp = value => typeof value === 'number' && Number.isFinite(value) && value >= 0 ? Math.min(value, current) : null;
        return {
            version: 1,
            mode: source.mode === 'bongo' ? 'bongo' : 'roam',
            visible: typeof source.visible === 'boolean' ? source.visible : true,
            position: {x: number(position.x, 24, 0, 100000), y: number(position.y, 24, 0, 100000)},
            xp: Math.floor(number(source.xp, 0, 0, 9900)),
            energy: number(source.energy, 80, 0, 100),
            affection: number(source.affection, 50, 0, 100),
            outfit,
            activity: activities.includes(source.activity) ? source.activity : 'idle',
            lastRewardAt: timestamp(source.lastRewardAt),
            lastFeedAt: timestamp(source.lastFeedAt),
            rewardDay: today,
            dailyXp: source.rewardDay === today ? Math.floor(number(source.dailyXp, 0, 0, 120)) : 0
        };
    }
    function reduce(state, action, now) {
        const current = time(now), next = create(state, current), event = object(action);
        switch (event.type) {
        case 'mode/set':
            if (event.mode === 'roam' || event.mode === 'bongo') next.mode = event.mode;
            break;
        case 'visible/set':
            if (typeof event.visible === 'boolean') next.visible = event.visible;
            break;
        case 'position/set':
            next.position = {x: number(event.x, next.position.x, 0, 100000), y: number(event.y, next.position.y, 0, 100000)};
            break;
        case 'outfit/set':
            if (slots.includes(event.slot) && items.includes(event.item)) next.outfit[event.slot] = outfitItem(event.slot, event.item);
            break;
        case 'activity/set':
            if (activities.includes(event.activity)) next.activity = event.activity;
            break;
        case 'feed': case 'pet': case 'play': {
            if (event.type === 'feed' && next.lastFeedAt !== null && current - next.lastFeedAt < 60000) break;
            if (next.lastRewardAt !== null && current - next.lastRewardAt < 30000) break;
            const reward = Math.min(event.type === 'play' ? 8 : 5, 120 - next.dailyXp, 9900 - next.xp);
            next.xp += reward;
            next.dailyXp += reward;
            next.lastRewardAt = current;
            if (event.type === 'feed') {
                next.lastFeedAt = current;
                next.energy = Math.min(100, next.energy + 15);
                next.activity = 'tea';
            } else {
                next.affection = Math.min(100, next.affection + (event.type === 'pet' ? 3 : 2));
                next.activity = event.type === 'pet' ? 'greet' : 'magic';
            }
            break;
        }
        }
        return next;
    }
    function level(state) { return 1 + Math.floor(number(object(state).xp, 0, 0, 9900) / 100); }
    function daypart(now) {
        const hour = new Date(time(now)).getHours();
        return hour < 6 || hour >= 22 ? 'night' : hour < 12 ? 'morning' : hour < 18 ? 'afternoon' : 'evening';
    }
    function chooseIdle(now, random) {
        const part = daypart(now);
        const choices = part === 'night' ? ['sleep','sleep','idle','tea','phone'] :
            part === 'morning' ? ['greet','walk','tea','idle','magic'] : ['idle','walk','tea','magic','phone','greet'];
        const sample = number(typeof random === 'function' ? random() : Math.random(), 0, 0, 0.999999);
        return choices[Math.floor(sample * choices.length)];
    }
    function bongoPose(input) {
        const event = object(input);
        if (event.focused !== true) return 'idle';
        const left = event.left === true, right = event.right === true || event.mouse === true;
        return left && right ? 'both' : left ? 'left' : right ? 'right' : 'idle';
    }
    function isPrivateInput(element) {
        if (!element) return false;
        if (String(element.type || '').toLowerCase() === 'password') return true;
        if (typeof element.closest !== 'function') return false;
        return Boolean(element.closest('input[type="password"], [data-private], [data-pet-private], [data-sensitive], #view-settings, #settings, .settings-view, [data-view="settings"]'));
    }
    return Object.freeze({create, reduce, level, daypart, chooseIdle, bongoPose, isPrivateInput});
}));
