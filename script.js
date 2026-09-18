/**
 * EDITORIAL LUXURY WEDDING INVITATION CONTROLLER
 * Target Style: Editorial Luxury Invitation (white-pearls-template.vercel.app atmosphere)
 * Groom & Bride: Эрбол & Аделина
 * Date: October 20, 2026
 * Venue: Khan-Tengri Restaurant, Karakol
 */

// ==================== EDITORIAL CONFIGURATION ====================
const WEDDING_CONFIG = {
  groomName: "Эрбол",
  brideName: "Аделина",
  eventDateISO: "2026-10-20T15:00:00+06:00",
  venueCity: "Каракол шаары",
  venueAddress: "Гебзе көчөсү, 182 / 184",
  venueName: "«Хан-Тенгри» тойканасы",
  mapsUrl: "https://www.google.com/maps/search/?api=1&query=Khan+Tengri+restaurant+Karakol+Gebze+182",
  audioSrc: "https://cdn.pixabay.com/download/audio/2022/05/27/audio_1808fbf07a.mp3?filename=romantic-wedding-piano-112191.mp3"
};

document.addEventListener('DOMContentLoaded', () => {
  initGoldPetalsCanvas();
  initSurpriseOpeningSequence();
  initAudioPlayer();
  initCountdown();
  initScrollObserver();
  initTimelineProgress();
  initRSVPForm();
});

/* ==================== 1. FALLING GOLD PETALS & BOKEH CANVAS ==================== */
function initGoldPetalsCanvas() {
  const canvas = document.getElementById('ambientCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  let width = canvas.width = window.innerWidth;
  let height = canvas.height = window.innerHeight;

  window.addEventListener('resize', () => {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
  });

  const petals = [];
  const petalCount = Math.min(Math.floor(width / 16), 34);

  for (let i = 0; i < petalCount; i++) {
    petals.push({
      x: Math.random() * width,
      y: Math.random() * height,
      size: Math.random() * 3.5 + 1.5,
      rotation: Math.random() * Math.PI * 2,
      rotationSpeed: (Math.random() - 0.5) * 0.025,
      speedY: Math.random() * 0.5 + 0.2,
      speedX: Math.sin(Math.random() * Math.PI) * 0.35,
      alpha: Math.random() * 0.45 + 0.15
    });
  }

  function render() {
    ctx.clearRect(0, 0, width, height);

    petals.forEach(p => {
      p.y += p.speedY;
      p.x += Math.sin(p.y * 0.01) * 0.4;
      p.rotation += p.rotationSpeed;

      if (p.y > height + 10) {
        p.y = -10;
        p.x = Math.random() * width;
      }

      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rotation);
      ctx.beginPath();
      
      // Delicate gold petal shape
      ctx.ellipse(0, 0, p.size, p.size * 1.5, 0, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(197, 168, 128, ${p.alpha})`;
      ctx.shadowBlur = 6;
      ctx.shadowColor = 'rgba(216, 195, 168, 0.4)';
      ctx.fill();
      ctx.restore();
    });

    requestAnimationFrame(render);
  }

  render();
}

/* ==================== 2. SURPRISE OPENING SEQUENCE ==================== */
function initSurpriseOpeningSequence() {
  const openBtn = document.getElementById('openBtn');
  const envelope = document.getElementById('weddingEnvelope');
  const envelopeWrapper = document.getElementById('envelopeWrapper');
  const waxSeal = document.getElementById('waxSeal');
  const coverScreen = document.getElementById('coverScreen');
  const mainInvitation = document.getElementById('mainInvitation');
  const audio = document.getElementById('weddingAudio');
  const audioBtn = document.getElementById('audioBtn');
  const backdropPhoto = document.querySelector('.photo-bg-backdrop');

  if (!coverScreen || !mainInvitation) return;

  let opened = false;

  function triggerOpening() {
    if (opened) return;
    opened = true;

    // Step 1: Trigger 3D Envelope unfolding animation (Top flap opens 180deg, card slides out)
    if (envelope) {
      envelope.classList.add('opening');
    }

    // Step 2: Softly fade out open button
    if (openBtn) {
      openBtn.style.opacity = '0';
      openBtn.style.transform = 'translateY(10px)';
      openBtn.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
    }

    // Step 3: Play background wedding audio
    if (audio) {
      audio.play().then(() => {
        if (audioBtn) audioBtn.classList.add('playing');
      }).catch(err => {
        console.log("Autoplay deferred:", err);
      });
    }

    // Step 4: Background image backdrop transition
    if (backdropPhoto) {
      backdropPhoto.style.filter = 'blur(3px) brightness(0.96)';
    }

    // Step 5: Smooth transition into main invitation screen after envelope unfolds
    setTimeout(() => {
      mainInvitation.classList.remove('hidden-invitation');
      coverScreen.classList.add('unlocked');

      window.scrollTo({
        top: 0,
        behavior: 'smooth'
      });
    }, 1100);
  }

  if (openBtn) openBtn.addEventListener('click', triggerOpening);
  if (waxSeal) waxSeal.addEventListener('click', triggerOpening);
  if (envelopeWrapper) envelopeWrapper.addEventListener('click', triggerOpening);
}

/* ==================== 3. AUDIO PLAYER CONTROLLER ==================== */
function initAudioPlayer() {
  const audio = document.getElementById('weddingAudio');
  const audioBtn = document.getElementById('audioBtn');
  const audioIcon = document.getElementById('audioIcon');

  if (!audio || !audioBtn) return;

  audioBtn.addEventListener('click', () => {
    if (audio.paused) {
      audio.play().then(() => {
        audioBtn.classList.add('playing');
        if (audioIcon) audioIcon.textContent = '🎶';
      }).catch(err => {
        console.error("Audio playback error:", err);
      });
    } else {
      audio.pause();
      audioBtn.classList.remove('playing');
      if (audioIcon) audioIcon.textContent = '🎵';
    }
  });
}

/* ==================== 4. LIVE COUNTDOWN TIMER ==================== */
function initCountdown() {
  const targetTime = new Date(WEDDING_CONFIG.eventDateISO).getTime();

  const daysEl = document.getElementById('countDays');
  const hoursEl = document.getElementById('countHours');
  const minsEl = document.getElementById('countMinutes');
  const secsEl = document.getElementById('countSeconds');

  if (!daysEl || !hoursEl || !minsEl || !secsEl) return;

  function updateTimer() {
    const now = new Date().getTime();
    const distance = targetTime - now;

    if (distance < 0) {
      daysEl.textContent = "00";
      hoursEl.textContent = "00";
      minsEl.textContent = "00";
      secsEl.textContent = "00";
      return;
    }

    const days = Math.floor(distance / (1000 * 60 * 60 * 24));
    const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((distance % (1000 * 60)) / 1000);

    daysEl.textContent = days < 10 ? '0' + days : days;
    hoursEl.textContent = hours < 10 ? '0' + hours : hours;
    minsEl.textContent = minutes < 10 ? '0' + minutes : minutes;
    secsEl.textContent = seconds < 10 ? '0' + seconds : seconds;
  }

  updateTimer();
  setInterval(updateTimer, 1000);
}

/* ==================== 5. SCROLL INTERSECTION OBSERVER ==================== */
function initScrollObserver() {
  const sections = document.querySelectorAll('[data-reveal]');

  const observerOptions = {
    threshold: 0.12,
    rootMargin: '0px 0px -40px 0px'
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('active');
      }
    });
  }, observerOptions);

  sections.forEach(section => observer.observe(section));
}

/* ==================== 6. TIMELINE PROGRESS ANIMATION ==================== */
function initTimelineProgress() {
  const timelineItems = document.querySelectorAll('[data-timeline-item]');
  const progressBar = document.getElementById('timelineProgress');

  if (!timelineItems.length) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('active');
      }
    });

    const total = timelineItems.length;
    let visibleCount = 0;
    timelineItems.forEach(item => {
      if (item.classList.contains('active')) visibleCount++;
    });

    if (progressBar && total > 0) {
      const percentage = (visibleCount / total) * 100;
      progressBar.style.height = `${percentage}%`;
    }
  }, { threshold: 0.3 });

  timelineItems.forEach(item => observer.observe(item));
}

/* ==================== 7. RSVP FORM SUBMISSION ==================== */
function initRSVPForm() {
  const form = document.getElementById('rsvpForm');
  const successModal = document.getElementById('successModal');
  const modalCloseBtn = document.getElementById('modalCloseBtn');
  const backdrop = successModal ? successModal.querySelector('.modal-backdrop') : null;

  if (!form) return;

  form.addEventListener('submit', (e) => {
    e.preventDefault();

    const formData = new FormData(form);
    const guestData = {
      name: formData.get('guestName'),
      attendance: formData.get('attendance'),
      timestamp: new Date().toLocaleString('ru-RU', { timeZone: 'Asia/Bishkek' })
    };

    // Save locally to browser
    try {
      const existing = JSON.parse(localStorage.getItem('wedding_rsvp') || '[]');
      existing.push(guestData);
      localStorage.setItem('wedding_rsvp', JSON.stringify(existing));
    } catch(err) {
      console.log('Local storage save error:', err);
    }

    // 1. Send to FormSubmit cloud (delivered to adia.asakeeva.05@gmail.com and Erbolasakeev1@gmail.com 24/7)
    const emailPayload = {
      _subject: `Эрбол & Аделина — Жаңы конок жообу: ${guestData.name}`,
      "Коноктун аты-жөнү": guestData.name,
      "Катышуусу": guestData.attendance,
      "Убактысы": guestData.timestamp
    };

    // Primary email with CC
    fetch('https://formsubmit.co/ajax/adia.asakeeva.05@gmail.com', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify({
        ...emailPayload,
        _cc: 'Erbolasakeev1@gmail.com'
      })
    }).then(res => res.json()).then(data => {
      console.log('FormSubmit cloud response (adia):', data);
    }).catch(err => {
      console.log('FormSubmit cloud catch (adia):', err);
    });

    // Direct to Erbolasakeev1@gmail.com as well
    fetch('https://formsubmit.co/ajax/Erbolasakeev1@gmail.com', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify(emailPayload)
    }).then(res => res.json()).then(data => {
      console.log('FormSubmit cloud response (erbol):', data);
    }).catch(err => {
      console.log('FormSubmit cloud catch (erbol):', err);
    });

    // 2. Also send to local backend if running
    fetch('/api/rsvp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(guestData)
    }).catch(() => {});

    // 3. Prepare WhatsApp button on success modal
    const whatsappBtn = document.getElementById('modalWhatsappBtn');
    if (whatsappBtn) {
      const msg = encodeURIComponent(`Саламатсызбы! Эрбол & Аделина үйлөнүү тоюна чакырууга жооп:\n👤 Аты-жөнү: ${guestData.name}\n💌 Катышуусу: ${guestData.attendance}\n🤍`);
      whatsappBtn.href = `https://api.whatsapp.com/send?text=${msg}`;
      whatsappBtn.style.display = 'inline-flex';
    }

    if (successModal) {
      successModal.classList.add('active');
      successModal.setAttribute('aria-hidden', 'false');
    }

    form.reset();
  });

  const closeSuccess = () => {
    if (successModal) {
      successModal.classList.remove('active');
      successModal.setAttribute('aria-hidden', 'true');
    }
  };

  if (modalCloseBtn) modalCloseBtn.addEventListener('click', closeSuccess);
  if (backdrop) backdrop.addEventListener('click', closeSuccess);
}
