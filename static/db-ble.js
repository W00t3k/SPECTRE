// ══════════════════════════════════════════════════════
// OWNER LABELS  (stored in localStorage)
// Two maps:
//   BLE_LABELS        : full MAC  → owner string   e.g. "aa:bb:cc:dd:ee:ff" → "Brother"
//   BLE_PREFIX_LABELS : 8-char prefix → owner      e.g. "aa:bb:cc" → "Brother"
// ══════════════════════════════════════════════════════
let BLE_LABELS={};
let BLE_PREFIX_LABELS={};

function _saveLabels(){
  localStorage.setItem('ble_labels',        JSON.stringify(BLE_LABELS));
  localStorage.setItem('ble_prefix_labels', JSON.stringify(BLE_PREFIX_LABELS));
}
function _loadLabels(){
  try{ BLE_LABELS        = JSON.parse(localStorage.getItem('ble_labels')||'{}'); }catch(e){}
  try{ BLE_PREFIX_LABELS = JSON.parse(localStorage.getItem('ble_prefix_labels')||'{}'); }catch(e){}
}
_loadLabels();

// Returns {label, color} or null
const OWNER_COLORS=['#00ffc8','#ff0096','#ffe000','#3399ff','#ff8800','#cc44ff','#00ff88','#ff4444'];
const _ownerColorCache={};
function _ownerColor(label){
  if(!_ownerColorCache[label]){
    const keys=Object.values({...BLE_LABELS,...BLE_PREFIX_LABELS}).filter((v,i,a)=>a.indexOf(v)===i);
    _ownerColorCache[label]=OWNER_COLORS[keys.indexOf(label)%OWNER_COLORS.length]||'#aabbcc';
  }
  return _ownerColorCache[label];
}

function ownerLabel(addr){
  if(!addr)return null;
  const lo=addr.toLowerCase();
  if(BLE_LABELS[lo]) return {label:BLE_LABELS[lo],color:_ownerColor(BLE_LABELS[lo])};
  const pre=lo.slice(0,8); // "aa:bb:cc"
  if(BLE_PREFIX_LABELS[pre]) return {label:BLE_PREFIX_LABELS[pre],color:_ownerColor(BLE_PREFIX_LABELS[pre])};
  return null;
}

function ownerBadge(addr){
  const o=ownerLabel(addr);
  if(!o)return'';
  return `<span class="owner-badge" style="border-color:${o.color};color:${o.color};background:${o.color}18">👤 ${esc(o.label)}</span>`;
}

// ── Label editor modal ─────────────────────────────────
function openLabelModal(addr){
  const lo=(addr||'').toLowerCase();
  const pre=lo.slice(0,8);
  const cur=BLE_LABELS[lo]||BLE_PREFIX_LABELS[pre]||'';

  // Build all unique existing owner names for quick-pick
  const allOwners=[...new Set([...Object.values(BLE_LABELS),...Object.values(BLE_PREFIX_LABELS)])].filter(Boolean);
  const quickPicks=allOwners.map(n=>
    `<button class="owner-qbtn" onclick="document.getElementById('lbl-input').value='${esc(n)}'">${esc(n)}</button>`
  ).join('');

  $('lbl-addr').textContent=addr;
  $('lbl-prefix').textContent=pre;
  $('lbl-prefix2').textContent=pre;
  $('lbl-input').value=cur;
  $('lbl-quickpicks').innerHTML=quickPicks||'<span style="color:var(--dim);font-size:.58rem">No labels yet</span>';
  $('lbl-scope-mac').checked=true;
  $('lbl-modal').classList.add('open');
  setTimeout(()=>$('lbl-input').focus(),60);
}

function saveLabelModal(){
  const addr=$('lbl-addr').textContent.toLowerCase();
  const pre=addr.slice(0,8);
  const val=$('lbl-input').value.trim();
  const scope=$('lbl-scope-prefix').checked?'prefix':'mac';
  // invalidate color cache
  Object.keys(_ownerColorCache).forEach(k=>delete _ownerColorCache[k]);
  if(!val){
    delete BLE_LABELS[addr];
    delete BLE_PREFIX_LABELS[pre];
  } else if(scope==='prefix'){
    delete BLE_LABELS[addr];
    BLE_PREFIX_LABELS[pre]=val;
  } else {
    delete BLE_PREFIX_LABELS[pre];
    BLE_LABELS[addr]=val;
  }
  _saveLabels();
  closeLabelModal();
  renderBleDevices();
}

function closeLabelModal(){$('lbl-modal').classList.remove('open');}

// ══════════════════════════════════════════════════════
// BLE VIEW MODE
// ══════════════════════════════════════════════════════
let _bleView='grid';
let _bleSortKey='rssi';

function setBleView(v){
  _bleView=v;
  ['grid','table','compact','raw'].forEach(m=>{
    const el=$(m==='grid'?'ble-grid':`ble-${m}`);
    if(el) el.style.display=(m===v?(m==='table'?'table':'block'):'none');
    const btn=$('vbtn-'+m);
    if(btn) btn.classList.toggle('active',m===v);
  });
  renderBleDevices();
}

function bleTblSort(k){_bleSortKey=k;renderBleDevices();}

function _sortedBleDevs(){
  const devs=Object.values(bleDevs);
  if(_bleSortKey==='rssi')        devs.sort((a,b)=>b.rssi-a.rssi);
  else if(_bleSortKey==='name')   devs.sort((a,b)=>(a.name||'').localeCompare(b.name||''));
  else if(_bleSortKey==='type')   devs.sort((a,b)=>{
    const ta=(a.frames||[])[0]?.type||'';const tb2=(b.frames||[])[0]?.type||'';
    return ta.localeCompare(tb2);
  });
  else if(_bleSortKey==='seen')   devs.sort((a,b)=>b.last_seen-a.last_seen);
  return devs;
}

// ── TABLE VIEW ────────────────────────────────────────
function renderBleTable(sorted){
  const tbody=$('ble-tbody');tbody.innerHTML='';
  for(const dev of sorted){
    const isLost=!!dev.lost;
    const dn=bleDisplayName(dev);
    const enumerable=dn.name!==null;
    const displayName=dn.name||'UNNAMED';
    const model=!dn.derived?bleModelName(dev.frames):'';
    const det=enumerable?bleDetailText(dev.frames):'';
    const tr=document.createElement('tr');
    tr.className=(dev.addr===selectedBle?'sel':'')+(isLost?' lost-dev':'');
    tr.style.opacity=!enumerable?'0.28':isLost?'0.42':'';
    tr.style.cursor=enumerable?'pointer':'default';
    tr.style.filter=enumerable?'':'grayscale(70%)';
    tr.onclick=enumerable?()=>inspectBle(dev.addr):null;
    const nameStyle=dn.derived?'color:var(--dim);font-style:italic':(!enumerable?'color:rgba(255,255,255,0.2)':'');
    tr.innerHTML=`
      <td>
        <div class="bt-name" style="${nameStyle}">${esc(displayName)}${isLost?' 👻':''}</div>
        ${model?`<div class="bt-model">▸ ${esc(model)}</div>`:''}
        ${ownerBadge(dev.addr)}
        <div class="bt-addr" style="${!enumerable?'opacity:.3':''}">${esc(dev.addr)}</div>
      </td>
      <td><div class="ctags">${bleTags(dev.frames)}</div></td>
      <td style="color:${enumerable?rssiColor(dev.rssi):'rgba(255,255,255,0.2)'};font-weight:bold;white-space:nowrap">${dev.rssi} dBm</td>
      <td class="bt-detail">${det}</td>
      <td style="color:var(--dim);font-size:.55rem;white-space:nowrap">${elapsed(dev.last_seen)}</td>`;
    tbody.appendChild(tr);
  }
}

// ── COMPACT VIEW ──────────────────────────────────────
function renderBleCompact(sorted){
  const wrap=$('ble-compact');wrap.innerHTML='';
  for(const dev of sorted){
    const isLost=!!dev.lost;
    const dn=bleDisplayName(dev);
    const enumerable=dn.name!==null;
    const displayName=dn.name||'UNNAMED';
    const model=!dn.derived?bleModelName(dev.frames):'';
    const row=document.createElement('div');
    row.className='bc-row'+(dev.addr===selectedBle?' sel':'')+(isLost?' lost-dev':'');
    row.style.opacity=!enumerable?'0.28':isLost?'0.42':'';
    row.style.cursor=enumerable?'pointer':'default';
    row.style.filter=enumerable?'':'grayscale(70%)';
    row.onclick=enumerable?()=>inspectBle(dev.addr):null;
    const dotCol=enumerable?rssiColor(dev.rssi):'rgba(255,255,255,0.15)';
    const nameStyle=dn.derived?'color:var(--dim);font-style:italic':(!enumerable?'color:rgba(255,255,255,0.2)':'');
    row.innerHTML=`
      <div style="display:flex;align-items:center;justify-content:center">
        <div class="bc-dot" style="background:${dotCol};box-shadow:0 0 5px ${dotCol}"></div>
      </div>
      <div style="overflow:hidden">
        <div class="bc-name" style="${nameStyle}">${esc(displayName)}${model?' <span style="color:var(--cyan);font-weight:normal;font-size:.56rem">▸ '+esc(model)+'</span>':''} ${ownerBadge(dev.addr)}</div>
        <div style="font-size:.5rem;color:var(--dim);${!enumerable?'opacity:.3':''}">${esc(dev.addr)}</div>
      </div>
      <div class="bc-tags">${bleTags(dev.frames)}</div>
      <div class="bc-rssi" style="color:${dotCol}">${dev.rssi}</div>
      <div class="bc-ts">${elapsed(dev.last_seen)}</div>`;
    wrap.appendChild(row);
  }
}

// ── RAW HEX VIEW ──────────────────────────────────────
function renderBleRaw(sorted){
  const wrap=$('ble-raw');wrap.innerHTML='';
  for(const dev of sorted){
    const isLost=!!dev.lost;
    const row=document.createElement('div');
    row.className='braw-row'+(dev.addr===selectedBle?' sel':'');
    row.onclick=()=>inspectBle(dev.addr);
    const hex=(dev.raw_hex||'');
    // colour first 2 bytes (type/len header) differently
    const bytes=hex.match(/.{1,2}/g)||[];
    const coloured=bytes.map((b,i)=>{
      const cls=i<2?'hi':i<6?'mid':'';
      return `<span class="braw-byte ${cls}">${b}</span>`;
    }).join('');
    const frameTypes=(dev.frames||[]).map(f=>esc(f.type)).join(' · ');
    row.innerHTML=`
      <div class="braw-addr">${esc(dev.addr)} <span style="color:var(--dim);font-size:.5rem">${esc(dev.name)}</span> ${ownerBadge(dev.addr)}</div>
      <div class="braw-hex">${coloured||'<span style="color:var(--dim)">no data</span>'}</div>
      <div class="braw-meta">${frameTypes} · ${dev.rssi} dBm · ${elapsed(dev.last_seen)}${isLost?' · 👻 LOST':''}</div>`;
    wrap.appendChild(row);
  }
}

// ── PLAIN-TEXT DETAIL (used by table view) ────────────
function bleDetailText(frames){
  const parts=[];
  for(const f of (frames||[])){
    if(f.type_id===0x10){
      const s=f.phone_state||f.activity||'';
      parts.push([stateIcon(s),s,f.ios_version,'WiFi:'+(f.wifi_on?'✓':'✗')].filter(Boolean).join(' '));
    } else if(f.type_id===0x07){
      const L=f.left_bat!=null?(f.left_bat*10)+'%':'?';
      const R=f.right_bat!=null?(f.right_bat*10)+'%':'?';
      const C=f.case_bat!=null?(f.case_bat*10)+'%':'?';
      parts.push(`L:${L} R:${R} 🗃:${C}`+(f.status?` ${f.status}`:''));
    } else if(f.type_id===0x0f){
      parts.push(f.action||'Nearby Action');
    } else if(f.type_id===0x05){
      parts.push('AirDrop'+(f.phone?` ph:${f.phone}`:''));
    } else if(f.type_id===0x0d||f.type_id===0x0e){
      parts.push((f.type_id===0x0d?'Hotspot':'Tethering')+(f.network_type?` ${f.network_type}`:'')+(f.battery!=null?` 🔋${f.battery}%`:''));
    } else if(f.type_id===0x06){
      parts.push(`HomeKit: ${f.category||'?'}`);
    } else if(f.type_id===0x08){
      parts.push(`Siri${f.device_type?` ${f.device_type}`:''}${f.battery!=null?` 🔋${f.battery}%`:''}`);
    } else if(f.type_id===0x0b){
      parts.push(f.wrist_state||'Magic Switch');
    } else if(f.type_id===0x0c){
      parts.push('Handoff');
    } else if(f.type_id===0x12){
      parts.push('Find My'+(f.status?` ${f.status}`:''));
    }
  }
  return parts.map(p=>`<span>${esc(p)}</span>`).join('<br>');
}

// ── DISPATCH ──────────────────────────────────────────
function renderBleDevices(){
  const all=_sortedBleDevs();
  const sorted=typeof _bleFilteredDevs==='function'?_bleFilteredDevs(all):all;
  if(_bleView==='grid')         renderBleGridInner(sorted);
  else if(_bleView==='table')   renderBleTable(sorted);
  else if(_bleView==='compact') renderBleCompact(sorted);
  else if(_bleView==='raw')     renderBleRaw(sorted);
  // always update stats counters using unfiltered list
  _updateBleStats(all);
}

// ══════════════════════════════════════════════════════
// BLE GRID
// ══════════════════════════════════════════════════════
const TYPE_MAP={
  0x10:['tc','Nearby Info','t-ni'],  0x0f:['ty','Nearby Action','t-na'],
  0x07:['tb','AirPods','t-ap'],      0x05:['tm','AirDrop','t-ad'],
  0x0c:['tg','Handoff','t-hf'],      0x0d:['to','Hotspot','t-hs'],
  0x0e:['to','Tethering','t-hs'],    0x12:['tr2','Find My','t-fm'],
  0x09:['tc','AirPlay','t-ni'],      0x06:['td2','HomeKit','t-xx'],
  0x0b:['td2','Magic Switch','t-xx'],0x08:['tc','Siri','t-ni'],
  0x03:['td2','AirPrint','t-xx'],
};

const STATE_ICONS={
  'Screen Active':'🔓','Lock screen':'🔒','Screen Off':'😴','Off':'😴','Idle':'💤',
  'Driving':'🚗','Incoming call':'📞','Outgoing call':'📞','Music':'🎵',
  'Video':'🎬','Home screen':'📱','Watch Unlocked':'⌚','Recent Interaction':'👆',
  'Audio (Screen Locked)':'🎶','Phone/FaceTime Call':'📹','Reporting Disabled':'🚫',
  'Wrist detection disabled':'⌚','On wrist':'⌚','Not on wrist':'📦','Disabled':'🚫',
};

const COLOR_SWATCHES={
  'White':'#f0f0f0','Black':'#1a1a1a','Red':'#ff3333','Blue':'#3366ff',
  'Pink':'#ff66aa','Gray':'#888888','Silver':'#c0c0c0','Gold':'#ffd700',
  'Rose Gold':'#b76e79','Space Gray':'#535353','Dark Blue':'#003399',
  'Light Blue':'#66aaff','Yellow':'#ffee00',
};

function bleCardClass(frames){
  const pri=[0x07,0x10,0x0f,0x05,0x0c,0x0d,0x12,0x08];
  for(const p of pri)if((frames||[]).some(f=>f.type_id===p))return TYPE_MAP[p]?.[2]||'t-xx';
  return 't-xx';
}
function bleTags(frames){
  return [...new Map((frames||[]).map(f=>[f.type_id,f])).values()]
    .map(f=>{const[cls,lbl]=TYPE_MAP[f.type_id]||['td2',f.type];return`<span class="ctag ${cls}">${esc(lbl)}</span>`;}).join('');
}

function stateIcon(s){return STATE_ICONS[s]||'';}
function colorSwatch(color){
  if(!color)return'';
  const c=COLOR_SWATCHES[color];
  if(!c)return'';
  return`<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${c};border:1px solid rgba(255,255,255,.3);margin-right:4px;vertical-align:middle;" title="${esc(color)}"></span>`;
}

function bleModelName(frames){
  for(const f of (frames||[])){
    if(f.type_id===0x07&&f.model&&!f.model.startsWith('0x'))return f.model;
    if(f.type_id===0x08&&f.device_type)return f.device_type;
    if(f.type_id===0x0f&&f.device_class)return f.device_class;
    if(f.type_id===0x10&&f.phone_state)return'';
  }
  return '';
}

// Best-effort display name from ALL frame data — never returns empty
function bleDisplayName(dev){
  const n=dev.name||'';
  // Already has a real name (not just generic fallback from server)
  const GENERIC=['Apple Device','Unknown'];
  if(n && !GENERIC.includes(n)) return {name:n,derived:false};
  // Try to derive from frames
  for(const f of (dev.frames||[])){
    if(f.type_id===0x07){
      const m=f.model&&!f.model.startsWith('0x')?f.model:'AirPods';
      return {name:m,derived:true};
    }
    if(f.type_id===0x08&&f.device_type)
      return {name:f.device_type,derived:true};
    if(f.type_id===0x0f){
      const a=f.action?`Action: ${f.action}`:'Nearby Action';
      const dc=f.device_class?` (${f.device_class})`:''
      return {name:a+dc,derived:true};
    }
    if(f.type_id===0x10){
      const ios=f.ios_version?` ${f.ios_version}`:'';
      const st=f.phone_state||f.activity||'';
      return {name:`iPhone/iPad${ios}${st?' · '+st:''}`,derived:true};
    }
    if(f.type_id===0x05) return {name:'AirDrop Device',derived:true};
    if(f.type_id===0x0c) return {name:'Handoff (Apple)',derived:true};
    if(f.type_id===0x0d){
      const nt=f.network_type||'Hotspot';
      return {name:`Hotspot · ${nt}`,derived:true};
    }
    if(f.type_id===0x0e) return {name:'iPhone Tethering',derived:true};
    if(f.type_id===0x06){
      const cat=f.category||'HomeKit';
      return {name:`HomeKit · ${cat}`,derived:true};
    }
    if(f.type_id===0x0b) return {name:'Magic Switch',derived:true};
    if(f.type_id===0x12){
      const st=f.status||'';
      return {name:`Find My${st?' · '+st:''}`,derived:true};
    }
    if(f.type_id===0x09) return {name:'AirPlay Target',derived:true};
    if(f.type_id===0x0a) return {name:'AirPlay Source',derived:true};
  }
  // Nothing useful — truly unknown
  return {name:null,derived:false};
}

// A device is enumerable if we can derive any name for it
function _isEnumerable(dev){
  return bleDisplayName(dev).name !== null;
}

function chip(label,val,col){
  if(!val&&val!==0)return'';
  return`<span style="display:inline-block;margin:1px 2px 1px 0;padding:1px 5px;border-radius:10px;font-size:.5rem;letter-spacing:.04em;border:1px solid ${col||'var(--dim)'};color:${col||'var(--text)'};background:${col||'var(--dim)'}18">${esc(label)}${val!==true?': '+esc(String(val)):''}</span>`;
}

function bleDetail(frames,dev){
  const lines=[];
  for(const f of (frames||[])){
    if(f.type_id===0x10){
      const st=f.phone_state||f.activity||'';
      const si=stateIcon(st);
      const ios=f.ios_version||'';
      const wifiCol=f.wifi_on?'var(--green)':'var(--dim)';
      let row='';
      if(st) row+=`<span style="font-weight:bold;color:var(--white)">${si} ${esc(st)}</span> `;
      if(ios) row+=chip('iOS',ios,ios.includes('26')||ios.includes('25')||ios.includes('24')?'var(--cyan)':'var(--blue)');
      row+=`<span style="font-size:.5rem;color:${wifiCol};margin-left:3px">WiFi${f.wifi_on?'✓':'✗'}</span>`;
      if(f.airdrop_status!==undefined) row+=chip('AirDrop',f.airdrop_status?'on':'off','var(--mag)');
      lines.push(row);
    } else if(f.type_id===0x0f){
      const act=f.action||'';
      lines.push(`<span style="color:var(--yellow)">⚡</span> <b>${esc(act||'Nearby Action')}</b>`+
        (f.device_class?` ${chip('device',f.device_class,'var(--blue)')}`:'')+ 
        (f.os_version?` ${chip('os',f.os_version,'var(--cyan)')}`:'')+ 
        (f.wifi_on!==undefined?`<span style="font-size:.5rem;color:${f.wifi_on?'var(--green)':'var(--dim)'};margin-left:3px">WiFi${f.wifi_on?'✓':'✗'}</span>`:''));
    } else if(f.type_id===0x07){
      const cs=colorSwatch(f.color);
      const st=f.status||'';
      const L=f.left_bat!=null?(f.left_bat*10)+'%':'';
      const R=f.right_bat!=null?(f.right_bat*10)+'%':'';
      const C=f.case_bat!=null?(f.case_bat*10)+'%':'';
      lines.push(`${cs}<b>${esc(f.model||'AirPods')}</b>`+
        (st?` <span style="color:var(--dim);font-size:.55rem">${esc(st)}</span>`:'')+
        (L||R||C?`<br><span style="font-size:.55rem;color:var(--dim)">L:${L||'?'} R:${R||'?'} 🗃:${C||'?'}</span>`:''));
    } else if(f.type_id===0x05){
      const ph=f.phone||'';const ai=f.apple_id||'';const em=f.email||'';
      lines.push(`<span style="color:var(--mag)">📡 AirDrop</span>`+
        (ph?`<br><span style="font-size:.54rem;color:var(--dim)">ph: <code style="color:var(--yellow)">${esc(ph)}</code></span>`:'')+
        (ai?`<br><span style="font-size:.54rem;color:var(--dim)">id: <code style="color:var(--text)">${esc(ai)}</code></span>`:'')+
        (em?`<br><span style="font-size:.54rem;color:var(--dim)">em: <code style="color:var(--text)">${esc(em)}</code></span>`:''));
    } else if(f.type_id===0x0c){
      lines.push(`<span style="color:var(--green)">🔄 Handoff</span>`+
        (f.sequence?` <span style="font-size:.54rem;color:var(--dim)">seq:${esc(String(f.sequence))}</span>`:''));
    } else if(f.type_id===0x0d||f.type_id===0x0e){
      const lbl=f.type_id===0x0d?'Hotspot':'Tethering';
      lines.push(`<span style="color:var(--orange)">📶 ${lbl}</span>`+
        (f.network_type?` ${chip('network',f.network_type,'var(--orange)')}`:'')+
        (f.battery!=null?` ${chip('🔋',f.battery+'%','var(--green)')}`:'')+
        (f.display_on!==undefined?` <span style="font-size:.5rem;color:var(--dim)">scr:${f.display_on?'on':'off'}</span>`:''));
    } else if(f.type_id===0x06){
      lines.push(`<span style="color:var(--dim)">🏠 HomeKit</span> <b>${esc(f.category||'?')}</b>`);
    } else if(f.type_id===0x0b){
      const ws=f.wrist_state||'';
      lines.push(`<span style="color:var(--dim)">⌚ ${stateIcon(ws)||''} ${esc(ws||'Magic Switch')}</span>`);
    } else if(f.type_id===0x08){
      lines.push(`<span style="color:var(--cyan)">🎤 Siri</span>`+
        (f.device_type?` ${chip('device',f.device_type,'var(--cyan)')}`:'')+ 
        (f.os_version?` ${chip('os',f.os_version,'var(--blue)')}`:'')+ 
        (f.battery!=null?` ${chip('🔋',f.battery+'%','var(--green)')}`:'')+ 
        (f.active!==undefined?` <span style="font-size:.5rem;color:${f.active?'var(--cyan)':'var(--dim)'}">siri:${f.active?'active':'off'}</span>`:'')); 
    } else if(f.type_id===0x12){
      lines.push(`<span style="color:var(--red)">📍 Find My</span>`+
        (f.status?` <span style="font-size:.54rem;color:var(--dim)">${esc(f.status)}</span>`:''));
    } else if(f.note){
      lines.push(`<span style="color:var(--dim);font-size:.55rem">${esc(f.note)}</span>`);
    }
  }
  return lines.join('<br>');
}

function bleBatBars(frames){
  const ap=(frames||[]).find(f=>f.type_id===0x07);if(!ap)return'';
  const L=ap.left_bat!=null?ap.left_bat*10:null;
  const R=ap.right_bat!=null?ap.right_bat*10:null;
  const C=ap.case_bat!=null?ap.case_bat*10:null;
  const bc=v=>v>60?'var(--green)':v>30?'var(--yellow)':'var(--red)';
  const chg=v=>v?'⚡':'';
  const bar=(lbl,charging,pct)=>pct!=null
    ?`<span class="bat-label">${lbl}${chg(charging)}</span><div class="bat-bar"><div class="bat-fill" style="width:${pct}%;background:${bc(pct)}"></div></div><span class="bat-pct">${pct}%</span>`
    :'';
  const rows=[bar('L',ap.left_charging,L),bar('R',ap.right_charging,R),bar('🗃',ap.case_charging,C)].filter(Boolean);
  if(!rows.length)return'';
  return `<div class="bat-row">${rows.join('')}</div>`;
}

function _pairedBatRow(pb){
  if(!pb||!Object.keys(pb).length)return'';
  const bc=v=>v>60?'var(--green)':v>30?'var(--yellow)':'var(--red)';
  const bar=(lbl,pct)=>pct!=null
    ?`<span class="bat-label">${lbl}</span><div class="bat-bar"><div class="bat-fill" style="width:${pct}%;background:${bc(pct)}"></div></div><span class="bat-pct">${pct}%</span>`
    :'';
  const rows=[
    pb.left!=null?bar('L',pb.left):'',
    pb.right!=null?bar('R',pb.right):'',
    pb.case!=null?bar('🗃',pb.case):'',
    pb.main!=null?bar('🔋',pb.main):'',
  ].filter(Boolean);
  if(!rows.length)return'';
  return`<div class="bat-row" style="opacity:.8">${rows.join('')}</div>`;
}

function renderBleGridInner(sorted){
  const grid=$('ble-grid');
  const existing={};for(const el of grid.children)existing[el.dataset.addr]=el;
  const seen=new Set();
  for(const dev of sorted){
    seen.add(dev.addr);
    const tc=bleCardClass(dev.frames);
    const dn=bleDisplayName(dev);
    const enumerable=dn.name!==null;
    let card=existing[dev.addr];
    if(!card){card=document.createElement('div');card.dataset.addr=dev.addr;
      card.classList.add('card-new');grid.appendChild(card);}
    // Only wire onclick if we have enough info to show a detail panel
    card.onclick=enumerable?()=>inspectBle(dev.addr):null;
    const isLost=!!dev.lost;
    const opacity=!enumerable?'0.28':isLost?'0.42':'1';
    card.className=`dev-card ${tc}${dev.addr===selectedBle?' sel':''}${isLost?' lost-dev':''}${!enumerable?' dev-ghost':''}`;
    card.style.opacity=opacity;
    card.style.cursor=enumerable?'pointer':'default';
    card.style.filter=enumerable?'':'grayscale(80%)';
    const lostBadge=isLost?'<span class="ctag tr2" style="animation:alertp .8s infinite">LOST</span>':'';
    const displayName=dn.name||'UNNAMED';
    const nameStyle=dn.derived?'color:var(--dim);font-style:italic':(!enumerable?'color:rgba(255,255,255,0.2)':'');
    const modelName=!dn.derived?bleModelName(dev.frames):'';
    const detail=enumerable?bleDetail(dev.frames,dev):'';
    const ob=ownerBadge(dev.addr);
    card.innerHTML=`
      <div class="card-header">
        <div class="card-title-wrap">
          <div class="cn" style="${nameStyle}">${esc(displayName)}${isLost?' 👻':''}${!enumerable?' <span style="font-size:.5rem;color:rgba(255,255,255,0.18);font-style:normal">UNNAMED</span>':''}</div>
          ${modelName?`<div class="cn-model">▸ ${esc(modelName)}</div>`:''}
          ${ob?`<div style="margin-top:2px">${ob}</div>`:''}
        </div>
        <div class="card-rssi-wrap">
          <div class="card-rssi" style="color:${enumerable?rssiColor(dev.rssi):'rgba(255,255,255,0.2)'}">${dev.rssi}<span style="font-size:.5rem">dBm</span></div>
          ${enumerable?`<button class="lbl-btn" onclick="event.stopPropagation();openLabelModal('${dev.addr}')">👤</button>`:''}
        </div>
      </div>
      <div class="ca" style="${!enumerable?'color:rgba(255,255,255,0.15)':''}">${esc(dev.addr)}${dev.vendor?` <span style="color:var(--dim);font-size:.48rem;margin-left:4px">${esc(dev.vendor.split(',')[0])}</span>`:''}</div>
      <div class="ctags">${bleTags(dev.frames)}${lostBadge}${dev.vendor&&!dev.vendor.includes('Apple')?`<span class="ctag" style="border-color:var(--dim);color:var(--dim)">${esc(dev.vendor.split(',')[0].slice(0,16))}</span>`:''}</div>
      ${enumerable?bleBatBars(dev.frames):''}
      ${_pairedBatRow(dev.paired_battery)}
      ${detail?`<div class="cd">${detail}</div>`:''}
      <div class="cts">Frames:${dev.frame_count||0} · ${elapsed(dev.last_seen)}</div>`;
  }
  for(const[addr,el]of Object.entries(existing))if(!seen.has(addr))grid.removeChild(el);
}

function _updateBleStats(sorted){
  let totalFrames=0;for(const d of sorted)totalFrames+=d.frame_count||0;
  $('bs-total').textContent=sorted.length;
  const ht=id=>sorted.filter(d=>(d.frames||[]).some(f=>f.type_id===id)).length;
  $('bs-ni').textContent=ht(0x10);$('bs-na').textContent=ht(0x0f);$('bs-ap').textContent=ht(0x07);
  $('bs-ad').textContent=ht(0x05);$('bs-hd').textContent=ht(0x0c);
  $('bs-hs').textContent=sorted.filter(d=>(d.frames||[]).some(f=>f.type_id===0x0d||f.type_id===0x0e)).length;
  $('bs-fm').textContent=ht(0x12);$('bs-fr').textContent=totalFrames;
}

function renderBleGrid(){renderBleDevices();}

// ══════════════════════════════════════════════════════
// BLE INSPECT
// ══════════════════════════════════════════════════════
function inspectBle(addr){
  const dev=bleDevs[addr];if(!dev)return;
  selectedBle=addr;renderBleGrid();
  let html=`<div class="dr"><span class="dk">NAME</span><span class="dv">${esc(dev.name)}</span></div>
    <div class="dr"><span class="dk">ADDRESS</span><span class="dv">${esc(dev.addr)}</span></div>
    <div class="dr"><span class="dk">RSSI</span><span class="dv" style="color:${rssiColor(dev.rssi)}">${dev.rssi} dBm</span></div>
    <div class="dr"><span class="dk">FRAMES SEEN</span><span class="dv">${dev.frame_count||0}</span></div>
    <div class="dr"><span class="dk">RAW HEX</span><span class="dv dv-hex">${esc(dev.raw_hex||'')}</span></div>`;
  for(const f of (dev.frames||[])){
    const[cls]=(TYPE_MAP[f.type_id]||['tc']);
    html+=`<div class="dr" style="margin-top:5px;border-top:1px solid #1a3a6a">
      <span class="dk ctag ${cls}" style="padding:0">${esc(f.type)}</span>
      <span class="dv dv-hex">0x${f.type_id.toString(16).padStart(2,'0')}</span></div>`;
    for(const[k,v]of Object.entries(f)){
      if(['type_id','type','raw'].includes(k))continue;
      const isHash=f.type_id===0x05&&['apple_id','phone','email','email2'].includes(k);
      const copyBtn=isHash?`<button onclick="navigator.clipboard.writeText('${v}')" style="margin-left:6px;background:none;border:1px solid var(--dim);color:var(--dim);font-size:.5rem;padding:0 3px;border-radius:2px;cursor:pointer">COPY</button>`:'';
      html+=`<div class="dr"><span class="dk">&nbsp;&nbsp;${esc(k.toUpperCase())}</span><span class="dv">${esc(String(v??''))}${copyBtn}</span></div>`;
    }
    html+=`<div class="dr"><span class="dk">&nbsp;&nbsp;RAW PAYLOAD</span><span class="dv dv-hex">${esc(f.raw||'')}</span></div>`;
  }
  if((dev.frames||[]).some(f=>f.type_id===0x05)){
    html+=`<div style="margin-top:8px;padding:6px 8px;background:#100510;border:1px solid var(--mag);border-radius:4px;font-size:.6rem;color:var(--mag)">
      ⚠ SHA256 truncated hashes. Use <b>hash2phone</b> pre-computed tables to reverse phone/email.</div>`;
  }
  $('ble-detail-wrap').innerHTML=html;
}
