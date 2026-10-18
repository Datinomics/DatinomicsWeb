// ─────────────────────────────────────────────────────────────
// Vista Comparador — la empresa carga sus SKUs y se compara contra
// otras empresas (filtros por rubro/región + selección personalizada)
// ─────────────────────────────────────────────────────────────

function Comparador({ navigate, range, setRange, currency, setCurrency }) {
  const RUBRO_NAMES = RUBROS.map(r => r.nm);
  const REGIONES = ['Todas','CABA','GBA','Córdoba','Nacional','Multi'];

  const SEED = [
    { id:'s1', nm:'Aceite de girasol 1.5L', rubro:'Alimentos',    precio:3290 },
    { id:'s2', nm:'Yerba mate 1kg',          rubro:'Alimentos',    precio:5400 },
    { id:'s3', nm:'Nafta súper · litro',     rubro:'Combustibles', precio:1230 },
  ];

  const [mySkus, setMySkus] = React.useState(() => {
    try { const s = localStorage.getItem('dn_mySkus'); return s ? JSON.parse(s) : SEED; }
    catch(e){ return SEED; }
  });
  React.useEffect(() => {
    try { localStorage.setItem('dn_mySkus', JSON.stringify(mySkus)); } catch(e){}
  }, [mySkus]);

  const [fNm, setFNm] = React.useState('');
  const [fRubro, setFRubro] = React.useState('Alimentos');
  const [fPre, setFPre] = React.useState('');
  const [region, setRegion] = React.useState('Todas');
  const [rubroFilter, setRubroFilter] = React.useState('Todos');
  const [selIds, setSelIds] = React.useState(null);   // null = todas las del pool
  const [selSku, setSelSku] = React.useState(null);

  const addSku = () => {
    const p = parseFloat(String(fPre).replace(',','.'));
    if (!fNm.trim() || !(p > 0)) return;
    setMySkus(a => [...a, { id:'s'+Date.now(), nm:fNm.trim(), rubro:fRubro, precio:Math.round(p) }]);
    setFNm(''); setFPre('');
  };
  const delSku = (id) => setMySkus(a => a.filter(s => s.id !== id));

  // Pool de competidores según filtros geo + rubro
  const pool = EMPRESAS.filter(e =>
    (region === 'Todas' || e.region.includes(region)) &&
    (rubroFilter === 'Todos' || e.rubro === rubroFilter)
  );
  const poolIds = pool.map(e => e.id);
  const selected = selIds === null ? poolIds : poolIds.filter(id => selIds.includes(id));
  const isSel = (id) => selIds === null ? true : selIds.includes(id);
  const toggle = (id) => setSelIds(prev => {
    const cur = prev === null ? [...poolIds] : [...prev];
    return cur.includes(id) ? cur.filter(x => x !== id) : [...cur, id];
  });

  // factor de nivel de precios por empresa (estable, determinístico)
  const hash01 = (s) => { let h=0; for (let i=0;i<s.length;i++) h=(h*31+s.charCodeAt(i))>>>0; return (h%1000)/1000; };
  const factor = (e) => Math.max(0.82, Math.min(1.18, 0.90 + hash01(e.id)*0.22 + (e.yoy-44)/350));

  // Comparación por SKU
  const rows = mySkus.map(s => {
    const comps = EMPRESAS
      .filter(e => selected.includes(e.id) && e.rubro === s.rubro)
      .map(e => ({ e, price: Math.round(s.precio * factor(e) / 10) * 10 }));
    const avg = comps.length ? comps.reduce((a,b)=>a+b.price,0)/comps.length : null;
    const delta = avg ? (s.precio/avg - 1)*100 : null;
    const rank = avg ? 1 + comps.filter(p => p.price < s.precio).length : null;
    return { ...s, comps, avg, delta, rank, n: comps.length };
  });
  const withData = rows.filter(r => r.avg != null);
  const basket = withData.length ? withData.reduce((a,r)=>a+r.delta,0)/withData.length : null;

  const selRow = rows.find(r => r.id === selSku) || rows.find(r => r.n > 0) || rows[0];
  // Series de evolución de precios (12m): tu empresa + competidores, terminando en el precio actual
  const refYoy = (selRow && selRow.n > 0) ? selRow.comps.reduce((a,p)=>a+p.e.yoy,0)/selRow.comps.length : 45;
  const scaleSerie = (end, yoy) => { const s = makeSerie(yoy), last = s[s.length-1]; return s.map(v => Math.round(end * v / last)); };
  const cmpSeries = (selRow && selRow.n > 0) ? [
    { name:'Tu empresa', color:'var(--amber)', bold:true, data: scaleSerie(selRow.precio, refYoy) },
    ...selRow.comps.map(p => ({ name:p.e.nm, color:p.e.color || 'var(--violet-500)', data: scaleSerie(p.price, p.e.yoy) }))
  ] : [];

  const deltaCls = (d) => d <= 0 ? 'delta delta-down' : 'delta delta-up';
  const deltaTxt = (d) => (d>0?'+':'') + d.toFixed(1) + '%';
  const posTxt = (r) => r.rank === 1 ? 'el más barato' : r.rank === r.n+1 ? 'el más caro' : `${r.rank}° de ${r.n+1}`;

  return (
    <div className="view">
      <TopBar
        title="Comparador de precios"
        subtitle="Cargá tus SKUs y compará tus precios contra el mercado."
        range={range} currency={currency} onRange={setRange} onCurrency={setCurrency}
      />

      <div className="cmp-grid">
        {/* ── Columna izquierda: cargar SKUs + competidores ── */}
        <div className="stack-col">
          <div className="card">
            <SectionHead right={<span className="mono ink-3">{mySkus.length} SKUs</span>}>TUS SKUS</SectionHead>
            <div className="sku-form">
              <input className="f-nm" placeholder="Nombre del producto / SKU" value={fNm}
                onChange={e=>setFNm(e.target.value)} onKeyDown={e=>e.key==='Enter'&&addSku()} />
              <div className="sku-form-r2">
                <select value={fRubro} onChange={e=>setFRubro(e.target.value)}>
                  {RUBRO_NAMES.map(r => <option key={r}>{r}</option>)}
                </select>
                <input placeholder="Precio $" inputMode="numeric" value={fPre}
                  onChange={e=>setFPre(e.target.value)} onKeyDown={e=>e.key==='Enter'&&addSku()} />
              </div>
              <button className="btn primary sku-add-btn" onClick={addSku}><Icon name="plus" size={16}/>Agregar SKU</button>
            </div>
            <div className="sku-rows">
              {mySkus.length === 0 && <div className="cmp-empty">Agregá tu primer SKU para empezar a comparar.</div>}
              {mySkus.map(s => (
                <div className="sku-r" key={s.id}>
                  <div>
                    <div className="sku-r-nm">{s.nm}</div>
                    <span className="tag">{s.rubro}</span>
                  </div>
                  <div className="sku-r-pr">{fmtMoney(s.precio)}</div>
                  <button className="sku-del" onClick={()=>delSku(s.id)} aria-label="Quitar"><Icon name="x" size={14}/></button>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <SectionHead>COMPARAR CONTRA</SectionHead>
            <div className="filters-lt" style={{marginBottom:'14px'}}>
              <Icon name="region" size={14}/>
              <Dropdown value={region} onChange={setRegion} options={REGIONES} />
              <Dropdown value={rubroFilter} onChange={setRubroFilter} options={['Todos', ...RUBRO_NAMES]} />
            </div>
            <div className="cmp-sub">
              <span>{selected.length} de {pool.length} empresas seleccionadas</span>
              <span className="row-r">
                <button className="link" onClick={()=>setSelIds([...poolIds])}>Todas</button>
                <span className="legend-sep">·</span>
                <button className="link" onClick={()=>setSelIds([])}>Ninguna</button>
              </span>
            </div>
            <div className="comp-chips">
              {pool.length === 0 && <div className="cmp-empty">No hay empresas con esos filtros.</div>}
              {pool.map(e => (
                <button key={e.id} className={`comp-chip ${isSel(e.id)?'on':''}`} onClick={()=>toggle(e.id)}>
                  <span className="dotc" style={{background:e.color}}></span>
                  {e.nm}
                  {isSel(e.id) && <span className="check"><Icon name="check" size={12}/></span>}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* ── Columna derecha: resultados ── */}
        <div className="stack-col">
          <div className="card">
            <SectionHead right={ basket!=null &&
              <span className={deltaCls(basket)}><span className="delta-arr">{basket<=0?'▼':'▲'}</span>{deltaTxt(basket)}</span>
            }>TU CANASTA VS MERCADO</SectionHead>
            {basket!=null
              ? <p className="cmp-lead">Tus precios están en promedio <b className={basket<=0?'pos-good':'pos-bad'}>{deltaTxt(basket)} {basket<=0?'por debajo':'por encima'}</b> del mercado, comparando contra <b>{selected.length}</b> empresas.</p>
              : <p className="cmp-lead ink-3">Seleccioná al menos una empresa del mismo rubro que tus SKUs para ver la comparación.</p>}
            <div className="table-wrap" style={{marginTop:'8px'}}>
              <table className="data-table">
                <thead><tr>
                  <th>SKU</th><th className="num">Tu precio</th><th className="num">Mercado</th>
                  <th className="num">Δ</th><th>Posición</th>
                </tr></thead>
                <tbody>
                  {rows.map(r => (
                    <tr key={r.id} onClick={()=>setSelSku(r.id)} className={selRow && selRow.id===r.id ? 'is-sel' : ''}>
                      <td><div className="sku-nm">{r.nm}</div><span className="tag">{r.rubro}</span></td>
                      <td className="num">{fmtMoney(r.precio)}</td>
                      <td className="num">{r.avg!=null ? fmtMoney(Math.round(r.avg)) : '—'}</td>
                      <td className="num">{r.delta!=null
                        ? <span className={deltaCls(r.delta)}><span className="delta-arr">{r.delta<=0?'▼':'▲'}</span>{deltaTxt(r.delta)}</span>
                        : <span className="ink-3">sin comparables</span>}</td>
                      <td className="cmp-pos">{r.n>0 ? posTxt(r) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {selRow && selRow.n > 0 && (
            <div className="card">
              <SectionHead right={<span className="mono ink-3">{selRow.n} competidores · {selRow.rubro}</span>}>
                {selRow.nm.toUpperCase()} · EVOLUCIÓN
              </SectionHead>
              <CompareChart series={cmpSeries} labels={MESES} height={260} valueFmt={fmtMoney} />
              <div className="cmp-legend">
                {cmpSeries.map((s,i)=>(
                  <span key={i} className={s.bold?'lg-you':''}><i style={{background:s.color, height:s.bold?'3px':'2px'}}></i>{s.name}</span>
                ))}
              </div>
              <div className="mono ink-3" style={{fontSize:'11px', marginTop:'8px'}}>Precios estimados · clic en otra fila para cambiar de SKU · se ajusta con los filtros</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
window.Comparador = Comparador;
