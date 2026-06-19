/* ============================================================
   SUNRISE CAFE & BAKERY — Website Scripts
   Artisan Bakery & Brunch Cafe | Austin, TX
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {
  // ==================== NAVBAR ====================
  const navbar = document.getElementById('navbar');
  const navToggle = document.getElementById('navToggle');
  const navLinks = document.getElementById('navLinks');

  const handleScroll = () => {
    navbar.classList.toggle('scrolled', window.scrollY > 50);
  };
  window.addEventListener('scroll', handleScroll, { passive: true });
  handleScroll();

  // Mobile menu toggle
  const closeMenu = () => {
    document.body.classList.remove('nav-open');
    navLinks.classList.remove('open');
    navToggle.classList.remove('active');
  };

  navToggle.addEventListener('click', () => {
    const isOpen = navLinks.classList.toggle('open');
    navToggle.classList.toggle('active', isOpen);
    document.body.classList.toggle('nav-open', isOpen);
  });

  navLinks.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', closeMenu);
  });

  // ==================== SMOOTH SCROLL ====================
  const SCROLL_OFFSET = 80;

  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', (e) => {
      const targetId = anchor.getAttribute('href');
      if (targetId === '#') return;

      const targetEl = document.querySelector(targetId);
      if (targetEl) {
        e.preventDefault();
        const top = targetEl.getBoundingClientRect().top + window.scrollY - SCROLL_OFFSET;
        window.scrollTo({ top, behavior: 'smooth' });
      }
    });
  });

  // ==================== ACTIVE NAV LINK ON SCROLL ====================
  const sections = document.querySelectorAll('section[id]');
  const navAnchors = document.querySelectorAll('.nav-links a');

  const highlightNav = () => {
    let current = '';
    sections.forEach(section => {
      const sectionTop = section.offsetTop - 120;
      if (window.scrollY >= sectionTop) {
        current = section.getAttribute('id');
      }
    });

    navAnchors.forEach(a => {
      a.classList.toggle('active', a.getAttribute('href') === `#${current}`);
    });
  };

  window.addEventListener('scroll', highlightNav, { passive: true });
  highlightNav();

  // ==================== SCROLL ANIMATIONS ====================
  const animatedElements = document.querySelectorAll('.animate-on-scroll');

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        const parent = entry.target.parentElement;
        const siblings = Array.from(parent.querySelectorAll('.animate-on-scroll'));
        const siblingIndex = siblings.indexOf(entry.target);
        const delay = siblingIndex * 100;

        setTimeout(() => {
          entry.target.classList.add('is-visible');
        }, delay);

        observer.unobserve(entry.target);
      }
    });
  }, { root: null, rootMargin: '0px 0px -60px 0px', threshold: 0.1 });

  animatedElements.forEach(el => observer.observe(el));

  // ==================== MENU CATEGORY FILTER ====================
  const menuTabs = document.querySelectorAll('.menu-tab');
  const menuCards = document.querySelectorAll('.menu-card');
  const bakerySpotlight = document.querySelector('.bakery-spotlight');

  menuTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      menuTabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');

      const category = tab.dataset.category;

      // The bakery spotlight is a hero strip for "All" / "Bakery"; hide it for others
      if (bakerySpotlight) {
        const showSpotlight = category === 'all' || category === 'bakery';
        bakerySpotlight.classList.toggle('spotlight-hidden', !showSpotlight);
      }

      let visibleIndex = 0;
      menuCards.forEach((card) => {
        const show = category === 'all' || card.dataset.category === category;
        card.classList.toggle('hidden', !show);

        if (show) {
          card.style.opacity = '0';
          card.style.transform = 'translateY(20px)';
          const i = visibleIndex++;
          setTimeout(() => {
            card.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
          }, i * 50);
        }
      });
    });
  });

  // ==================== NEWSLETTER FORM (Formspree) ====================
  const newsletterForm = document.getElementById('newsletterForm');
  const newsletterStatus = document.getElementById('newsletterStatus');

  if (newsletterForm) {
    newsletterForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const input = newsletterForm.querySelector('input[type="email"]');
      const btn = newsletterForm.querySelector('button');
      const email = input.value.trim();
      if (!email) return;

      const originalLabel = btn.textContent;
      btn.disabled = true;
      btn.textContent = 'Sending…';
      if (newsletterStatus) {
        newsletterStatus.textContent = '';
        newsletterStatus.classList.remove('error');
      }

      try {
        const res = await fetch(newsletterForm.action, {
          method: 'POST',
          body: new FormData(newsletterForm),
          headers: { Accept: 'application/json' },
        });

        if (res.ok) {
          newsletterForm.reset();
          btn.textContent = 'Subscribed!';
          if (newsletterStatus) {
            newsletterStatus.textContent = 'Thanks! Check your inbox to confirm. ☀️';
          }
        } else {
          throw new Error('Submission failed');
        }
      } catch (err) {
        btn.textContent = originalLabel;
        if (newsletterStatus) {
          newsletterStatus.classList.add('error');
          newsletterStatus.textContent = 'Something went wrong — please try again.';
        }
      } finally {
        btn.disabled = false;
        setTimeout(() => { btn.textContent = originalLabel; }, 3500);
      }
    });
  }

  // ==================== HERO PARALLAX ====================
  // Drives the background photo + glow layers and fades the content.
  const heroContent = document.getElementById('heroContent');
  const parallaxLayers = document.querySelectorAll('.hero-layer[data-speed]');
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  if (!prefersReducedMotion && (heroContent || parallaxLayers.length)) {
    let ticking = false;

    const updateParallax = () => {
      const y = window.scrollY;
      const vh = window.innerHeight;

      if (y < vh) {
        parallaxLayers.forEach(layer => {
          const speed = parseFloat(layer.dataset.speed) || 0.2;
          layer.style.transform = `translate3d(0, ${y * speed}px, 0)`;
        });
        if (heroContent) {
          heroContent.style.transform = `translateY(${y * 0.35}px)`;
          heroContent.style.opacity = String(Math.max(0, 1 - y / (vh * 0.75)));
        }
      }
      ticking = false;
    };

    window.addEventListener('scroll', () => {
      if (!ticking) {
        window.requestAnimationFrame(updateParallax);
        ticking = true;
      }
    }, { passive: true });

    updateParallax();
  }

  // ==================== TESTIMONIAL SLIDER ====================
  const track = document.getElementById('testimonialTrack');
  if (track) {
    const cards = track.querySelectorAll('.testimonial-card');
    const dotsContainer = document.getElementById('testimonialDots');
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    let currentSlide = 0;
    let slidesPerView = window.innerWidth >= 768 ? 2 : 1;
    let totalSlides = Math.ceil(cards.length / slidesPerView);

    function createDots() {
      if (!dotsContainer) return;
      dotsContainer.innerHTML = '';
      for (let i = 0; i < totalSlides; i++) {
        const dot = document.createElement('div');
        dot.className = `dot ${i === currentSlide ? 'active' : ''}`;
        dot.addEventListener('click', () => goToSlide(i));
        dotsContainer.appendChild(dot);
      }
    }

    function goToSlide(index) {
      currentSlide = index;
      const offset = -(currentSlide * (100 / slidesPerView)) * slidesPerView;
      track.style.transform = `translateX(${offset}%)`;

      if (dotsContainer) {
        dotsContainer.querySelectorAll('.dot').forEach((dot, i) => {
          dot.classList.toggle('active', i === currentSlide);
        });
      }
    }

    if (prevBtn) {
      prevBtn.addEventListener('click', () => {
        goToSlide(currentSlide > 0 ? currentSlide - 1 : totalSlides - 1);
      });
    }

    if (nextBtn) {
      nextBtn.addEventListener('click', () => {
        goToSlide(currentSlide < totalSlides - 1 ? currentSlide + 1 : 0);
      });
    }

    let autoPlay = setInterval(() => {
      goToSlide(currentSlide < totalSlides - 1 ? currentSlide + 1 : 0);
    }, 5000);

    const slider = document.getElementById('testimonialSlider');
    if (slider) {
      slider.addEventListener('mouseenter', () => clearInterval(autoPlay));
      slider.addEventListener('mouseleave', () => {
        autoPlay = setInterval(() => {
          goToSlide(currentSlide < totalSlides - 1 ? currentSlide + 1 : 0);
        }, 5000);
      });
    }

    window.addEventListener('resize', () => {
      const newPerView = window.innerWidth >= 768 ? 2 : 1;
      if (newPerView !== slidesPerView) {
        slidesPerView = newPerView;
        totalSlides = Math.ceil(cards.length / slidesPerView);
        currentSlide = 0;
        createDots();
        goToSlide(0);
      }
    });

    createDots();
  }
});
