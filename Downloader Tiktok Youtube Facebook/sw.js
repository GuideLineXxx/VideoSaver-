self.addEventListener('install', (e) => {
  console.log('[Service Worker] Install');
});

self.addEventListener('fetch', (e) => {
  // Hanya bypass fetch untuk fungsi dasar offline, 
  // karena aplikasi butuh backend hidup untuk download video.
});
