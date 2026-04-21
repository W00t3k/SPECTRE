// ══════════════════════════════════════════════════════
// TIMELINE TAB CHARTS
// ══════════════════════════════════════════════════════
const tlwc=$('tl-wifi-canvas'),tlwctx=tlwc.getContext('2d');
const tlbc=$('tl-ble-canvas'),tlbctx=tlbc.getContext('2d');
const tlac=$('tl-act-canvas'),tlactx=tlac.getContext('2d');
function sizeTl(){
  ['tl-wifi-canvas','tl-ble-canvas','tl-act-canvas'].forEach(id=>{
    const cv=$(id),p=cv.parentElement;cv.width=p.clientWidth;cv.height=p.clientHeight-28;
  });
}
function drawTlChart(ctx,W,H,entries){
  ctx.clearRect(0,0,W,H);ctx.fillStyle='#05050f';ctx.fillRect(0,0,W,H);
  if(!entries.length){ctx.font='10px Courier New';ctx.fillStyle='#3a4a5a';ctx.fillText('No data yet',W/2-40,H/2);return;}
  const PL=30,PR=6,PT=8,PB=8,cH=H-PT-PB,cW=W-PL-PR,mn=-100,mx=-25,rng=mx-mn;
  [-90,-75,-60,-45,-30].forEach(v=>{
    const y=PT+cH-(v-mn)/rng*cH;
    ctx.strokeStyle='#0a1a26';ctx.setLineDash([3,6]);ctx.lineWidth=1;
    ctx.beginPath();ctx.moveTo(PL,y);ctx.lineTo(W-PR,y);ctx.stroke();ctx.setLineDash([]);
    ctx.font='6px Courier New';ctx.fillStyle='#253545';ctx.fillText(`${v}`,2,y+3);
  });
  entries.forEach(({pts,col})=>{
    if(!pts||pts.length<2)return;
    ctx.beginPath();
    pts.forEach((p,i)=>{const v=Array.isArray(p)?p[1]:p,x=PL+i/(pts.length-1)*cW,y=PT+cH-(v-mn)/rng*cH;i?ctx.lineTo(x,y):ctx.moveTo(x,y);});
    ctx.strokeStyle=col;ctx.lineWidth=1.5;ctx.shadowColor=col;ctx.shadowBlur=4;ctx.stroke();ctx.shadowBlur=0;
  });
}
function drawTlWifi(){
  const nets=Object.values(wifiNets).sort((a,b)=>b.rssi-a.rssi).slice(0,8);
  drawTlChart(tlwctx,tlwc.width,tlwc.height,nets.map((n,i)=>({pts:wifiHistory[n.bssid]||[],col:TCOLS[i]})));
}
function drawTlBle(){
  const devs=Object.values(bleDevs).sort((a,b)=>b.rssi-a.rssi).slice(0,8);
  drawTlChart(tlbctx,tlbc.width,tlbc.height,devs.map((d,i)=>({pts:bleHistory[d.addr]||[],col:TCOLS[i]})));
}
function drawActHeatmap(){
  const W=tlac.width,H=tlac.height;
  tlactx.clearRect(0,0,W,H);tlactx.fillStyle='#05050f';tlactx.fillRect(0,0,W,H);
  const entries=Object.entries(actMap).sort((a,b)=>b[1]-a[1]).slice(0,10);
  if(!entries.length){tlactx.font='10px Courier New';tlactx.fillStyle='#3a4a5a';tlactx.fillText('No Nearby Info frames yet',W/2-80,H/2);return;}
  const PL=140,PR=50,PT=8,PB=8,cH=H-PT-PB,rowH=Math.floor(cH/entries.length)-1;
  const maxV=entries[0][1];
  entries.forEach(([act,cnt],i)=>{
    const y=PT+i*(rowH+1),bW=Math.max(4,(W-PL-PR)*(cnt/maxV)),col=TCOLS[i%TCOLS.length];
    tlactx.shadowColor=col;tlactx.shadowBlur=6;
    const gr=tlactx.createLinearGradient(PL,y,PL+bW,y);gr.addColorStop(0,col);gr.addColorStop(1,col+'44');
    tlactx.fillStyle=gr;tlactx.fillRect(PL,y,bW,rowH);tlactx.shadowBlur=0;
    tlactx.font='9px Courier New';tlactx.fillStyle=col;tlactx.fillText(act.slice(0,18),2,y+rowH-2);
    tlactx.fillStyle='#8aacbc';tlactx.fillText(String(cnt),PL+bW+4,y+rowH-2);
  });
}

// ══════════════════════════════════════════════════════
// RESIZE & ANIMATION LOOP
// ══════════════════════════════════════════════════════
function resizeAll(){
  for(const tabId of Object.keys(DEFAULT_LAYOUTS))applyDefaultLayout(tabId);
  sizeRadar();sizeSig();sizeCh();sizeWifiTl();sizeTl();
}
window.addEventListener('resize',resizeAll);
initAllPanels();
resizeAll();

function animate(){
  radarAngle=(radarAngle+0.8)%360;
  drawRadar();
  requestAnimationFrame(animate);
}
animate();
