// ─────────────────────────────────────────────────────────────
// AppShell — sidebar nav, top toolbar, live ticker, page chrome
// ─────────────────────────────────────────────────────────────

const Icon = ({ name, size=16 }) => {
  const props = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round" };
  const icons = {
    // ── Geometric custom set ──
    // Brujula / explorador: círculo perfecto + asa diagonal + punto data
    search: (<>
      <circle cx="10.5" cy="10.5" r="5.5" fill="none" stroke="currentColor" strokeWidth="2"/>
      <circle cx="10.5" cy="10.5" r="1.6" fill="currentColor" stroke="none"/>
      <line x1="14.6" y1="14.6" x2="20" y2="20" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"/>
    </>),
    // Edificio: bloque vertical con ventanas en grilla
    building: (<>
      <rect x="5" y="3.5" width="14" height="17" rx="1.5" fill="none" stroke="currentColor" strokeWidth="2"/>
      <rect x="8"  y="6.5" width="2.6" height="2.6" rx="0.4" fill="currentColor" stroke="none"/>
      <rect x="13.4" y="6.5" width="2.6" height="2.6" rx="0.4" fill="currentColor" stroke="none"/>
      <rect x="8"  y="11"  width="2.6" height="2.6" rx="0.4" fill="currentColor" stroke="none"/>
      <rect x="13.4" y="11"  width="2.6" height="2.6" rx="0.4" fill="currentColor" stroke="none"/>
      <rect x="10" y="15.5" width="4" height="5"  rx="0.6" fill="currentColor" stroke="none"/>
    </>),
    // Grilla: 4 cuadrados, uno relleno (rubro seleccionado)
    grid: (<>
      <rect x="3" y="3" width="8" height="8" rx="1.6" fill="currentColor" stroke="none"/>
      <rect x="13" y="3" width="8" height="8" rx="1.6" fill="none" stroke="currentColor" strokeWidth="2"/>
      <rect x="3" y="13" width="8" height="8" rx="1.6" fill="none" stroke="currentColor" strokeWidth="2"/>
      <rect x="13" y="13" width="8" height="8" rx="1.6" fill="none" stroke="currentColor" strokeWidth="2"/>
    </>),
    // Campana: hat + cuerpo + badillo
    bell: (<>
      <line x1="12" y1="2.5" x2="12" y2="4.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      <path d="M6.5 17 L17.5 17 L16.5 14 V11 a4.5 4.5 0 0 0 -9 0 V14 Z" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round"/>
      <circle cx="12" cy="20" r="1.6" fill="currentColor" stroke="none"/>
    </>),
    // Código: ⟨ I ⟩ con barra inclinada
    code: (<>
      <polyline points="9 7 4 12 9 17" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round"/>
      <polyline points="15 7 20 12 15 17" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round"/>
      <line x1="14" y1="6" x2="10" y2="18" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </>),
    // Ajustes: 3 sliders con puntos
    settings: (<>
      <line x1="4" y1="6" x2="20" y2="6"   stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      <line x1="4" y1="12" x2="20" y2="12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      <line x1="4" y1="18" x2="20" y2="18" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      <circle cx="16" cy="6"  r="2.4" fill="white" stroke="currentColor" strokeWidth="2"/>
      <circle cx="9"  cy="12" r="2.4" fill="white" stroke="currentColor" strokeWidth="2"/>
      <circle cx="14" cy="18" r="2.4" fill="white" stroke="currentColor" strokeWidth="2"/>
    </>),
    // Descargar: flecha hacia bandeja
    download: (<>
      <line x1="12" y1="3.5" x2="12" y2="14.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      <polyline points="7 10 12 15.5 17 10" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round"/>
      <line x1="4" y1="20" x2="20" y2="20" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </>),
    // Más
    plus: (<>
      <line x1="12" y1="5" x2="12" y2="19" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"/>
      <line x1="5" y1="12" x2="19" y2="12" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"/>
    </>),
    // Chevron derecha / abajo
    chevron:  (<polyline points="9 5 16 12 9 19" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round"/>),
    chevronD: (<polyline points="5 9 12 16 19 9" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round"/>),
    // Check
    check: (<polyline points="4 12.5 10 18 20 6.5" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinejoin="round" strokeLinecap="round"/>),
    // Cerrar
    x: (<>
      <line x1="6" y1="6" x2="18" y2="18" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"/>
      <line x1="18" y1="6" x2="6" y2="18" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"/>
    </>),
    // Volver
    back: (<>
      <line x1="20" y1="12" x2="5" y2="12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      <polyline points="11 6 5 12 11 18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round"/>
    </>),
    // Rayo (filled)
    bolt: (<polygon points="14 2.5 4.5 13.5 11 13.5 10 21.5 19.5 10.5 13 10.5 14 2.5" fill="currentColor" stroke="none"/>),
    // Región / pin de mapa
    region: (<>
      <path d="M12 21.5 C 12 21.5 5 14.5 5 10 a 7 7 0 0 1 14 0 c 0 4.5 -7 11.5 -7 11.5 Z" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"/>
      <circle cx="12" cy="10" r="2.6" fill="currentColor" stroke="none"/>
    </>),
    // Filtro (embudo)
    filter: (<path d="M4 5.5 L20 5.5 L14 12.5 L14 19 L10 17 L10 12.5 Z" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round"/>),
    // Pin (push-pin)
    pin: (<>
      <line x1="12" y1="14" x2="12" y2="21" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      <polygon points="6 8 18 8 16 14 8 14" fill="currentColor" stroke="none"/>
      <line x1="5" y1="8" x2="19" y2="8" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </>),
    // Info
    info: (<>
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="2"/>
      <rect x="11" y="10.5" width="2" height="6.5" rx="1" fill="currentColor" stroke="none"/>
      <circle cx="12" cy="7.5" r="1.4" fill="currentColor" stroke="none"/>
    </>),
    // Usuario
    user: (<>
      <circle cx="12" cy="8" r="4" fill="none" stroke="currentColor" strokeWidth="2"/>
      <path d="M4 20 a 8 8 0 0 1 16 0" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </>),
    // Flecha a derecha
    arrow: (<>
      <line x1="4" y1="12" x2="19" y2="12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      <polyline points="13 6 19 12 13 18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round"/>
    </>),
    // Libro
    book: (<>
      <path d="M5 3 H17 a2 2 0 0 1 2 2 V21 H7 a2 2 0 0 1 -2 -2 V3 Z" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"/>
      <line x1="9" y1="3" x2="9" y2="21" stroke="currentColor" strokeWidth="2"/>
    </>),
    // Play
    play: (<polygon points="6.5 4 20 12 6.5 20" fill="currentColor" stroke="none"/>),
    // Comparar: dos barras de distinta altura (una llena, una outline)
    compare: (<>
      <rect x="4" y="9" width="6" height="11" rx="1.5" fill="currentColor" stroke="none"/>
      <rect x="14" y="4" width="6" height="16" rx="1.5" fill="none" stroke="currentColor" strokeWidth="2"/>
    </>),
  };
  return <svg {...props}>{icons[name]}</svg>;
};
window.Icon = Icon;

// Brand logo (Pulse mark from brand system)
const LogoMark = ({ size=22 }) => (
  <svg className="logo-pulse" width={size} height={size} viewBox="0 0 120 120">
    <rect x="6"   y="50" width="10" height="20" rx="5" fill="oklch(0.78 0.12 290)"/>
    <rect x="22"  y="38" width="10" height="44" rx="5" fill="oklch(0.62 0.18 290)"/>
    <rect x="38"  y="22" width="10" height="76" rx="5" fill="oklch(0.48 0.20 290)"/>
    <rect x="54"  y="8"  width="12" height="104" rx="6" fill="oklch(0.36 0.18 290)"/>
    <rect x="72"  y="22" width="10" height="76" rx="5" fill="oklch(0.48 0.20 290)"/>
    <rect x="88"  y="38" width="10" height="44" rx="5" fill="oklch(0.62 0.18 290)"/>
    <rect x="104" y="50" width="10" height="20" rx="5" fill="oklch(0.78 0.12 290)"/>
    <circle cx="60" cy="8" r="6" fill="oklch(0.78 0.16 70)"/>
  </svg>
);
window.LogoMark = LogoMark;

// Mark alternativo (D-spike, del brand system) — para el sidebar, distinto al pulse del topbar
const SpikeMark = ({ size=30 }) => (
  <svg width={size} height={size} viewBox="0 0 120 120">
    <rect x="6" y="6" width="108" height="108" rx="24" fill="oklch(0.36 0.18 290)"/>
    <polyline points="18,82 38,68 54,86 70,42 86,58 102,30" fill="none" stroke="white" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round"/>
    <circle cx="70" cy="42" r="7.5" fill="oklch(0.78 0.16 70)" stroke="white" strokeWidth="3"/>
  </svg>
);
window.SpikeMark = SpikeMark;

// Sidebar
function Sidebar({ view, navigate, brandPinned }) {
  const navItems = [
    { id: 'explorador', nm: 'Explorador', icon: 'search' },
    { id: 'empresas',   nm: 'Empresas',   icon: 'building' },
    { id: 'rubros',     nm: 'Rubros',     icon: 'grid' },
    { id: 'comparador', nm: 'Comparador', icon: 'compare' },
    { id: 'alertas',    nm: 'Alertas',    icon: 'bell', badge: 3 },
  ];
  const resourceItems = [
    { id: 'api',       nm: 'API & docs', icon: 'code' },
    { id: 'ajustes',   nm: 'Ajustes',    icon: 'settings' },
  ];

  // Detail views map back to their parent for highlighting
  const activeId = view.startsWith('empresa:') ? 'empresas'
                 : view.startsWith('rubro:')   ? 'rubros'
                 : view;

  return (
    <aside className="sidebar">
      <div className={`sb-brand ${brandPinned ? 'show' : ''}`} onClick={() => navigate('explorador')}>
        <LogoMark size={26} />
        <span className="wm">Datinomics<span className="pt">.</span></span>
      </div>

      <div className="sb-section">Plataforma</div>
      <nav className="sb-nav">
        {navItems.map(it => (
          <button
            key={it.id}
            className={`sb-item ${activeId === it.id ? 'active' : ''}`}
            onClick={() => navigate(it.id)}>
            <Icon name={it.icon} size={18}/>
            <span>{it.nm}</span>
            {it.badge && <span className="sb-badge">{it.badge}</span>}
          </button>
        ))}
      </nav>

      <div className="sb-section">Recursos</div>
      <nav className="sb-nav">
        {resourceItems.map(it => (
          <button
            key={it.id}
            className={`sb-item ${activeId === it.id ? 'active' : ''}`}
            onClick={() => navigate(it.id)}>
            <Icon name={it.icon} size={18}/>
            <span>{it.nm}</span>
          </button>
        ))}
      </nav>

      <div className="sb-foot">
        un producto de <b>BERÁ</b>
      </div>
    </aside>
  );
}
window.Sidebar = Sidebar;

// Live ticker (top bar — shared by views)
function LiveTicker() {
  const items = [
    { c: 'Indumentaria', p: '+3.4%', up: true },
    { c: 'Tecnología', p: '+2.0%', up: true },
    { c: 'Construcción', p: '+1.7%', up: true },
    { c: 'Servicios', p: '+2.3%', up: true },
    { c: 'Salud', p: '+3.8%', up: true },
    { c: 'Alimentos', p: '+2.4%', up: true },
    { c: 'Combustibles', p: '−0.4%', up: false },
    { c: 'Educación', p: '+1.9%', up: true },
    { c: 'Turismo', p: '+4.1%', up: true },
  ];
  return (
    <div className="live-ticker">
      <div className="lt-tag"><span className="lt-dot"></span>EN VIVO</div>
      <div className="lt-items">
        {items.map((it, i) => (
          <React.Fragment key={i}>
            <span className="lt-cat">{it.c}</span>
            <span className={`lt-pct ${it.up?'up':'down'}`}>{it.p}<span className="lt-arr">{it.up?'▲':'▼'}</span></span>
            {i < items.length-1 && <span className="lt-sep">·</span>}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}
window.LiveTicker = LiveTicker;

// Top toolbar inside main content area (search + range + currency + cta)
function TopBar({ title, subtitle, searchPlaceholder='Buscar empresa, rubro o SKU…', onBack=null, range='12 meses', currency='ARS', onRange, onCurrency, brand=false }) {
  return (
    <header className="topbar">
      <div className="tb-title">
        {onBack && (
          <button className="tb-back" onClick={onBack} aria-label="Volver">
            <Icon name="back" size={18}/>
          </button>
        )}
        <div>
          {brand
            ? <div className="tb-lockup" id="heroBrand"><LogoMark size={64}/><span className="tb-wm">Datinomics<span className="pt">.</span></span></div>
            : <h1 className="tb-h1">{title}</h1>}
          {subtitle && <p className="tb-sub">{subtitle}</p>}
        </div>
      </div>
      <div className="tb-controls">
        <div className="tb-search">
          <Icon name="search" size={16}/>
          <input placeholder={searchPlaceholder} />
          <span className="kbd">⌘K</span>
        </div>
        <Dropdown value={range} onChange={onRange} options={['3 meses','12 meses','24 meses','5 años','Máx']} />
        <Dropdown value={currency} onChange={onCurrency} options={['ARS','USD','EUR']} compact />
      </div>
    </header>
  );
}
window.TopBar = TopBar;

// Generic dropdown
function Dropdown({ value, onChange, options, compact=false }) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef(null);
  React.useEffect(() => {
    const onDoc = (e) => { if (!ref.current?.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);
  return (
    <div className={`dd ${compact?'compact':''}`} ref={ref}>
      <button className="dd-btn" onClick={()=>setOpen(o=>!o)}>
        <span>{value}</span>
        <Icon name="chevronD" size={14}/>
      </button>
      {open && (
        <div className="dd-menu">
          {options.map(o => (
            <button key={o} className={`dd-opt ${o===value?'active':''}`} onClick={()=>{ onChange?.(o); setOpen(false); }}>
              {o}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
window.Dropdown = Dropdown;

// Section header (italic uppercase, matching their existing style)
function SectionHead({ children, right, tone='ink' }) {
  return (
    <div className={`sec-head tone-${tone}`}>
      <h2 className="sec-h2">{children}</h2>
      {right && <div className="sec-right">{right}</div>}
    </div>
  );
}
window.SectionHead = SectionHead;

// Delta badge (▲ +2.3)
function Delta({ value, withSign=true, inverted=false }) {
  // For inflation context: up = "bad" (red). For other contexts pass inverted
  const up = value > 0;
  const cls = inverted ? (up?'down':'up') : (up?'up':'down');
  const arrow = up ? '▲' : '▼';
  const sign = value > 0 && withSign ? '+' : '';
  return (
    <span className={`delta delta-${cls}`}>
      <span className="delta-arr">{arrow}</span>
      {sign}{Math.abs(value).toFixed(1)}
    </span>
  );
}
window.Delta = Delta;
