(function() {
  const isNative = typeof Capacitor !== 'undefined';
  if (!isNative) return;

  window.astrochino = {
    isNative: true,
    isIOS: Capacitor.getPlatform() === 'ios',
    isAndroid: Capacitor.getPlatform() === 'android',
  };
})();
