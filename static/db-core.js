// ══════════════════════════════════════════════════════
// UTILS
// ══════════════════════════════════════════════════════
const $=id=>document.getElementById(id);
function esc(s){const d=document.createElement('div');d.textContent=String(s??'');return d.innerHTML;}
function elapsed(ts){const s=Math.round(Date.now()/1e3-ts);if(s<5)return'now';if(s<60)return s+'s';return Math.floor(s/60)+'m';}
function norm(r){return Math.max(0,Math.min(1,(r+90)/60));}
function rssiColor(r){return r>=-55?'#00ff88':r>=-70?'#ffe000':'#ff4444';}
function band(ch){return parseInt(ch)>14?'5GHz':'2.4GHz';}
function dl(url){const a=document.createElement('a');a.href=url;a.download='';document.body.appendChild(a);a.click();a.remove();}

const OUI={'00:50:f2':'Microsoft','ac:de:48':'Apple','f4:f5:d8':'Apple','a4:c3:f0':'Apple',
  '00:1b:63':'Apple','00:1f:33':'Netgear','20:4e:7f':'Netgear','c4:04:15':'Linksys',
  '00:23:69':'Cisco','c8:d7:19':'Cisco','00:26:5a':'TP-Link','50:c7:bf':'TP-Link',
  'ec:08:6b':'TP-Link','00:1d:7e':'Asus','f8:32:e4':'Asus','00:1a:70':'Ubiquiti',
  'fc:ec:da':'Ubiquiti','04:18:d6':'Ubiquiti','b8:27:eb':'Raspberry Pi','dc:a6:32':'Raspberry Pi',
  'de:ad:be':'Demo','aa:bb:cc':'Demo','ca:fe:ba':'Demo'};
function vendor(b){const lo=b.toLowerCase();return OUI[lo.slice(0,11)]||OUI[lo.slice(0,8)]||'?';}

const TCOLS=['#00ffc8','#ff0096','#00ff88','#ffe000','#3399ff','#ff8800','#cc44ff','#ff4444'];

// ══════════════════════════════════════════════════════
// STATE
// ══════════════════════════════════════════════════════
let wifiNets={}, bleDevs={}, allEvents=[], allAlerts=[];
let wifiHistory={}, bleHistory={};
let wSortKey='rssi', selectedWifi=null, selectedBle=null;
let radarAngle=0, ripples=[];
let actMap={};
let _batteryData={mac:null,bt:[]};   // latest battery info from server

// ══════════════════════════════════════════════════════
// CLOCK
// ══════════════════════════════════════════════════════
setInterval(()=>$('clock').textContent=new Date().toTimeString().slice(0,8),1000);

// ══════════════════════════════════════════════════════
// SOCKET
// ══════════════════════════════════════════════════════
const socket=io();
socket.on('connect',()=>{$('status-b').textContent='● LIVE';$('status-b').className='badge bg';
  // request fresh system info on reconnect
  setTimeout(loadSystemInfo,300);
});
socket.on('disconnect',()=>{$('status-b').textContent='○ OFFLINE';$('status-b').className='badge bd';});
socket.on('alert',al=>{
  // Only show toast for high-signal alerts — suppress generic re-appearance noise
  const HIGH_KINDS=['🎯 AIRDROP DETECTED','🔴 HIGH-VALUE TARGET','📡 OPEN NETWORK'];
  const isHigh=HIGH_KINDS.some(k=>al.kind&&al.kind.includes(k.replace(/[^ \w]/g,'').trim().split(' ')[0]))
    || (al.kind&&al.kind.includes('HIGH-VALUE'))
    || (al.detail&&al.detail.includes('HIGH'));
  if(isHigh) showToast(al);
});
socket.on('interval_ack',d=>{const el=$('interval-val');if(el)el.textContent=d.interval+'s';});
socket.on('mute_state',d=>{
  const btn=$('mute-btn');
  if(btn){btn.textContent=d.muted?'🔕 MUTED':'🔔 NOTIF';btn.style.opacity=d.muted?'0.5':'1';}
});
socket.on('update',data=>{
  const prevW=new Set(Object.keys(wifiNets));
  wifiNets={}; for(const n of (data.wifi||[])) wifiNets[n.bssid]=n;
  bleDevs={};  for(const d of (data.ble||[]))  bleDevs[d.addr]=d;
  wifiHistory=data.wifi_history||{};
  bleHistory=data.ble_history||{};
  allEvents=data.events||[];
  allAlerts=data.alerts||[];
  if(data.battery){_batteryData=data.battery;renderBatteryWidget();}
  for(const d of (data.ble||[])) for(const f of (d.frames||[]))
    if(f.type_id===0x10&&f.activity){actMap[f.activity]=(actMap[f.activity]||0)+1;}
  $('wifi-b').textContent=`WiFi: ${Object.keys(wifiNets).length}`;
  $('ble-b').textContent=`BLE: ${Object.keys(bleDevs).length}`;
  $('mode-b').textContent=data.demo?'DEMO':'LIVE';
  $('mode-b').className=data.demo?'badge bm':'badge bg';
  updateWifiStats();
  renderWifiTable(prevW);
  renderBleGrid();
  renderBleLog();
  renderUnifiedLog();
  renderAlerts();
  drawSigBars();
  drawChMap();
  drawWifiTrend();
  drawTlWifi();
  drawTlBle();
  drawActHeatmap();
});

// ══════════════════════════════════════════════════════
// GUI ACTIONS
// ══════════════════════════════════════════════════════
function toggleDemo(){
  socket.emit('toggle_demo');
  showToast({kind:'DEMO',name:'Demo mode',detail:'toggled'});
}
function toggleMute(){
  socket.emit('toggle_mute');
}
function injectDemoBle(){socket.emit('inject_demo_ble');showToast({kind:'INJECT',name:'Demo BLE',detail:'loaded'});}
function injectDemoWifi(){socket.emit('inject_demo_wifi');showToast({kind:'INJECT',name:'Demo WiFi',detail:'loaded'});}
function clearAlerts(){socket.emit('clear_alerts');showToast({kind:'CLEAR',name:'Alerts',detail:'cleared'});}
function setScanInterval(v){
  const n=parseInt(v);
  socket.emit('set_interval',{interval:n});
  const el=$('interval-val');if(el)el.textContent=n+'s';
}

// ── WiFi search/filter ────────────────────────────────
let _wifiFilter='';
function setWifiFilter(v){_wifiFilter=v.toLowerCase();renderWifiTable(null);}

// ── BLE type filter ───────────────────────────────────
let _bleTypeFilter='all';
function setBleTypeFilter(v){_bleTypeFilter=v;renderBleDevices();}
function _bleFilteredDevs(sorted){
  if(_bleTypeFilter==='all')return sorted;
  const typeMap={airpods:0x07,nearby:0x10,action:0x0f,airdrop:0x05,handoff:0x0c,hotspot:0x0d,findmy:0x12,siri:0x08,homekit:0x06};
  const tid=typeMap[_bleTypeFilter];
  if(tid===undefined)return sorted;
  return sorted.filter(d=>(d.frames||[]).some(f=>f.type_id===tid));
}

// ── System Info ───────────────────────────────────────
let _sysInfo=null;
function loadSystemInfo(){
  fetch('/api/system_info').then(r=>r.json()).then(d=>{_sysInfo=d;renderSysInfo();}).catch(()=>{});
}
function renderSysInfo(){
  const d=_sysInfo;if(!d)return;
  // interfaces
  const iw=$('sys-ifaces');if(iw){
    iw.innerHTML=d.interfaces.map(i=>{
      const col=i.status==='UP'?'var(--green)':'var(--dim)';
      return`<div class="si-row"><span class="si-k" style="color:${col}">${esc(i.iface)}</span>`+
        `<span class="si-v">${esc(i.ip4||i.ip6||'—')}</span>`+
        `<span style="font-size:.52rem;color:var(--dim)">${esc(i.mac)}</span>`+
        `<span class="si-badge" style="color:${col}">${esc(i.status)}</span></div>`;
    }).join('');
  }
  // USB
  const uw=$('sys-usb');if(uw){
    if(!d.usb||!d.usb.length){uw.innerHTML='<div style="color:var(--dim);font-size:.62rem;padding:8px">No USB devices</div>';}
    else uw.innerHTML=d.usb.filter(u=>u.name).map(u=>{
      const speed=u.speed?`<span class="si-badge">${esc(u.speed)}</span>`:'';
      return`<div class="si-row"><span class="si-k">${esc(u.name)}</span>`+
        `<span class="si-v" style="color:var(--dim)">${esc(u.vendor)}</span>${speed}</div>`;
    }).join('');
  }
  // metadata
  const hel=$('sys-host');if(hel)hel.textContent=d.hostname;
  const oel=$('sys-os');if(oel)oel.textContent=d.os;
  const iel=$('sys-interval');if(iel)iel.textContent=d.wifi_scan_interval+'s';
  const slid=$('interval-slider');if(slid)slid.value=d.wifi_scan_interval;
  const iv=$('interval-val');if(iv)iv.textContent=d.wifi_scan_interval+'s';
  if(d.battery){_batteryData=d.battery;renderBatteryWidget();}
}

// ── Battery Widget ─────────────────────────────────────
function _ringColor(pct){
  if(pct===null||pct===undefined)return'var(--dim)';
  if(pct>50)return'var(--cyan)';
  if(pct>20)return'var(--yellow)';
  return'var(--red)';
}
function _drawRing(ctx,cx,cy,r,pct,color,label,sublabel,charging){
  const TAU=Math.PI*2,START=-Math.PI/2;
  ctx.clearRect(cx-r-14,cy-r-14,r*2+28,r*2+48);
  // track
  ctx.beginPath();ctx.arc(cx,cy,r,0,TAU);
  ctx.strokeStyle='rgba(255,255,255,0.08)';ctx.lineWidth=6;ctx.stroke();
  // fill
  if(pct!==null&&pct!==undefined){
    ctx.beginPath();ctx.arc(cx,cy,r,START,START+(TAU*(pct/100)));
    ctx.strokeStyle=color;ctx.lineWidth=7;
    ctx.shadowColor=color;ctx.shadowBlur=10;
    ctx.stroke();ctx.shadowBlur=0;
  }
  // icon area — % text
  ctx.fillStyle=pct===null?'rgba(255,255,255,0.25)':color;
  ctx.font='bold 13px Courier New';
  ctx.textAlign='center';ctx.textBaseline='middle';
  ctx.fillText(pct===null?'?':pct+'%',cx,cy+(charging?-6:0));
  if(charging){
    ctx.fillStyle='var(--yellow)';ctx.font='11px serif';
    ctx.fillText('⚡',cx,cy+8);
  }
  // label below ring
  ctx.fillStyle='rgba(255,255,255,0.45)';ctx.font='9px Courier New';
  ctx.fillText(label,cx,cy+r+12);
  if(sublabel){
    ctx.fillStyle='rgba(255,255,255,0.25)';
    ctx.fillText(sublabel,cx,cy+r+23);
  }
}
function renderBatteryWidget(){
  const el=$('sys-battery');if(!el)return;
  // Build list of items: MacBook + ioreg BT + AirPods from live BLE
  const items=[];
  const mac=_batteryData.mac;
  if(mac)items.push({label:'MacBook',sub:mac.source||'',pct:mac.pct,charging:mac.charging});
  // ioreg BT devices
  for(const b of (_batteryData.bt||[])){
    items.push({label:b.name.slice(0,14),sub:'',pct:b.pct,charging:false});
  }
  // AirPods from live BLE scan (more granular — L/R/Case)
  for(const d of Object.values(bleDevs)){
    for(const f of (d.frames||[])){
      if(f.type_id===0x07){
        const L=f.left_bat!=null?Math.round(f.left_bat/15*100):null;
        const R=f.right_bat!=null?Math.round(f.right_bat/15*100):null;
        const C=f.case_bat!=null?Math.round(f.case_bat/15*100):null;
        const model=(f.model||d.name||'AirPods').slice(0,12);
        if(L!==null)items.push({label:'L',sub:model,pct:L,charging:f.left_charging||false,ble:true});
        if(R!==null)items.push({label:'R',sub:model,pct:R,charging:f.right_charging||false,ble:true});
        if(C!==null)items.push({label:'Case',sub:model,pct:C,charging:f.case_charging||false,ble:true});
      }
    }
  }
  if(!items.length){
    el.innerHTML='<div style="color:var(--dim);font-size:.6rem;padding:14px 12px">No battery data available.<br>Connect to AC or pair Bluetooth devices.</div>';
    return;
  }
  const SZ=78,PAD=10,COLS=Math.max(1,Math.floor((el.clientWidth-PAD)/(SZ+PAD)));
  const ROWS=Math.ceil(items.length/COLS);
  const W=el.clientWidth||300,H=Math.max(140,(SZ+50)*ROWS+PAD*2);
  el.innerHTML='';
  const cv=document.createElement('canvas');cv.width=W;cv.height=H;
  cv.style.cssText='display:block;width:100%;height:'+H+'px';
  el.appendChild(cv);
  const ctx=cv.getContext('2d');
  const R=SZ/2-6;
  items.forEach((it,i)=>{
    const col=i%COLS,row=Math.floor(i/COLS);
    const cx=PAD+col*(SZ+PAD)+SZ/2;
    const cy=PAD+row*(SZ+50)+SZ/2;
    _drawRing(ctx,cx,cy,R,it.pct,_ringColor(it.pct),it.label,it.sub,it.charging);
  });
}

// ══════════════════════════════════════════════════════
// TABS
// ══════════════════════════════════════════════════════
function switchTab(name){
  const names=['wifi','ble','timeline','alerts','system'];
  document.querySelectorAll('.tab').forEach((t,i)=>t.classList.toggle('active',names[i]===name));
  document.querySelectorAll('.tab-content').forEach(el=>el.classList.toggle('active',el.id===`tab-${name}`));
  if(name==='system')loadSystemInfo();
  setTimeout(()=>{resizeAll();},60);
}

// ══════════════════════════════════════════════════════
// EVENT LOG
// ══════════════════════════════════════════════════════
function renderLog(wrapId,events,max){
  const wrap=$(wrapId);wrap.innerHTML='';
  for(const ev of events.slice(0,max)){
    const d=document.createElement('div');d.className='log-entry';
    const sc=`le-src-${ev.source}`,tc=`le-${ev.type}`;
    d.innerHTML=`<span class="le-ts">${esc(ev.ts)}</span><span class="${sc} ${tc}">[${esc(ev.type)}]</span><span>${esc(ev.name)} ${esc(ev.detail||'')}</span>`;
    wrap.appendChild(d);
  }
}
function renderBleLog(){renderLog('ble-log-wrap',allEvents,80);}
function renderUnifiedLog(){renderLog('tl-events-wrap',allEvents,150);}

// ══════════════════════════════════════════════════════
// ALERTS
// ══════════════════════════════════════════════════════
function renderAlerts(){
  const list=$('alert-list');list.innerHTML='';
  if(!allAlerts.length){list.innerHTML='<div class="no-sel" style="padding:14px">No alerts — open WiFi, AirDrop and hotspot events appear here</div>';return;}
  for(const al of allAlerts){
    const d=document.createElement('div');d.className='alert-card';
    d.innerHTML=`<div class="at">${esc(al.kind)}</div><div class="ad">${esc(al.name)} — ${esc(al.detail)}</div><div class="ats">${esc(al.ts)}</div>`;
    list.appendChild(d);
  }
}
let _dbgOpen=false;
function toggleDbgBar(){
  _dbgOpen=!_dbgOpen;
  const bar=$('dbg-bar');
  if(bar){bar.style.display=_dbgOpen?'flex':'none';}
  const btn=document.querySelector('button[onclick="toggleDbgBar()"]');
  if(btn)btn.style.color=_dbgOpen?'var(--yellow)':'var(--dim)';
}
function showToast(al){
  const el=document.createElement('div');el.className='toast-item';
  el.innerHTML=`<div class="tk">${esc(al.kind)}</div><div>${esc(al.name)}: ${esc(al.detail)}</div>`;
  $('toast').appendChild(el);setTimeout(()=>el.remove(),5000);
}

// ══════════════════════════════════════════════════════
// EXPORT
// ══════════════════════════════════════════════════════
function exportEventsCSV(){
  const cols=['ts','type','source','name','detail','rssi'];
  let csv=cols.join(',')+'\n';
  for(const ev of allEvents) csv+=cols.map(k=>JSON.stringify(String(ev[k]??''))).join(',')+'\n';
  const a=document.createElement('a');
  a.href='data:text/csv;charset=utf-8,'+encodeURIComponent(csv);
  a.download='events.csv';document.body.appendChild(a);a.click();a.remove();
}
function copySnapshot(){
  const snap={wifi:Object.values(wifiNets),ble:Object.values(bleDevs),events:allEvents,ts:new Date().toISOString()};
  navigator.clipboard.writeText(JSON.stringify(snap,null,2)).then(()=>alert('Copied!'));
}

// ══════════════════════════════════════════════════════
// MODAL (close)
// ══════════════════════════════════════════════════════
function closeModal(e){
  if(e&&e.target!==e.currentTarget)return;
  $('modal-overlay').classList.remove('open');
  selectedWifi=null;selectedBle=null;
  renderWifiTable(null);renderBleGrid();
}
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal();});
