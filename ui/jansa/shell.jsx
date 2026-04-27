/* JANSA shell — Sidebar + Topbar + Focus/Theme toggles + page router.
   CSS variables drive theme swap. No style-object collisions: all style
   objects prefixed with `shell`.

   ── CONNECTED VERSION ──
   Modified from prototype: App() loads data via jansaBridge before
   rendering. All visual components are identical to the standalone. */

const { useState, useEffect, useRef, useCallback } = React;

/* ── SVG icons — outline, 1.5px, matches SF Symbols weight ── */
const shellIcons = {
  overview: <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="2" width="6" height="6" rx="1.2"/><rect x="10" y="2" width="6" height="6" rx="1.2"/><rect x="2" y="10" width="6" height="6" rx="1.2"/><rect x="10" y="10" width="6" height="6" rx="1.2"/></svg>,
  executer: <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"><circle cx="9" cy="9" r="7"/><path d="M7 6.5 L12 9 L7 11.5 Z" fill="currentColor" stroke="none"/></svg>,
  runs: <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"><path d="M2 15 L6 10 L9 12 L15 4"/><circle cx="15" cy="4" r="1.4"/></svg>,
  consultants: <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"><circle cx="9" cy="6" r="3"/><path d="M3 16c0-3.3 2.7-5 6-5s6 1.7 6 5"/></svg>,
  contractors: <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"><rect x="2.5" y="6.5" width="13" height="9" rx="1.2"/><path d="M5 6.5 V4.5 a4 4 0 018 0 V6.5"/></svg>,
  discrepancies: <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"><path d="M9 2 L16.5 15 H1.5 Z"/><path d="M9 7 V10.5"/><circle cx="9" cy="13" r="0.6" fill="currentColor"/></svg>,
  reports: <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"><path d="M3.5 1.5 H11 L15 5.5 V16 a0.5 0.5 0 01-0.5 0.5 H3.5 a0.5 0.5 0 01-0.5-0.5 V2 a0.5 0.5 0 01.5-.5 Z"/><path d="M11 1.5 V5.5 H15"/><path d="M6 9 H12 M6 12 H10"/></svg>,
  settings: <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"><circle cx="9" cy="9" r="2.6"/><path d="M9 1.5 v2 M9 14.5 v2 M3.7 3.7 l1.4 1.4 M12.9 12.9 l1.4 1.4 M1.5 9 h2 M14.5 9 h2 M3.7 14.3 l1.4-1.4 M12.9 5.1 l1.4-1.4"/></svg>,
  sun: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"><circle cx="8" cy="8" r="3"/><path d="M8 1 v1.5 M8 13.5 V15 M1 8 h1.5 M13.5 8 H15 M2.8 2.8 l1 1 M12.2 12.2 l1 1 M2.8 13.2 l1-1 M12.2 3.8 l1-1"/></svg>,
  moon: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"><path d="M13 10 A6 6 0 113 6 a5 5 0 0010 4 Z"/></svg>,
  focus: <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"><path d="M2 5 V2 h3 M11 2 h3 v3 M14 11 v3 h-3 M5 14 H2 v-3"/><circle cx="8" cy="8" r="2"/></svg>,
  search: <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"><circle cx="6" cy="6" r="4.2"/><path d="M9.2 9.2 L12.5 12.5"/></svg>,
};

/* ── Sidebar — vivid gradient glyph, section labels, live badge ── */
function Sidebar({ active, onNav, focusMode, focusCount, runCount, consultantCount, contractorCount }) {
  const items = [
    { group: 'Pilotage', entries: [
      { id:'Overview',    label:'Vue d\u2019ensemble', icon: shellIcons.overview, badge: null },
      { id:'Executer',    label:'Ex\u00e9cuter',             icon: shellIcons.executer, badge: null },
      { id:'Runs',        label:'Runs',                 icon: shellIcons.runs,     badge: runCount || null },
    ]},
    { group: 'Acteurs', entries: [
      { id:'Consultants', label:'Consultants',          icon: shellIcons.consultants, badge: consultantCount || null },
      { id:'Contractors', label:'Entreprises',          icon: shellIcons.contractors, badge: contractorCount || null },
    ]},
    { group: 'Qualit\u00e9', entries: [
      { id:'Discrepancies', label:'\u00C9carts',        icon: shellIcons.discrepancies, badge: focusMode ? focusCount : null },
      { id:'Reports',     label:'Rapports',             icon: shellIcons.reports,     badge: null },
    ]},
    { group: 'Syst\u00e8me', entries: [
      { id:'Settings',    label:'Param\u00e8tres',           icon: shellIcons.settings, badge: null },
    ]},
  ];

  return (
    <aside style={{
      width: 232, flexShrink: 0,
      background: 'var(--bg-elev)',
      borderRight: '1px solid var(--line)',
      display: 'flex', flexDirection: 'column',
      fontFamily: window.JANSA_FONTS.ui,
      position: 'relative', zIndex: 2,
    }}>
      {/* Brand */}
      <div style={{ padding: '22px 20px 24px', display:'flex', alignItems:'center', gap: 12 }}>
        <div style={{
          width: 32, height: 32, borderRadius: 9,
          background: 'linear-gradient(135deg, #0A84FF 0%, #5E5CE6 55%, #BF5AF2 100%)',
          display:'flex', alignItems:'center', justifyContent:'center',
          boxShadow:'0 6px 18px -6px rgba(10,132,255,0.55)',
          position:'relative', overflow:'hidden',
        }}>
          <span style={{ fontFamily: window.JANSA_FONTS.ui, fontWeight: 700, color:'#fff', fontSize: 14, letterSpacing:'-.02em' }}>J</span>
          <div style={{
            position:'absolute', inset:0,
            background:'linear-gradient(135deg, rgba(255,255,255,0.25), transparent 45%)',
            pointerEvents:'none',
          }}/>
        </div>
        <div style={{ lineHeight: 1.15 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', letterSpacing: '-.01em' }}>JANSA</div>
          <div style={{ fontSize: 10.5, color: 'var(--text-3)', letterSpacing:'.08em', textTransform:'uppercase' }}>VISASIST</div>
        </div>
      </div>

      {/* Project pill — uses live data */}
      <div style={{ padding: '0 16px 12px' }}>
        <div style={{
          padding: '10px 12px', borderRadius: 10,
          background: 'var(--bg-elev-2)', border: '1px solid var(--line)',
          display:'flex', alignItems:'center', gap: 10,
        }}>
          <div style={{ width: 6, height: 6, borderRadius: 99, background: 'var(--good)', boxShadow:'0 0 6px var(--good)', flexShrink:0 }}/>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>P17&CO</div>
            <div style={{ fontSize: 10.5, color: 'var(--text-3)' }}>
              Tranche 2 {window.OVERVIEW ? '\u00b7 Run #' + window.OVERVIEW.run_number : ''}
            </div>
          </div>
        </div>
      </div>

      {/* Nav groups */}
      <nav style={{ padding: '4px 8px 16px', flex: 1, overflowY:'auto' }}>
        {items.map((grp, gi) => (
          <div key={gi} style={{ marginBottom: 14 }}>
            <div style={{
              padding: '10px 12px 6px',
              fontSize: 10, fontWeight: 600, color: 'var(--text-3)',
              letterSpacing: '.1em', textTransform: 'uppercase',
            }}>{grp.group}</div>

            {grp.entries.map(e => {
              const isActive = active === e.id;
              return (
                <button key={e.id}
                  onClick={() => onNav(e.id)}
                  style={{
                    width: '100%', display:'flex', alignItems:'center', gap: 11,
                    padding: '9px 12px', margin: '1px 0',
                    borderRadius: 9, border: 'none', background: 'transparent',
                    cursor: 'pointer', textAlign: 'left',
                    color: isActive ? 'var(--text)' : 'var(--text-2)',
                    fontFamily: 'inherit', fontSize: 13,
                    fontWeight: isActive ? 600 : 500,
                    position: 'relative', overflow: 'hidden',
                    transition: 'background 0.18s, color 0.18s',
                  }}
                  onMouseEnter={ev => { if (!isActive) ev.currentTarget.style.background = 'var(--bg-elev-2)'; }}
                  onMouseLeave={ev => { if (!isActive) ev.currentTarget.style.background = 'transparent'; }}
                >
                  {isActive && (
                    <div style={{
                      position:'absolute', left: 0, top: 6, bottom: 6, width: 3,
                      background: 'linear-gradient(180deg, #0A84FF, #5E5CE6)',
                      borderRadius: '0 3px 3px 0',
                    }}/>
                  )}
                  {isActive && (
                    <div style={{
                      position:'absolute', inset: 0,
                      background: 'linear-gradient(90deg, rgba(10,132,255,0.10), rgba(10,132,255,0.02) 70%)',
                      pointerEvents:'none',
                    }}/>
                  )}
                  <span style={{ color: isActive ? 'var(--accent)' : 'var(--text-3)', display:'inline-flex', position:'relative' }}>{e.icon}</span>
                  <span style={{ position:'relative', flex: 1 }}>{e.label}</span>
                  {e.badge != null && (
                    <span style={{
                      position:'relative',
                      fontSize: 10, padding:'2px 7px', borderRadius: 99,
                      background: isActive ? 'var(--accent-soft)' : 'var(--bg-chip)',
                      color: isActive ? 'var(--accent)' : 'var(--text-3)',
                      fontFamily: window.JANSA_FONTS.num, fontVariantNumeric:'tabular-nums',
                      fontWeight: 500,
                    }}>{e.badge}</span>
                  )}
                </button>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div style={{
        padding: '14px 16px', borderTop: '1px solid var(--line)',
        display:'flex', alignItems:'center', gap: 10,
      }}>
        <div style={{
          width: 30, height: 30, borderRadius: '50%',
          background:'linear-gradient(135deg, #FF9500, #FF375F)',
          display:'flex', alignItems:'center', justifyContent:'center',
          color:'#fff', fontSize: 11, fontWeight: 700,
        }}>EM</div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)' }}>Eid Maalouf</div>
          <div style={{ fontSize: 10.5, color: 'var(--text-3)' }}>OPC — Contr\u00f4le Visa</div>
        </div>
      </div>
    </aside>
  );
}

/* ── Topbar — breadcrumb + search + Focus toggle + Theme toggle ── */
function Topbar({ page, focusMode, setFocusMode, theme, setTheme, focusStats, staleDays, onStaleChange }) {
  return (
    <header style={{
      height: 60, flexShrink: 0,
      borderBottom: '1px solid var(--line)',
      background: 'var(--blur-bg)',
      backdropFilter: 'saturate(1.4) blur(20px)',
      WebkitBackdropFilter: 'saturate(1.4) blur(20px)',
      display:'flex', alignItems:'center', padding: '0 28px', gap: 20,
      fontFamily: window.JANSA_FONTS.ui,
      position:'sticky', top: 0, zIndex: 10,
    }}>
      <div style={{ display:'flex', alignItems:'baseline', gap: 10 }}>
        <span style={{ fontSize: 12, color: 'var(--text-3)', letterSpacing:'.08em', textTransform:'uppercase' }}>P17&CO</span>
        <span style={{ color: 'var(--text-3)' }}>/</span>
        <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)', letterSpacing:'-.01em' }}>{page}</span>
      </div>

      {/* Search */}
      <div style={{
        flex: 1, maxWidth: 420, margin: '0 auto',
        display:'flex', alignItems:'center', gap: 8,
        padding: '6px 12px', borderRadius: 8,
        background: 'var(--bg-elev-2)', border:'1px solid var(--line)',
        color: 'var(--text-3)',
      }}>
        {shellIcons.search}
        <input
          placeholder="Rechercher consultants, entreprises, documents\u2026"
          style={{
            flex: 1, border:'none', outline:'none', background:'transparent',
            fontFamily:'inherit', fontSize: 12.5, color:'var(--text)',
          }}
        />
        <span style={{
          fontFamily: window.JANSA_FONTS.num, fontSize: 10,
          padding:'1px 6px', borderRadius: 4,
          background:'var(--bg-chip)', color:'var(--text-3)',
          border:'1px solid var(--line)',
        }}>\u2318K</span>
      </div>

      {/* Controls */}
      <div style={{ display:'flex', alignItems:'center', gap: 10 }}>
        <FocusToggle
          focusMode={focusMode} setFocusMode={setFocusMode}
          stats={focusStats}
          staleDays={staleDays} onStaleChange={onStaleChange}
        />
        <ThemeToggle theme={theme} setTheme={setTheme}/>
      </div>
    </header>
  );
}

/* ── Focus toggle — pill with ripple + aperture icon rotation ── */
/* When focus is active, shows a ⚙ gear that opens a stale-threshold popover. */
function FocusToggle({ focusMode, setFocusMode, stats, staleDays, onStaleChange }) {
  const [showPopover, setShowPopover] = React.useState(false);
  return (
    <div style={{ position: 'relative', display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <button onClick={() => setFocusMode(m => !m)}
        style={{
          position:'relative',
          display:'flex', alignItems:'center', gap: 9,
          padding: '7px 13px', borderRadius: 99,
          background: focusMode
            ? 'linear-gradient(135deg, rgba(10,132,255,0.18), rgba(94,92,230,0.14))'
            : 'var(--bg-elev-2)',
          border: `1px solid ${focusMode ? 'rgba(10,132,255,0.45)' : 'var(--line)'}`,
          color: focusMode ? 'var(--accent)' : 'var(--text-2)',
          cursor:'pointer', fontFamily:'inherit', fontSize: 12, fontWeight: 600,
          letterSpacing:'.02em',
          transition:'all 0.22s cubic-bezier(.4,0,.2,1)',
          boxShadow: focusMode ? '0 0 0 4px rgba(10,132,255,0.08), 0 4px 12px -3px rgba(10,132,255,0.3)' : 'none',
        }}
      >
        <span style={{
          display:'inline-flex',
          transform: `rotate(${focusMode ? 45 : 0}deg)`,
          transition:'transform 0.35s cubic-bezier(.4,0,.2,1)',
        }}>{shellIcons.focus}</span>
        <span>Focus</span>
        {focusMode && stats && (
          <span style={{
            fontFamily: window.JANSA_FONTS.num, fontVariantNumeric:'tabular-nums',
            fontSize: 11, color: 'var(--text)',
            padding:'1px 7px', borderRadius: 99,
            background:'rgba(255,255,255,0.06)',
            border:'1px solid var(--line)',
          }}>{stats.focused}
            {stats.p1_overdue > 0 && <span style={{ color:'var(--bad)', marginLeft: 4 }}>{'\u00b7'} {stats.p1_overdue}</span>}
          </span>
        )}
      </button>

      {/* Gear button — visible only when focus mode is active.
          Always accent-coloured so it is clearly visible against the topbar. */}
      {focusMode && (
        <button
          onClick={() => setShowPopover(p => !p)}
          title="Seuil de p\u00e9remption"
          style={{
            width: 30, height: 30, borderRadius: 99,
            background: showPopover
              ? 'var(--accent)'
              : 'var(--accent-soft)',
            border: '1px solid rgba(10,132,255,0.50)',
            color: showPopover ? '#fff' : 'var(--accent)',
            cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 15, padding: 0,
            transition: 'all 0.18s',
            boxShadow: showPopover ? '0 0 0 3px rgba(10,132,255,0.2)' : 'none',
          }}
        >\u2699</button>
      )}

      {/* Stale-threshold popover */}
      {showPopover && focusMode && (
        <div style={{
          position: 'absolute', top: '110%', right: 0, zIndex: 200,
          background: 'var(--bg-elev)',
          border: '1px solid rgba(10,132,255,0.35)',
          borderRadius: 14, padding: 20, width: 260,
          boxShadow: '0 8px 32px -8px rgba(0,0,0,0.5)',
          fontFamily: window.JANSA_FONTS.ui,
        }}>
          <div style={{
            fontSize: 10.5, fontWeight: 600, letterSpacing: '.12em',
            textTransform: 'uppercase', color: 'var(--text-3)', marginBottom: 14,
          }}>Seuil de p\u00e9remption</div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
            <input
              type="range" min={30} max={365} step={15}
              value={staleDays != null ? staleDays : 90}
              onChange={e => onStaleChange && onStaleChange(Number(e.target.value))}
              style={{ flex: 1, accentColor: 'var(--accent)' }}
            />
            <span style={{
              fontSize: 12, fontWeight: 600, color: 'var(--accent)',
              fontVariantNumeric: 'tabular-nums', minWidth: 46, textAlign: 'right',
              fontFamily: window.JANSA_FONTS.num,
            }}>{staleDays != null ? staleDays : 90} j</span>
          </div>

          {stats && (
            <div style={{ borderTop: '1px solid var(--line)', paddingTop: 12 }}>
              <div style={{ fontSize: 11, color: 'var(--text-2)', marginBottom: 6 }}>
                Documents exclus\u00a0: {stats.excluded ?? '\u2014'}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 4 }}>
                \u00b7 R\u00e9solus\u00a0: {stats.resolved ?? 0}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 4 }}>
                \u00b7 P\u00e9rim\u00e9s (&gt;{staleDays != null ? staleDays : 90}j)\u00a0: {stats.stale ?? 0}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-3)' }}>
                \u00b7 Total trac\u00e9s\u00a0: {stats.total_dernier ?? 0}
              </div>
            </div>
          )}

          <button
            onClick={() => setShowPopover(false)}
            style={{
              marginTop: 14, fontSize: 11, color: 'var(--accent)',
              background: 'none', border: 'none', cursor: 'pointer',
              fontFamily: 'inherit', padding: 0,
            }}
          >Fermer</button>
        </div>
      )}
    </div>
  );
}

/* ── Theme toggle — sun/moon crossfade ── */
function ThemeToggle({ theme, setTheme }) {
  return (
    <button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
      title={theme === 'dark' ? 'Mode clair' : 'Mode sombre'}
      style={{
        position:'relative', width: 34, height: 34, borderRadius: 99,
        background:'var(--bg-elev-2)', border: '1px solid var(--line)',
        color: 'var(--text-2)', cursor:'pointer', padding: 0,
        display:'flex', alignItems:'center', justifyContent:'center',
        overflow:'hidden',
      }}>
      <span style={{
        position:'absolute', display:'inline-flex',
        transition:'transform 0.4s cubic-bezier(.4,0,.2,1), opacity 0.3s',
        transform: theme === 'dark' ? 'translateY(0) rotate(0)' : 'translateY(-200%) rotate(-60deg)',
        opacity: theme === 'dark' ? 1 : 0,
      }}>{shellIcons.moon}</span>
      <span style={{
        position:'absolute', display:'inline-flex',
        transition:'transform 0.4s cubic-bezier(.4,0,.2,1), opacity 0.3s',
        transform: theme === 'light' ? 'translateY(0) rotate(0)' : 'translateY(200%) rotate(60deg)',
        opacity: theme === 'light' ? 1 : 0,
      }}>{shellIcons.sun}</span>
    </button>
  );
}

/* ── Focus Cinema — full-screen zoom overlay played once per toggle ── */
function FocusCinema({ show, on }) {
  if (!show) return null;
  return (
    <div style={{
      position:'fixed', inset: 0, zIndex: 500, pointerEvents:'none',
      animation:'focusCinemaRise 650ms cubic-bezier(.2,.7,.2,1) forwards',
    }}>
      {/* Radial halo */}
      <div style={{
        position:'absolute', inset:0,
        background: on
          ? 'radial-gradient(circle at 50% 50%, rgba(10,132,255,0.28) 0%, rgba(10,132,255,0.04) 40%, transparent 70%)'
          : 'radial-gradient(circle at 50% 50%, rgba(10,132,255,0.14) 0%, transparent 65%)',
        animation:'focusCinemaFade 650ms cubic-bezier(.2,.7,.2,1) forwards',
      }}/>
      {/* Aperture ring */}
      <svg width="100%" height="100%" style={{ position:'absolute', inset:0 }}>
        <circle cx="50%" cy="50%" r="60" fill="none"
          stroke="rgba(10,132,255,0.55)" strokeWidth="1.5"
          style={{ transformOrigin:'center', animation:'focusCinemaRing 650ms cubic-bezier(.2,.7,.2,1) forwards' }}/>
        <circle cx="50%" cy="50%" r="120" fill="none"
          stroke="rgba(10,132,255,0.3)" strokeWidth="1"
          style={{ transformOrigin:'center', animation:'focusCinemaRing 700ms cubic-bezier(.2,.7,.2,1) 50ms forwards' }}/>
        <circle cx="50%" cy="50%" r="220" fill="none"
          stroke="rgba(10,132,255,0.15)" strokeWidth="1"
          style={{ transformOrigin:'center', animation:'focusCinemaRing 800ms cubic-bezier(.2,.7,.2,1) 100ms forwards' }}/>
      </svg>
      {/* Label */}
      <div style={{
        position:'absolute', top:'50%', left:'50%',
        transform:'translate(-50%, -50%)',
        fontFamily: window.JANSA_FONTS.ui,
        fontSize: 14, fontWeight: 600, letterSpacing:'.22em',
        color: 'var(--accent)', textTransform: 'uppercase',
        animation:'focusCinemaLabel 650ms cubic-bezier(.2,.7,.2,1) forwards',
      }}>
        {on ? 'Focus \u00b7 ON' : 'Focus \u00b7 OFF'}
      </div>
    </div>
  );
}

/* ── Loading screen — shown while backend data loads ── */
function LoadingScreen({ error }) {
  const F = window.JANSA_FONTS;
  return (
    <div style={{
      display:'flex', height:'100vh', width:'100vw',
      background:'var(--bg)', color:'var(--text)',
      fontFamily: F.ui,
      alignItems:'center', justifyContent:'center',
      flexDirection:'column', gap: 20,
    }}>
      <div style={{
        width: 48, height: 48, borderRadius: 14,
        background: 'linear-gradient(135deg, #0A84FF 0%, #5E5CE6 55%, #BF5AF2 100%)',
        display:'flex', alignItems:'center', justifyContent:'center',
        boxShadow:'0 8px 24px -6px rgba(10,132,255,0.55)',
      }}>
        <span style={{ fontWeight: 700, color:'#fff', fontSize: 20, letterSpacing:'-.02em' }}>J</span>
      </div>
      {error ? (
        <div style={{ textAlign:'center', maxWidth: 400 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--bad)', marginBottom: 8 }}>
            Erreur de connexion
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-2)' }}>{error}</div>
        </div>
      ) : (
        <div style={{ fontSize: 13, color: 'var(--text-3)', letterSpacing:'.06em' }}>
          Chargement des donn\u00e9es\u2026
        </div>
      )}
    </div>
  );
}

/* ── App Root — CONNECTED VERSION ──
   Loads data from backend via jansaBridge before rendering.
   Reloads on focus toggle. Loads fiche data on consultant navigate. */
function App() {
  const [active, setActive] = useState(() => localStorage.getItem('jansa_page') || 'Overview');
  const [focusMode, setFocusModeRaw] = useState(() => localStorage.getItem('jansa_focus') === '1');
  const [theme, setTheme] = useState(() => localStorage.getItem('jansa_theme') || 'dark');
  const [cinemaKey, setCinemaKey] = useState(0);
  const [cinemaOn, setCinemaOn] = useState(false);
  const [selectedConsultant, setSelectedConsultant] = useState(null);

  // ── Stale threshold (Step 11 — stale threshold control parity) ──
  const [staleDays, setStaleDaysRaw] = useState(() => {
    var v = parseInt(localStorage.getItem('jansa_stale') || '90', 10);
    return isNaN(v) ? 90 : v;
  });
  const staleDaysRef = useRef(staleDays);
  useEffect(() => { staleDaysRef.current = staleDays; }, [staleDays]);

  // ── Data loading state (NEW for connected version) ──
  const [dataReady, setDataReady] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const [dataVersion, setDataVersion] = useState(0);  // bump to force re-render after data reload
  const [reloading, setReloading] = useState(false);   // true while focus toggle reload is in flight

  // Ref mirror of focusMode — lets setFocusMode compute next value without
  // relying on stale closure captures or side effects inside state updaters.
  const focusModeRef = useRef(focusMode);
  useEffect(() => { focusModeRef.current = focusMode; }, [focusMode]);

  // Race-condition guard: only the latest toggle/stale request may apply its result
  const focusGenRef = useRef(0);

  // Debounce timer for stale-days slider reload
  const staleTimerRef = useRef(null);

  // Called by FocusToggle slider — updates state + debounced reload (400 ms)
  const onStaleChange = useCallback((days) => {
    setStaleDaysRaw(days);
    localStorage.setItem('jansa_stale', String(days));
    if (staleTimerRef.current) clearTimeout(staleTimerRef.current);
    staleTimerRef.current = setTimeout(() => {
      if (!focusModeRef.current || !window.jansaBridge.api) return;
      var gen = ++focusGenRef.current;
      setReloading(true);
      window.jansaBridge.refreshForFocus(focusModeRef.current, days).then(function () {
        if (gen === focusGenRef.current) {
          setDataVersion(function (v) { return v + 1; });
          setReloading(false);
        }
      }).catch(function () {
        if (gen === focusGenRef.current) setReloading(false);
      });
    }, 400);
  }, []);

  // Initial data load
  useEffect(() => {
    window.jansaBridge.init(focusMode, staleDaysRef.current).then(() => {
      setDataReady(true);
      if (window.jansaBridge.error) {
        setLoadError(window.jansaBridge.error);
      }
    }).catch(err => {
      setLoadError(err.message || String(err));
      setDataReady(true);  // Still show UI with placeholders
    });
  }, []);

  useEffect(() => { window.applyJansaTheme(theme); localStorage.setItem('jansa_theme', theme); }, [theme]);
  useEffect(() => { localStorage.setItem('jansa_page', active); }, [active]);
  useEffect(() => { localStorage.setItem('jansa_focus', focusMode ? '1' : '0'); }, [focusMode]);

  const setFocusMode = useCallback((updater) => {
    // 1. Compute next value from ref (always current, handles rapid clicks)
    const prev = focusModeRef.current;
    const next = typeof updater === 'function' ? updater(prev) : updater;
    focusModeRef.current = next;   // update ref immediately for subsequent rapid clicks

    // 2. Update React state (pure, no side effects)
    setFocusModeRaw(next);

    // 3. Cinema only when ENTERING focus mode
    if (next) {
      setCinemaOn(true);
      setCinemaKey(k => k + 1);
    }

    // 4. Show loading overlay immediately, then reload data
    if (window.jansaBridge.api) {
      const gen = ++focusGenRef.current;
      setReloading(true);
      window.jansaBridge.refreshForFocus(next, staleDaysRef.current).then(() => {
        // Only apply result if this is still the latest toggle request
        if (gen === focusGenRef.current) {
          setDataVersion(v => v + 1);
          setReloading(false);
        }
      }).catch(() => {
        if (gen === focusGenRef.current) {
          setReloading(false);
        }
      });
    }
  }, []);

  const focusStats = (window.OVERVIEW && window.OVERVIEW.focus) || { focused: 0, p1_overdue: 0 };

  const navigateTo = async (id, payload) => {
    if (id === 'ConsultantFiche') {
      const consultant = payload || (window.FICHE_DATA && window.FICHE_DATA.consultant);
      setSelectedConsultant(consultant);
      // Load fiche data from backend using canonical_name if available
      const apiName = (consultant && (consultant.canonical_name || consultant.name)) || '';
      if (apiName && window.jansaBridge.api) {
        await window.jansaBridge.loadFiche(apiName, focusMode, staleDaysRef.current);
        setDataVersion(v => v + 1);
      }
    }
    setActive(id);
  };

  if (!dataReady) {
    return <LoadingScreen error={loadError}/>;
  }

  // Dynamic badge counts from real data
  const runCount = (window.OVERVIEW && window.OVERVIEW.total_runs) || null;
  const consultantCount = (window.CONSULTANTS && window.CONSULTANTS.length) || null;
  const contractorCount = Object.keys(window.CONTRACTORS || {}).length || null;

  return (
    <div style={{
      display:'flex', height:'100vh', width:'100vw',
      background:'var(--bg)', color:'var(--text)',
      fontFamily: window.JANSA_FONTS.ui,
      overflow:'hidden',
      transition:'background 0.35s ease',
    }}>
      <Sidebar active={active} onNav={navigateTo} focusMode={focusMode} focusCount={focusStats.focused}
        runCount={runCount} consultantCount={consultantCount} contractorCount={contractorCount}/>

      <main style={{
        flex: 1, display:'flex', flexDirection:'column',
        minWidth: 0, position:'relative',
        transform: focusMode ? 'scale(0.995)' : 'scale(1)',
        transition:'transform 0.5s cubic-bezier(.2,.7,.2,1)',
      }}>
        <Topbar
          page={pageTitle(active)} focusMode={focusMode} setFocusMode={setFocusMode}
          theme={theme} setTheme={setTheme}
          focusStats={focusMode ? focusStats : null}
          staleDays={staleDays} onStaleChange={onStaleChange}
        />

        {/* Focus-mode vignette frame */}
        <div style={{
          position:'absolute', inset: '60px 0 0 0', pointerEvents:'none', zIndex: 4,
          boxShadow: focusMode ? 'inset 0 0 0 1px rgba(10,132,255,0.3), inset 0 0 120px rgba(10,132,255,0.08)' : 'inset 0 0 0 0 transparent',
          transition:'box-shadow 0.5s cubic-bezier(.2,.7,.2,1)',
        }}/>

        <div style={{ flex: 1, overflowY:'auto', position:'relative' }}>
          {/* Loading overlay — visible while focus toggle reload is in flight */}
          {reloading && (
            <div style={{
              position:'absolute', inset: 0, zIndex: 20,
              background: 'var(--bg)',
              display:'flex', alignItems:'center', justifyContent:'center',
              flexDirection:'column', gap: 14,
              animation: 'fadeInUp 0.15s ease-out',
            }}>
              <div style={{
                width: 36, height: 36, borderRadius: 10,
                background: 'linear-gradient(135deg, #0A84FF 0%, #5E5CE6 55%, #BF5AF2 100%)',
                display:'flex', alignItems:'center', justifyContent:'center',
                boxShadow:'0 6px 18px -6px rgba(10,132,255,0.55)',
              }}>
                <span style={{ fontWeight: 700, color:'#fff', fontSize: 15 }}>J</span>
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-3)', letterSpacing:'.06em' }}>
                Chargement des donn\u00e9es\u2026
              </div>
            </div>
          )}
          {active === 'Overview'       && <OverviewPage focusMode={focusMode} onNavigate={navigateTo}/>}
          {active === 'Consultants'    && <ConsultantsPage onOpen={(c) => navigateTo('ConsultantFiche', c)}/>}
          {active === 'ConsultantFiche'&& <ConsultantFichePage consultant={selectedConsultant} onBack={() => navigateTo('Consultants')} focusMode={focusMode}/>}
          {active === 'Contractors'    && <StubPage title="Entreprises" note="Laiss\u00e9 intact volontairement dans cette it\u00e9ration."/>}
          {active === 'Executer'       && <ExecuterPage onRunComplete={async () => {
            if (window.jansaBridge && window.jansaBridge.api) {
              try { await window.jansaBridge.refreshForFocus(focusMode, staleDaysRef.current); } catch (e) {}
              setDataVersion(v => v + 1);
            }
          }}/>}
          {active === 'Runs'           && <RunsPage/>}
          {active === 'Discrepancies'  && <StubPage title="\u00C9carts" note="Gestion des \u00e9carts \u2014 non retravaillé dans cette maquette."/>}
          {active === 'Reports'        && <ReportsPage/>}
          {active === 'Settings'       && <StubPage title="Param\u00e8tres" note="Pr\u00e9f\u00e9rences \u2014 non retravaillé dans cette maquette."/>}
        </div>
      </main>

      {/* Cinema animation — plays once per toggle */}
      <FocusCinema key={cinemaKey} show={cinemaKey > 0} on={cinemaOn}/>

      <style>{`
        @keyframes focusCinemaRise {
          0% { opacity: 0; }
          20% { opacity: 1; }
          100% { opacity: 0; }
        }
        @keyframes focusCinemaFade {
          0% { opacity: 0; transform: scale(0.6); }
          30% { opacity: 1; transform: scale(1); }
          100% { opacity: 0; transform: scale(1.4); }
        }
        @keyframes focusCinemaRing {
          0% { opacity: 0; transform: scale(0.3); }
          30% { opacity: 1; }
          100% { opacity: 0; transform: scale(2.2); }
        }
        @keyframes focusCinemaLabel {
          0% { opacity: 0; transform: translate(-50%, -50%) scale(0.8); letter-spacing: .08em; }
          30% { opacity: 1; transform: translate(-50%, -50%) scale(1); letter-spacing: .22em; }
          100% { opacity: 0; transform: translate(-50%, -50%) scale(1.1); letter-spacing: .32em; }
        }
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(8px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes drawLine {
          from { stroke-dashoffset: 1000; }
          to   { stroke-dashoffset: 0; }
        }
        ::-webkit-scrollbar { width: 10px; height: 10px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: var(--line-2); border-radius: 10px; border: 2px solid transparent; background-clip: padding-box; }
        ::-webkit-scrollbar-thumb:hover { background: var(--line-3); background-clip: padding-box; border: 2px solid transparent; }
      `}</style>
    </div>
  );
}

function pageTitle(id) {
  const map = {
    Overview: 'Vue d\u2019ensemble', Executer: 'Ex\u00e9cuter', Runs: 'Runs',
    Consultants: 'Consultants', ConsultantFiche: 'Fiche Consultant',
    Contractors: 'Entreprises', Discrepancies: '\u00C9carts',
    Reports: 'Rapports', Settings: 'Param\u00e8tres',
  };
  return map[id] || id;
}

function StubPage({ title, note }) {
  return (
    <div style={{ padding: 48, color: 'var(--text-2)' }}>
      <h1 style={{
        fontFamily: window.JANSA_FONTS.ui, fontSize: 40, fontWeight: 300,
        letterSpacing:'-.03em', color:'var(--text)', margin: 0,
      }}>{title}</h1>
      <p style={{ marginTop: 14, fontSize: 14 }}>{note}</p>
    </div>
  );
}

/* ── Reports page (Step 11 parity) ── */
function ReportsPage() {
  const [exporting, setExporting] = React.useState(false);
  const [exportResult, setExportResult] = React.useState(null);

  const handleExport = async () => {
    if (!window.jansaBridge || !window.jansaBridge.api) return;
    setExporting(true);
    setExportResult(null);
    try {
      const res = await window.jansaBridge.api.export_team_version();
      if (res && res.success) {
        setExportResult({ ok: true });
        if (window.jansaBridge.api.open_file_in_explorer && res.path) {
          window.jansaBridge.api.open_file_in_explorer(res.path);
        }
      } else {
        setExportResult({ ok: false, msg: (res && res.error) || 'Erreur export' });
      }
    } catch (e) {
      setExportResult({ ok: false, msg: String(e) });
    } finally {
      setExporting(false);
      setTimeout(() => setExportResult(null), 4000);
    }
  };

  return (
    <div style={{ padding: 48, maxWidth: 860, fontFamily: window.JANSA_FONTS.ui }}>
      <h1 style={{
        fontSize: 40, fontWeight: 300, letterSpacing: '-.03em',
        color: 'var(--text)', margin: '0 0 6px',
      }}>Rapports &amp; Exports</h1>
      <p style={{ marginTop: 0, marginBottom: 32, fontSize: 14, color: 'var(--text-2)' }}>
        G\u00e9n\u00e9rer et exporter les documents de suivi du projet.
      </p>

      {/* Tableau de Suivi VISA */}
      <div style={{
        background: 'var(--bg-elev)', border: '1px solid var(--line)',
        borderRadius: 16, padding: 24, marginBottom: 16,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 20,
      }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)', marginBottom: 4 }}>
            Tableau de Suivi VISA
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-2)' }}>
            Exporte le Grand Fichier enrichi (version \u00e9quipe)\u00a0\u2014
            {' '}<span style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--text-3)' }}>
              Tableau de suivi de visa DD_MM_YYYY.xlsx
            </span>
          </div>
        </div>
        <button
          onClick={handleExport}
          disabled={exporting}
          style={{
            flexShrink: 0,
            padding: '9px 18px', borderRadius: 9,
            background: 'var(--accent-soft)',
            border: '1px solid rgba(10,132,255,0.35)',
            color: 'var(--accent)',
            fontFamily: 'inherit', fontSize: 13, fontWeight: 500,
            cursor: exporting ? 'wait' : 'pointer',
            opacity: exporting ? 0.6 : 1,
            transition: 'opacity 0.15s',
          }}
        >
          {exporting ? 'Export en cours\u2026'
            : exportResult ? (exportResult.ok ? '\u2713 Export\u00e9' : '\u2717 Erreur')
            : 'Tableau de Suivi VISA'}
        </button>
      </div>

      {/* Other reports placeholder */}
      <div style={{
        background: 'var(--bg-elev)', border: '1px solid var(--line)',
        borderRadius: 16, padding: 24, opacity: 0.5,
      }}>
        <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-2)', marginBottom: 4 }}>
          Autres rapports
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-3)' }}>
          Fiches consultants, bilans entreprises \u2014 \u00e0 venir.
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { App, Sidebar, Topbar, FocusToggle, ThemeToggle, FocusCinema, LoadingScreen });
