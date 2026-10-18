// ─────────────────────────────────────────────────────────────
// Root App — routing + state + Tweaks integration
// ─────────────────────────────────────────────────────────────

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "density":      "comfortable",
  "accent":       "violet",
  "deltaSemantic":"inflation",
  "sidebarStyle": "light"
}/*EDITMODE-END*/;

function App() {
  const [view, setView] = React.useState('explorador');
  const [range, setRange] = React.useState('12 meses');
  const [currency, setCurrency] = React.useState('ARS');
  // ¿mostrar la marca en el sidebar? (cuando el hero grande no está a la vista, o no es el explorador)
  const [brandPinned, setBrandPinned] = React.useState(false);

  // Tweaks state
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);

  // navigate("empresa:coto") or navigate("explorador")
  const navigate = (target) => {
    setView(target);
    window.scrollTo({ top: 0 });
  };

  // Apply tweaks to the root element via data-attributes
  React.useEffect(() => {
    const root = document.documentElement;
    root.dataset.density = t.density;
    root.dataset.accent = t.accent;
    root.dataset.sidebar = t.sidebarStyle;
    root.dataset.delta = t.deltaSemantic;
  }, [t]);

  // Brand reveal: en el Explorador la marca vive en el hero grande; cuando el hero
  // sale de pantalla (scroll) la marca aparece en el sidebar. En otras vistas, directo.
  React.useEffect(() => {
    if (view !== 'explorador') { setBrandPinned(true); return; }
    setBrandPinned(false);
    const el = document.getElementById('heroBrand');
    if (!el) { setBrandPinned(true); return; }
    const io = new IntersectionObserver(
      ([e]) => setBrandPinned(!e.isIntersecting),
      { threshold: 0, rootMargin: '-8px 0px 0px 0px' }
    );
    io.observe(el);
    return () => io.disconnect();
  }, [view]);

  // Route
  let content;
  if (view.startsWith('empresa:')) {
    const id = view.slice('empresa:'.length);
    content = <EmpresaDetail empresaId={id} navigate={navigate} range={range} setRange={setRange} currency={currency} setCurrency={setCurrency}/>;
  } else if (view === 'empresas') {
    content = <Empresas navigate={navigate} range={range} setRange={setRange} currency={currency} setCurrency={setCurrency}/>;
  } else if (view === 'rubros') {
    content = <Rubros navigate={navigate} range={range} setRange={setRange} currency={currency} setCurrency={setCurrency}/>;
  } else if (view === 'comparador') {
    content = <Comparador navigate={navigate} range={range} setRange={setRange} currency={currency} setCurrency={setCurrency}/>;
  } else if (view === 'alertas') {
    content = <Alertas navigate={navigate} range={range} setRange={setRange} currency={currency} setCurrency={setCurrency}/>;
  } else if (view === 'api') {
    content = <ApiDocs navigate={navigate} range={range} setRange={setRange} currency={currency} setCurrency={setCurrency}/>;
  } else if (view === 'ajustes') {
    content = <Ajustes navigate={navigate} range={range} setRange={setRange} currency={currency} setCurrency={setCurrency}/>;
  } else {
    content = <Explorador navigate={navigate} range={range} setRange={setRange} currency={currency} setCurrency={setCurrency}/>;
  }

  return (
    <>
      <div className="app">
        <Sidebar view={view} navigate={navigate} brandPinned={brandPinned} />
        <main>
          {content}
        </main>
      </div>

      <TweaksPanel title="Tweaks">
        <TweakSection title="Apariencia">
          <TweakRadio
            label="Densidad"
            value={t.density}
            onChange={v => setTweak('density', v)}
            options={[
              {value:'compact',     label:'Compacta'},
              {value:'comfortable', label:'Cómoda'},
            ]}/>
          <TweakRadio
            label="Sidebar"
            value={t.sidebarStyle}
            onChange={v => setTweak('sidebarStyle', v)}
            options={[
              {value:'light', label:'Clara'},
              {value:'dark',  label:'Oscura'},
            ]}/>
        </TweakSection>

        <TweakSection title="Color">
          <TweakRadio
            label="Acento"
            value={t.accent}
            onChange={v => setTweak('accent', v)}
            options={[
              {value:'violet', label:'Violeta'},
              {value:'indigo', label:'Índigo'},
              {value:'teal',   label:'Teal'},
              {value:'rose',   label:'Rosa'},
            ]}/>
        </TweakSection>

        <TweakSection title="Datos">
          <TweakRadio
            label="Color de variación"
            value={t.deltaSemantic}
            onChange={v => setTweak('deltaSemantic', v)}
            options={[
              {value:'inflation', label:'Sube = rojo'},
              {value:'finance',   label:'Sube = verde'},
            ]}/>
        </TweakSection>
      </TweaksPanel>
    </>
  );
}
window.App = App;
