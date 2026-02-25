/* ==========================================================================
   Template Repo -- GitHub Pages Site
   Progressive enhancement: all features degrade gracefully without JS
   ========================================================================== */

(function () {
  "use strict";

  /* Mark JS as active so CSS can gate animations on .js class */
  document.documentElement.classList.add("js");

  var prefersReducedMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  ).matches;

  /* ---------- Mobile Nav Toggle ---------- */
  var navToggle = document.querySelector(".nav-toggle");
  var navLinks = document.querySelector(".nav-links");

  if (navToggle && navLinks) {
    navToggle.addEventListener("click", function () {
      var isOpen = navLinks.classList.toggle("open");
      navToggle.setAttribute("aria-expanded", String(isOpen));
      navToggle.textContent = isOpen ? "\u2715" : "\u2630";
    });

    /* Close menu on link click */
    navLinks.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", function () {
        navLinks.classList.remove("open");
        navToggle.setAttribute("aria-expanded", "false");
        navToggle.textContent = "\u2630";
      });
    });
  }

  /* ---------- Active Nav Tracking ---------- */
  var sections = document.querySelectorAll("section[id]");
  var navItems = document.querySelectorAll(".nav-links a");

  if (sections.length && navItems.length && "IntersectionObserver" in window) {
    var navObserver = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            var id = entry.target.getAttribute("id");
            navItems.forEach(function (item) {
              item.classList.toggle(
                "active",
                item.getAttribute("href") === "#" + id
              );
            });
          }
        });
      },
      { rootMargin: "-30% 0px -70% 0px" }
    );

    sections.forEach(function (section) {
      navObserver.observe(section);
    });
  }

  /* ---------- Scroll Reveal ---------- */
  var revealElements = document.querySelectorAll(".reveal");

  if (
    revealElements.length &&
    !prefersReducedMotion &&
    "IntersectionObserver" in window
  ) {
    var revealObserver = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("visible");
            revealObserver.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.1 }
    );

    revealElements.forEach(function (el) {
      revealObserver.observe(el);
    });
  } else {
    /* If reduced motion or no IO, show everything immediately */
    revealElements.forEach(function (el) {
      el.classList.add("visible");
    });
  }

  /* ---------- Stat Counter Animation ---------- */
  var statNumbers = document.querySelectorAll(".stat-number[data-target]");

  function animateCounter(el) {
    var target = parseInt(el.getAttribute("data-target"), 10);
    if (isNaN(target)) return;

    if (prefersReducedMotion) {
      el.textContent = target;
      return;
    }

    var duration = 1500;
    var start = 0;
    var startTime = null;

    function step(timestamp) {
      if (!startTime) startTime = timestamp;
      var progress = Math.min((timestamp - startTime) / duration, 1);
      /* Ease out cubic */
      var eased = 1 - Math.pow(1 - progress, 3);
      el.textContent = Math.round(eased * target);
      if (progress < 1) {
        requestAnimationFrame(step);
      } else {
        el.textContent = target;
      }
    }

    requestAnimationFrame(step);
  }

  if (statNumbers.length && "IntersectionObserver" in window) {
    var counterObserver = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            animateCounter(entry.target);
            counterObserver.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.5 }
    );

    statNumbers.forEach(function (el) {
      counterObserver.observe(el);
    });
  } else {
    statNumbers.forEach(function (el) {
      el.textContent = el.getAttribute("data-target");
    });
  }

  /* ---------- MCP Filter ---------- */
  var filterBtns = document.querySelectorAll(".filter-btn[data-filter]");
  var mcpCards = document.querySelectorAll(".mcp-card[data-category]");

  if (filterBtns.length && mcpCards.length) {
    filterBtns.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var filter = btn.getAttribute("data-filter");

        filterBtns.forEach(function (b) {
          b.classList.remove("active");
        });
        btn.classList.add("active");

        mcpCards.forEach(function (card) {
          if (filter === "all" || card.getAttribute("data-category") === filter) {
            card.style.display = "";
          } else {
            card.style.display = "none";
          }
        });
      });
    });
  }
})();
