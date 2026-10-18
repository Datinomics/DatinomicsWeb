// ─────────────────────────────────────────────────────────────
// Vista Explorador — pantalla principal
// ─────────────────────────────────────────────────────────────

function Explorador({ navigate, range, setRange, currency, setCurrency }) {
  const [filterRubro, setFilterRubro] = React.useState('Todos');
  const [filterRegion, setFilterRegion] = React.useState('Todas');
  const [orderBy, setOrderBy] = React.useState('yoy');
  const [orderDir, setOrderDir] = React.useState('desc');

  const empresas = React.useMemo(() => {
    let arr = [...EMPRESAS];
    if (filterRubro !== 'Todos') arr = arr.filter(e => e.rubro === filterRubro);
    if (filterRegion !== 'Todas') arr = arr.filter(e => e.region.includes(filterRegion));
    arr.sort((a,b) => {
      const va = a[orderBy], vb = b[orderBy];
      const cmp = typeof va === 'number' ? va - vb : String(va).localeCompare(String(vb));
      return orderDir === 'asc' ? cmp : -cmp;
    });
    return arr;
  }, [filterRubro, filterRegion, orderBy, orderDir]);

  const skuTotal = empresas.reduce((s, e) => s + e.skus, 0);
  const momProm  = empresas.reduce((s, e) => s + e.mom, 0) / empresas.length || 0;
  const yoyProm  = empresas.reduce((s, e) => s + e.yoy, 0) / empresas.length || 0;

  const toggleOrder = (key) => {
    if (orderBy === key) setOrderDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setOrderBy(key); setOrderDir('desc'); }
  };

  // top movers
  const top = [...EMPRESAS].sort((a,b) => b.mom - a.mom).slice(0, 5);
  const bottom = [...EMPRESAS].sort((a,b) => a.mom - b.mom).slice(0, 5);

  return (
    <div className="view">
      <TopBar
        brand
        title="Explorador de precios"
        subtitle="Todos los precios de la economía, en un solo lugar."
        range={range} currency={currency}
        onRange={setRange} onCurrency={setCurrency}
      />

      {/* Filters bar */}
      <div className="filters-bar">
        <div className="filters-lt">
          <Icon name="filter" size={14}/>
          <span className="filters-lbl">Filtros</span>
          <Dropdown value={filterRegion} onChange={setFilterRegion} options={['Todas','CABA','GBA','Multi','Nacional']} />
          <Dropdown value={filterRubro}  onChange={setFilterRubro}  options={['Todos', ...RUBROS.map(r=>r.nm)]} />
          <Dropdown value="Todas las ciudades" onChange={()=>{}} options={['Todas las ciudades','Buenos Aires','Córdoba','Rosario','Mendoza','La Plata']} />
          { (filterRubro!=='Todos' || filterRegion!=='Todas') && (
            <button className="filters-clear" onClick={() => { setFilterRubro('Todos'); setFilterRegion('Todas'); }}>
              Limpiar
            </button>
          )}
        </div>
        <div className="filters-rt mono">{empresas.length} empresas · {skuTotal} SKUs</div>
      </div>

      {/* KPI row */}
      <div className="kpi-row">
        <Kpi icon="building" label="Empresas"           value={empresas.length} delta="+2 esta semana" deltaTone="up" />
        <Kpi icon="grid"     label="SKUs relevados"     value={skuTotal}        delta="+18 este mes"    deltaTone="up" />
        <Kpi icon="bolt"     label="Var. mensual prom." value={fmtPct(momProm)} big />
        <Kpi icon="region"   label="Var. interanual"    value={fmtPct(yoyProm)} big />
      </div>

      {/* Chart + side panels */}
      <div className="explorer-grid">
        <div className="card">
          <SectionHead right={<span className="mono ink-3">jun '25 → may '26 · base 100</span>}>
            ÍNDICE DE PRECIOS
          </SectionHead>
          <AreaChart data={SERIE_GENERAL} labels={MESES} height={280}/>
          <div className="legend-row">
            <span className="legend-dot" style={{background:'var(--violet-700)'}}></span>
            <span>Índice general Datinomics</span>
            <span className="legend-sep">·</span>
            <span className="mono ink-3">Último: 145.3 (+45.3% i/a)</span>
          </div>
        </div>

        <div className="card">
          <SectionHead right={<a className="link" onClick={()=>navigate('rubros')}>Ver todos →</a>}>
            VARIACIÓN I/A POR RUBRO
          </SectionHead>
          <HBarChart
            items={[...RUBROS].sort((a,b)=>b.yoy-a.yoy).map(r => ({
              label: r.nm,
              value: r.yoy,
              color: 'var(--violet-700)',
            }))}
            max={50}
          />
        </div>
      </div>

      {/* Top movers + companies table */}
      <div className="movers-grid">
        <div className="card">
          <SectionHead right={<span className="mono ink-3">últimos 30 días</span>}>
            TOP MOVERS
          </SectionHead>
          <div className="movers-cols">
            <div>
              <div className="movers-h mono">▲ Subas</div>
              {top.map(e => (
                <button className="mover" key={e.id} onClick={() => navigate('empresa:'+e.id)}>
                  <span className="mover-nm">{e.nm}</span>
                  <span className="mover-rubro">{e.rubro}</span>
                  <span className="mover-pct up">{fmtPct(e.mom)}</span>
                </button>
              ))}
            </div>
            <div>
              <div className="movers-h mono">▼ Bajas</div>
              {bottom.map(e => (
                <button className="mover" key={e.id} onClick={() => navigate('empresa:'+e.id)}>
                  <span className="mover-nm">{e.nm}</span>
                  <span className="mover-rubro">{e.rubro}</span>
                  <span className={`mover-pct ${e.mom>0?'up':'down'}`}>{fmtPct(e.mom)}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="card">
          <SectionHead right={
            <div className="row-r mono">
              <button className="chip"><Icon name="download" size={12}/> CSV</button>
              <button className="chip"><Icon name="code" size={12}/> API</button>
            </div>
          }>
            EMPRESAS RELEVADAS
          </SectionHead>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th onClick={()=>toggleOrder('nm')}>Empresa</th>
                  <th onClick={()=>toggleOrder('rubro')}>Rubro</th>
                  <th>Región</th>
                  <th onClick={()=>toggleOrder('skus')} className="num">SKUs</th>
                  <th onClick={()=>toggleOrder('mom')} className="num">Mensual</th>
                  <th onClick={()=>toggleOrder('yoy')} className="num">Interanual</th>
                  <th>12 meses</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {empresas.map(e => (
                  <tr key={e.id} onClick={() => navigate('empresa:'+e.id)}>
                    <td>
                      <div className="emp-cell">
                        <div className="emp-avatar" style={{background: e.color}}>{e.nm.charAt(0)}</div>
                        <div>
                          <div className="emp-nm">{e.nm}</div>
                          <div className="emp-tk mono">{e.ticker}</div>
                        </div>
                      </div>
                    </td>
                    <td><span className="tag">{e.rubro}</span></td>
                    <td className="ink-2">{e.region}</td>
                    <td className="num mono">{e.skus}</td>
                    <td className="num"><Delta value={e.mom}/></td>
                    <td className="num"><Delta value={e.yoy}/></td>
                    <td>
                      <Sparkline data={makeSerie(e.yoy)} width={80} height={26} />
                    </td>
                    <td><Icon name="chevron" size={14}/></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
window.Explorador = Explorador;

// KPI card
function Kpi({ icon, label, value, delta, deltaTone='up', big=false }) {
  return (
    <div className="kpi">
      <div className="kpi-ic"><Icon name={icon} size={18}/></div>
      <div className="kpi-body">
        <div className="kpi-lbl">{label}</div>
        <div className={`kpi-val ${big?'big':''}`}>{value}</div>
        {delta && (
          <div className={`kpi-d ${deltaTone}`}>
            <span className="arr">{deltaTone==='up'?'▲':'▼'}</span>{delta}
          </div>
        )}
      </div>
    </div>
  );
}
window.Kpi = Kpi;
