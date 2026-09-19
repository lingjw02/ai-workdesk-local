(function(root, factory) {
  if(typeof module === 'object' && module.exports) module.exports = factory();
  else root.PetAwareness = factory();
})(globalThis, function() {
  return Object.freeze({
    canObserve: s => !!s.enabled && !s.hidden && !s.privateView && !s.busy && s.now - s.lastStarted >= 10000,
    frameChanged: (a,b) => {
      if(!a || a.length !== b.length) return true;
      let difference = 0;
      for(let i=0;i<b.length;i+=4) difference += Math.abs(a[i]-b[i])+Math.abs(a[i+1]-b[i+1])+Math.abs(a[i+2]-b[i+2]);
      return difference / Math.max(1,b.length / 4 * 3) > 3;
    },
    cleanObservation: text => String(text || '').replace(/\s+/g,' ').trim().slice(0,300)
  });
});
