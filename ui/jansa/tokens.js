/* JANSA — Design tokens for dark + light themes.
   Apple/Tesla aesthetic: near-black or near-white canvas, a single
   luminous accent, muted status colors, generous whitespace.
   All values resolved at runtime via CSS custom properties so the
   theme can swap without a re-render. */

window.JANSA_TOKENS = {
  dark: {
    '--bg':          '#0A0A0B',
    '--bg-elev':     '#111113',
    '--bg-elev-2':   '#18181B',
    '--bg-chip':     '#222226',
    '--line':        'rgba(255,255,255,0.08)',
    '--line-2':      'rgba(255,255,255,0.14)',
    '--line-3':      'rgba(255,255,255,0.22)',
    '--text':        '#F5F5F7',
    '--text-2':      '#A1A1A6',
    '--text-3':      '#6E6E73',
    '--accent':      '#0A84FF',
    '--accent-soft': 'rgba(10,132,255,0.14)',
    '--good':        '#30D158',
    '--good-soft':   'rgba(48,209,88,0.14)',
    '--warn':        '#FFD60A',
    '--warn-soft':   'rgba(255,214,10,0.14)',
    '--bad':         '#FF453A',
    '--bad-soft':    'rgba(255,69,58,0.14)',
    '--neutral':     '#8E8E93',
    '--neutral-soft':'rgba(142,142,147,0.14)',
    '--shadow-lg':   '0 24px 48px -12px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.04)',
    '--blur-bg':     'rgba(10,10,11,0.72)',
  },
  light: {
    '--bg':          '#FAFAFA',
    '--bg-elev':     '#FFFFFF',
    '--bg-elev-2':   '#F4F4F5',
    '--bg-chip':     '#E8E8EA',
    '--line':        'rgba(0,0,0,0.08)',
    '--line-2':      'rgba(0,0,0,0.14)',
    '--line-3':      'rgba(0,0,0,0.22)',
    '--text':        '#1C1C1E',
    '--text-2':      '#48484A',
    '--text-3':      '#8E8E93',
    '--accent':      '#0A84FF',
    '--accent-soft': 'rgba(10,132,255,0.10)',
    '--good':        '#1E8E3E',
    '--good-soft':   'rgba(30,142,62,0.10)',
    '--warn':        '#B58100',
    '--warn-soft':   'rgba(181,129,0,0.10)',
    '--bad':         '#D70015',
    '--bad-soft':    'rgba(215,0,21,0.10)',
    '--neutral':     '#636366',
    '--neutral-soft':'rgba(99,99,102,0.10)',
    '--shadow-lg':   '0 24px 48px -12px rgba(0,0,0,0.18), 0 0 0 1px rgba(0,0,0,0.04)',
    '--blur-bg':     'rgba(255,255,255,0.78)',
  },
};

window.JANSA_FONTS = {
  ui:  "'SF Pro Display','Inter',-apple-system,BlinkMacSystemFont,'Helvetica Neue',sans-serif",
  num: "'SF Mono','JetBrains Mono','Menlo',monospace",
};

window.applyJansaTheme = function(name) {
  const t = window.JANSA_TOKENS[name] || window.JANSA_TOKENS.dark;
  const root = document.documentElement;
  for (const k in t) root.style.setProperty(k, t[k]);
  root.setAttribute('data-theme', name);
};

(function () {
  var activeTarget = null;
  var printHost = null;
  var cleanupTimer = null;
  var originalTitle = null;

  function escapeAttrValue(value) {
    if (window.CSS && typeof window.CSS.escape === "function") {
      return window.CSS.escape(value);
    }
    return String(value).replace(/\\/g, "\\\\").replace(/"/g, '\\"');
  }

  function cleanup() {
    if (cleanupTimer) {
      window.clearTimeout(cleanupTimer);
      cleanupTimer = null;
    }
    if (activeTarget) {
      activeTarget.classList.remove("jansa-print-active-target");
      activeTarget = null;
    }
    if (printHost && printHost.parentNode) {
      printHost.parentNode.removeChild(printHost);
      printHost = null;
    }
    document.body.removeAttribute("data-jansa-print-active");
    document.body.classList.remove("jansa-printing");
    if (originalTitle !== null) {
      document.title = originalTitle;
      originalTitle = null;
    }
  }

  window.addEventListener("afterprint", cleanup);

  window.JANSAPrint = {
    printTarget: function (targetId, options) {
      options = options || {};
      var id = String(targetId || "").trim();
      if (!id) return false;

      cleanup();

      var selector = '[data-jansa-print-target="' + escapeAttrValue(id) + '"]';
      var target = document.querySelector(selector);
      if (!target) {
        console.warn("[JANSAPrint] target not found:", id);
        return false;
      }

      printHost = document.createElement("div");
      printHost.id = "jansa-print-host";
      printHost.setAttribute("aria-hidden", "true");
      activeTarget = target.cloneNode(true);
      activeTarget.classList.add("jansa-print-active-target");
      printHost.appendChild(activeTarget);
      document.body.appendChild(printHost);
      document.body.setAttribute("data-jansa-print-active", id);
      document.body.classList.add("jansa-printing");

      if (options.title) {
        originalTitle = document.title;
        document.title = String(options.title);
      }

      cleanupTimer = window.setTimeout(cleanup, 3000);
      window.print();
      return true;
    },
    clear: cleanup,
  };
})();
