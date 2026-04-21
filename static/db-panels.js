// ══════════════════════════════════════════════════════
// DRAGGABLE / RESIZABLE PANELS
// ══════════════════════════════════════════════════════
const PANEL_LAYOUTS={}; // panelId -> {x,y,w,h}
function initPanel(panel){
  const id=panel.id;
  if(!panel.querySelector('.resize-grip')){
    const grip=document.createElement('div');grip.className='resize-grip';panel.appendChild(grip);
    grip.addEventListener('mousedown',e=>startResize(e,panel));
  }
  const pt=panel.querySelector('.ptitle');
  if(pt&&!pt.querySelector('.panel-collapse-btn')){
    const sp=document.createElement('span');sp.className='ptitle-spacer';pt.appendChild(sp);
    const btn=document.createElement('button');btn.className='panel-collapse-btn';btn.textContent='−';
    btn.title='Collapse/Expand';
    btn.onclick=e=>{e.stopPropagation();const c=panel.classList.toggle('collapsed');btn.textContent=c?'+':'−';};
    pt.appendChild(btn);
    pt.addEventListener('mousedown',e=>{if(e.target===btn)return;startDrag(e,panel);});
  }
  const saved=PANEL_LAYOUTS[id];
  if(saved){panel.style.left=saved.x+'px';panel.style.top=saved.y+'px';
    panel.style.width=saved.w+'px';panel.style.height=saved.h+'px';}
}
function saveLayout(panel){
  PANEL_LAYOUTS[panel.id]={x:parseInt(panel.style.left),y:parseInt(panel.style.top),
    w:parseInt(panel.style.width),h:parseInt(panel.style.height)};
}
function startDrag(e,panel){
  e.preventDefault();
  panel.classList.add('dragging');
  bringToFront(panel);
  const ox=e.clientX-panel.offsetLeft,oy=e.clientY-panel.offsetTop;
  function onMove(e){
    const body=$('body');const bw=body?body.offsetWidth:window.innerWidth;
    const bh=window.innerHeight-84;
    panel.style.left=Math.max(0,Math.min(bw-80,e.clientX-ox))+'px';
    panel.style.top=Math.max(0,Math.min(bh-28,e.clientY-oy))+'px';
  }
  function onUp(){panel.classList.remove('dragging');saveLayout(panel);document.removeEventListener('mousemove',onMove);document.removeEventListener('mouseup',onUp);}
  document.addEventListener('mousemove',onMove);
  document.addEventListener('mouseup',onUp);
}
function startResize(e,panel){
  e.preventDefault();e.stopPropagation();
  const startX=e.clientX,startY=e.clientY;
  const startW=panel.offsetWidth,startH=panel.offsetHeight;
  function onMove(e){
    panel.style.width=Math.max(180,startW+e.clientX-startX)+'px';
    panel.style.height=Math.max(80,startH+e.clientY-startY)+'px';
    resizeAll();
  }
  function onUp(){saveLayout(panel);document.removeEventListener('mousemove',onMove);document.removeEventListener('mouseup',onUp);}
  document.addEventListener('mousemove',onMove);
  document.addEventListener('mouseup',onUp);
}
let _zTop=10;
function bringToFront(panel){panel.style.zIndex=++_zTop;}

// Ratio-based layouts: {lx, ly, lw, lh} as fractions 0..1 of (W, H)
// W = viewport width, H = viewport height minus topbar+tabs (84px)
const G=3; // gap px between panels
const DEFAULT_LAYOUTS={
  'tab-wifi':{
    'radar-panel':      {lx:0,     ly:0,    lw:.333, lh:.68},
    'wifi-table-panel': {lx:.333,  ly:0,    lw:.5,   lh:.68},
    'wifi-stats-panel': {lx:.833,  ly:0,    lw:.167, lh:.68},
    'sig-panel':        {lx:0,     ly:.68,  lw:.333, lh:.32},
    'ch-panel':         {lx:.333,  ly:.68,  lw:.5,   lh:.32},
    'wifi-tl-panel':    {lx:.833,  ly:.68,  lw:.167, lh:.32},
  },
  'tab-ble':{
    'ble-devices-panel':{lx:0,     ly:0,    lw:.69,  lh:.63},
    'ble-log-panel':    {lx:.69,   ly:0,    lw:.31,  lh:.63},
    'ble-detail-panel': {lx:0,     ly:.63,  lw:.69,  lh:.37},
    'ble-stats-panel':  {lx:.69,   ly:.63,  lw:.31,  lh:.37},
  },
  'tab-timeline':{
    'tl-wifi-panel':    {lx:0,     ly:0,    lw:.5,   lh:.5},
    'tl-ble-panel':     {lx:.5,    ly:0,    lw:.5,   lh:.5},
    'tl-act-panel':     {lx:0,     ly:.5,   lw:.5,   lh:.5},
    'tl-events-panel':  {lx:.5,    ly:.5,   lw:.5,   lh:.5},
  },
  'tab-alerts':{
    'alert-list-panel': {lx:0,     ly:0,    lw:.5,   lh:1},
    'export-panel':     {lx:.5,    ly:0,    lw:.5,   lh:1},
  },
  'tab-system':{
    'sys-meta-panel':   {lx:0,     ly:0,    lw:.28,  lh:1},
    'sys-ifaces-panel': {lx:.28,   ly:0,    lw:.38,  lh:.5},
    'sys-usb-panel':    {lx:.28,   ly:.5,   lw:.38,  lh:.5},
  },
};
function _viewportWH(){
  const W=window.innerWidth;
  const H=window.innerHeight-84; // subtract topbar(50)+tabs(34)
  return [W,H];
}
function applyDefaultLayout(tabId,force){
  const defs=DEFAULT_LAYOUTS[tabId]||{};
  const [W,H]=_viewportWH();
  for(const[pid,r]of Object.entries(defs)){
    const p=$(pid);if(!p)continue;
    if(force||!PANEL_LAYOUTS[pid]){
      const x=Math.round(r.lx*W)+G, y=Math.round(r.ly*H)+G;
      const w=Math.round(r.lw*W)-G*2, h=Math.round(r.lh*H)-G*2;
      p.style.left=x+'px';p.style.top=y+'px';
      p.style.width=w+'px';p.style.height=h+'px';
      if(force)PANEL_LAYOUTS[pid]={x,y,w,h};
    }
  }
}
function initAllPanels(){
  document.querySelectorAll('.panel').forEach(p=>initPanel(p));
  for(const tabId of Object.keys(DEFAULT_LAYOUTS))applyDefaultLayout(tabId);
}

// ══════════════════════════════════════════════════════
// THEME SWITCHER
// ══════════════════════════════════════════════════════
const THEMES=['','theme-matrix','theme-amber','theme-ice','theme-light','theme-neon','theme-stealth'];
let _curTheme='';
function toggleThemePicker(){
  $('theme-picker').classList.toggle('open');
}
function applyTheme(t){
  document.body.classList.remove(...THEMES.filter(x=>x));
  if(t)document.body.classList.add(t);
  _curTheme=t;
  document.querySelectorAll('.tpopt').forEach(el=>el.classList.toggle('sel',el.dataset.theme===t));
  $('theme-picker').classList.remove('open');
  resizeAll();
}
document.querySelectorAll('.tpopt').forEach(el=>el.addEventListener('click',()=>applyTheme(el.dataset.theme)));

function setFiltPill(id){
  document.querySelectorAll('.filt-pill').forEach(b=>b.classList.remove('active'));
  const el=$('fp-'+id);if(el)el.classList.add('active');
}

function resetLayout(){
  for(const k of Object.keys(PANEL_LAYOUTS))delete PANEL_LAYOUTS[k];
  for(const tabId of Object.keys(DEFAULT_LAYOUTS))applyDefaultLayout(tabId,true);
  resizeAll();
}
