// ══════════════════════════════════════════════════════
// SPARKLINE helper
// ══════════════════════════════════════════════════════
function drawSparkline(cv,hist,col){
  const W=cv.width,H=cv.height,ctx=cv.getContext('2d');
  ctx.clearRect(0,0,W,H);
  const pts=(hist||[]).map(p=>Array.isArray(p)?p[1]:p).filter(v=>v!=null);
  if(pts.length<2)return;
  const mn=-100,mx=-25,rng=mx-mn;
  ctx.beginPath();
  pts.forEach((v,i)=>{const x=i/(pts.length-1)*W,y=H-(v-mn)/rng*H;i?ctx.lineTo(x,y):ctx.moveTo(x,y);});
  ctx.strokeStyle=col;ctx.lineWidth=1.5;ctx.shadowColor=col;ctx.shadowBlur=4;ctx.stroke();ctx.shadowBlur=0;
}

// ══════════════════════════════════════════════════════
// WIFI TABLE
// ══════════════════════════════════════════════════════
function wSort(k){wSortKey=k;renderWifiTable(null);}
function renderWifiTable(prevKeys){
  const tbody=$('wifi-tbody');
  let sorted=Object.values(wifiNets);
  if(wSortKey==='rssi') sorted.sort((a,b)=>b.rssi-a.rssi);
  else if(wSortKey==='ssid') sorted.sort((a,b)=>a.ssid.localeCompare(b.ssid));
  else if(wSortKey==='channel') sorted.sort((a,b)=>+a.channel-+b.channel);
  else if(wSortKey==='security') sorted.sort((a,b)=>a.security.localeCompare(b.security));
  if(typeof _wifiFilter==='string'&&_wifiFilter){
    sorted=sorted.filter(n=>
      n.ssid.toLowerCase().includes(_wifiFilter)||
      n.bssid.toLowerCase().includes(_wifiFilter)||
      n.security.toLowerCase().includes(_wifiFilter)||
      String(n.channel).includes(_wifiFilter));
  }
  const existing={};for(const tr of tbody.rows)existing[tr.dataset.bssid]=tr;
  const seen=new Set();
  for(const net of sorted){
    seen.add(net.bssid);
    const isNew=prevKeys&&!prevKeys.has(net.bssid);
    const nb=Math.max(1,Math.round(norm(net.rssi)*5));
    const sig=Array.from({length:5},(_,i)=>{
      const h=4+i*3,c=i<nb?rssiColor(net.rssi):'#1a2a3a';
      return `<span class="sb" style="height:${h}px;background:${c}"></span>`;
    }).join('');
    const rc=norm(net.rssi)>.6?'rs':norm(net.rssi)>.3?'rm':'rw';
    const sc=net.security==='Open'||net.security==='--'||net.security==='NONE'?'so':net.security==='WPA3'?'sw3':'sw2';
    const isOpen=sc==='so';
    const vnd=vendor(net.bssid);
    let tr=existing[net.bssid];
    if(!tr){tr=document.createElement('tr');tr.dataset.bssid=net.bssid;tbody.appendChild(tr);if(isNew)tr.classList.add('new-row');}
    tr.onclick=()=>inspectWifi(net.bssid);
    tr.className=net.bssid===selectedWifi?'sel':'';
    const ssidHidden=net.ssid==='<hidden>';
    const ssidHtml=`<div style="font-weight:bold;font-size:.72rem;color:${ssidHidden?'var(--dim)':'var(--white)'}">${esc(net.ssid)}${isOpen?'<span class="ti">⚠</span>':''}</div>`+
      `<div style="font-size:.54rem;color:var(--dim);margin-top:1px">${esc(net.bssid)}</div>`;
    tr.innerHTML=[
      `<td>${ssidHtml}</td>`,
      `<td style="color:var(--cyan);font-size:.62rem;font-weight:bold">${esc(vnd!=='?'?vnd:'')}</td>`,
      `<td class="${rc}" style="font-weight:bold">${net.rssi}</td>`,
      `<td style="display:flex;align-items:flex-end;padding:2px 7px">${sig}</td>`,
      `<td>${net.channel}</td>`,
      `<td class="${parseInt(net.channel)>14?'b5':'b24'}">${band(net.channel)}</td>`,
      `<td class="${sc}">${esc(net.security)}</td>`,
    ].join('');
  }
  for(const[b,tr]of Object.entries(existing))if(!seen.has(b))tbody.removeChild(tr);
}

// ══════════════════════════════════════════════════════
// WIFI STATS
// ══════════════════════════════════════════════════════
function updateWifiStats(){
  const nets=Object.values(wifiNets);
  const opens=nets.filter(n=>n.security==='Open'||n.security==='--'||n.security==='NONE');
  const best=nets.reduce((a,b)=>(!a||b.rssi>a.rssi)?b:a,null);
  const worst=nets.reduce((a,b)=>(!a||b.rssi<a.rssi)?b:a,null);
  $('ws-total').textContent=nets.length;
  $('ws-24').textContent=nets.filter(n=>parseInt(n.channel)<=14).length;
  $('ws-5').textContent=nets.filter(n=>parseInt(n.channel)>14).length;
  $('ws-open').textContent=opens.length;
  $('ws-wpa3').textContent=nets.filter(n=>n.security==='WPA3').length;
  $('ws-hid').textContent=nets.filter(n=>n.ssid==='<hidden>').length;
  $('ws-best').textContent=best?`${best.rssi}`:'-';
  $('ws-worst').textContent=worst?`${worst.rssi}`:'-';
  if(opens.length){$('alert-b').style.display='';$('alert-b').textContent=`⚠ ${opens.length} OPEN`;}
  else $('alert-b').style.display='none';
}

// ══════════════════════════════════════════════════════
// WIFI MODAL
// ══════════════════════════════════════════════════════
function inspectWifi(bssid){
  const net=wifiNets[bssid];if(!net)return;
  selectedWifi=bssid;renderWifiTable(null);
  $('modal-title').textContent=net.ssid==='<hidden>'?'[ HIDDEN ]':net.ssid;
  const rows=[['BSSID',net.bssid],['VENDOR',vendor(net.bssid)],
    ['RSSI',`${net.rssi} dBm`],['CHANNEL',net.channel],['BAND',band(net.channel)],
    ['SECURITY',net.security],['LAST SEEN',elapsed(net.last_seen)]];
  $('modal-body').innerHTML=rows.map(([k,v])=>`<div class="mrow"><span class="mk">${k}</span><span class="mv">${esc(v)}</span></div>`).join('');
  const mc=$('modal-spark-cv');mc.width=mc.parentElement.offsetWidth||280;
  const hist=(wifiHistory[bssid]||[]).map(p=>Array.isArray(p)?p[1]:p);
  drawSparkline(mc,hist.length?hist:[net.rssi],rssiColor(net.rssi));
  $('modal-overlay').classList.add('open');
}

// ══════════════════════════════════════════════════════
// RADAR
// ══════════════════════════════════════════════════════
const rc=$('radar-canvas'),rctx=rc.getContext('2d');
function sizeRadar(){const p=rc.parentElement;rc.width=p.clientWidth;rc.height=p.clientHeight-28;}
rc.addEventListener('click',e=>{
  const rect=rc.getBoundingClientRect(),mx=e.clientX-rect.left,my=e.clientY-rect.top;
  const W=rc.width,H=rc.height,cx=W/2,cy=H/2,R=Math.min(cx,cy)-12;
  let best=null,bestD=999;
  for(const net of Object.values(wifiNets)){
    const a=_bssidAngle(net.bssid);
    const dn=Math.max(.08,Math.min(.95,(net.rssi+100)/70)),dist=R*(1-dn+.05);
    const bx=cx+dist*Math.cos((a-90)*Math.PI/180),by=cy+dist*Math.sin((a-90)*Math.PI/180);
    const d=Math.hypot(mx-bx,my-by);if(d<bestD){bestD=d;best=net;}
  }
  if(best&&bestD<22)inspectWifi(best.bssid);
});

// Stable per-BSSID angle using all 6 octets with prime mixing for good spread
function _bssidAngle(bssid){
  const parts=bssid.split(':');
  let h=0;
  const primes=[31,37,41,43,47,53];
  for(let i=0;i<parts.length;i++) h=(h*primes[i%primes.length]+parseInt(parts[i]||'0',16))>>>0;
  return(h%360+360)%360;
}

function drawRadar(){
  const W=rc.width,H=rc.height,cx=W/2,cy=H/2,R=Math.min(cx,cy)-14,now=performance.now();
  rctx.clearRect(0,0,W,H);

  // Deep space background gradient
  const bg=rctx.createRadialGradient(cx,cy,0,cx,cy,R*1.1);
  bg.addColorStop(0,'#07101f');bg.addColorStop(1,'#020810');
  rctx.fillStyle=bg;rctx.fillRect(0,0,W,H);

  // Range rings with dBm labels
  const dbmLabels={1:'-85dBm',2:'-70dBm',3:'-55dBm',4:'-40dBm'};
  for(let i=1;i<=4;i++){
    rctx.beginPath();rctx.arc(cx,cy,R*i/4,0,Math.PI*2);
    const alpha=i===4?0.35:0.15;
    rctx.strokeStyle=`rgba(0,220,180,${alpha})`;rctx.lineWidth=i===4?1.2:0.7;rctx.stroke();
    rctx.font='7px Courier New';rctx.fillStyle='rgba(0,200,160,0.35)';rctx.textAlign='left';
    rctx.fillText(dbmLabels[i],cx+R*i/4+3,cy-3);
  }

  // Spoke lines
  rctx.setLineDash([2,10]);rctx.strokeStyle='rgba(0,180,140,0.12)';rctx.lineWidth=0.8;
  for(let a=0;a<360;a+=30){
    const r=a*Math.PI/180;
    rctx.beginPath();rctx.moveTo(cx,cy);rctx.lineTo(cx+Math.cos(r)*R,cy+Math.sin(r)*R);rctx.stroke();
  }
  rctx.setLineDash([]);

  // Sweep trail — brighter, more dramatic
  for(let i=70;i>=0;i--){
    const a=(radarAngle-i*2.2)*Math.PI/180,prev=(radarAngle-(i+1)*2.2)*Math.PI/180;
    rctx.beginPath();rctx.moveTo(cx,cy);rctx.arc(cx,cy,R,prev-Math.PI/2,a-Math.PI/2);
    rctx.closePath();
    const t=Math.pow(1-i/70,2);
    rctx.fillStyle=`rgba(0,255,200,${t*0.38})`;rctx.fill();
  }

  // Ripples
  for(let i=ripples.length-1;i>=0;i--){
    const rip=ripples[i];rip.r+=1.8;rip.alpha*=0.90;
    if(rip.alpha<0.02){ripples.splice(i,1);continue;}
    rctx.beginPath();rctx.arc(rip.bx,rip.by,rip.r,0,Math.PI*2);
    rctx.strokeStyle=`${rip.col},${rip.alpha})`;rctx.lineWidth=1.5;rctx.stroke();
  }

  // --- Compute dot positions then do label collision resolution ---
  const nets=Object.values(wifiNets);
  const dotData=nets.map(net=>{
    const ad=_bssidAngle(net.bssid);
    const dn=Math.max(.08,Math.min(.95,(net.rssi+100)/70));
    const dist=R*(1-dn+.05);
    const brad=(ad-90)*Math.PI/180;
    return {net,ad,bx:cx+dist*Math.cos(brad),by:cy+dist*Math.sin(brad)};
  });

  // Draw dots + rings first (below labels)
  for(const {net,ad,bx,by} of dotData){
    const isOpen=net.security==='Open'||net.security==='--'||net.security==='NONE';
    const isSel=net.bssid===selectedWifi;
    const diff=((radarAngle-ad)%360+360)%360;

    // Sweep hit → ripple
    if(diff<3) ripples.push({bx,by,r:4,alpha:.75,col:isOpen?'rgba(255,50,150,':'rgba(0,255,136,'});

    // Open network — pulsing danger ring
    if(isOpen){
      rctx.beginPath();rctx.arc(bx,by,13,0,Math.PI*2);
      rctx.strokeStyle=`rgba(255,30,120,${.45+.25*Math.sin(now/280)})`;
      rctx.lineWidth=2;rctx.shadowColor='#ff1e78';rctx.shadowBlur=12;rctx.stroke();rctx.shadowBlur=0;
    }
    // Selected ring
    if(isSel){
      rctx.beginPath();rctx.arc(bx,by,15,0,Math.PI*2);
      rctx.strokeStyle=`rgba(0,255,200,${.7+.3*Math.sin(now/160)})`;
      rctx.lineWidth=2.5;rctx.shadowColor='#00ffc8';rctx.shadowBlur=18;rctx.stroke();rctx.shadowBlur=0;
    }
    const col=rssiColor(net.rssi);
    const pr=isSel?6+1.5*Math.sin(now/200):4.5;
    rctx.beginPath();rctx.arc(bx,by,pr,0,Math.PI*2);
    rctx.fillStyle=col;rctx.shadowColor=col;rctx.shadowBlur=isSel?20:10;rctx.fill();rctx.shadowBlur=0;
  }

  // --- Label collision resolution ---
  // Candidate label positions: right, left, above, below, diagonals
  const OFFSETS=[[10,-6],[-10,-6],[0,-14],[0,10],[10,8],[-10,8]];
  const placed=[]; // {x1,y1,x2,y2} bounding boxes

  function overlaps(x,y,w,h){
    for(const b of placed){
      if(x<b.x2+2&&x+w>b.x1-2&&y<b.y2+2&&y+h>b.y1-2)return true;
    }
    return false;
  }

  rctx.font='9px "Courier New"';
  for(const {net,bx,by} of dotData){
    const isSel=net.bssid===selectedWifi;
    const lbl=(net.ssid&&net.ssid!=='<hidden>')?
      (net.ssid.length>14?net.ssid.slice(0,13)+'…':net.ssid):'<hidden>';
    const tw=rctx.measureText(lbl).width;
    const th=10;
    let placed_=false;
    for(const [ox,oy] of OFFSETS){
      const lx=bx+ox,ly=by+oy;
      if(!overlaps(lx,ly,tw,th)){
        placed.push({x1:lx,y1:ly-th,x2:lx+tw,y2:ly});
        // connector line from dot to label if offset is large
        if(Math.hypot(ox,oy)>12){
          rctx.beginPath();rctx.moveTo(bx,by);rctx.lineTo(lx,ly-4);
          rctx.strokeStyle='rgba(255,255,255,0.15)';rctx.lineWidth=0.7;rctx.stroke();
        }
        rctx.font=(isSel?'bold ':'')+'9px "Courier New"';
        const alpha=isSel?1.0:0.82;
        rctx.fillStyle=isSel?`rgba(0,255,200,${alpha})`:`rgba(220,240,255,${alpha})`;
        rctx.shadowColor='#000';rctx.shadowBlur=4;
        rctx.fillText(lbl,lx,ly);
        rctx.shadowBlur=0;
        placed_=true;break;
      }
    }
    // fallback — still draw if all slots taken, dimmer
    if(!placed_){
      rctx.font='8px "Courier New"';
      rctx.fillStyle='rgba(180,200,220,0.45)';
      rctx.shadowColor='#000';rctx.shadowBlur=3;
      rctx.fillText(lbl,bx+10,by-5);rctx.shadowBlur=0;
    }
  }
  rctx.textAlign='left';

  // Sweep line — bright gradient
  const sa=(radarAngle-90)*Math.PI/180;
  const g=rctx.createLinearGradient(cx,cy,cx+Math.cos(sa)*R,cy+Math.sin(sa)*R);
  g.addColorStop(0,'rgba(0,255,200,.05)');g.addColorStop(0.6,'rgba(0,255,200,.6)');g.addColorStop(1,'rgba(0,255,200,1)');
  rctx.beginPath();rctx.moveTo(cx,cy);rctx.lineTo(cx+Math.cos(sa)*R,cy+Math.sin(sa)*R);
  rctx.strokeStyle=g;rctx.lineWidth=2.5;rctx.shadowColor='#00ffc8';rctx.shadowBlur=10;rctx.stroke();rctx.shadowBlur=0;

  // Centre hub
  rctx.beginPath();rctx.arc(cx,cy,5,0,Math.PI*2);
  rctx.fillStyle='#00ffc8';rctx.shadowColor='#00ffc8';rctx.shadowBlur=14;rctx.fill();rctx.shadowBlur=0;
}

// ══════════════════════════════════════════════════════
// SIGNAL BARS
// ══════════════════════════════════════════════════════
const sc2=$('sig-canvas'),sc2ctx=sc2.getContext('2d');
function sizeSig(){const p=sc2.parentElement;sc2.width=p.clientWidth;sc2.height=p.clientHeight-28;}
function _roundRect(ctx,x,y,w,h,r){
  if(h<r*2)r=h/2;
  ctx.beginPath();ctx.moveTo(x+r,y);ctx.lineTo(x+w-r,y);
  ctx.quadraticCurveTo(x+w,y,x+w,y+r);ctx.lineTo(x+w,y+h);
  ctx.lineTo(x,y+h);ctx.lineTo(x,y+r);
  ctx.quadraticCurveTo(x,y,x+r,y);ctx.closePath();
}
function drawSigBars(){
  const W=sc2.width,H=sc2.height;
  sc2ctx.clearRect(0,0,W,H);
  // SciChart navy bg
  const bg=sc2ctx.createLinearGradient(0,0,0,H);
  bg.addColorStop(0,'#0d1b2e');bg.addColorStop(1,'#091524');
  sc2ctx.fillStyle=bg;sc2ctx.fillRect(0,0,W,H);
  const nets=Object.values(wifiNets).sort((a,b)=>b.rssi-a.rssi).slice(0,20);if(!nets.length)return;
  const PL=6,PR=6,PT=10,PB=26,cH=H-PT-PB,n=nets.length;
  const gap=2,bW=Math.max(7,Math.floor((W-PL-PR-(n-1)*gap)/n));
  // dashed grid lines — SciChart style
  [-90,-75,-60,-45,-30].forEach(v=>{
    const y=PT+cH*(1-Math.max(0,Math.min(1,(v+100)/70)));
    sc2ctx.strokeStyle='rgba(77,173,200,0.15)';sc2ctx.setLineDash([3,5]);sc2ctx.lineWidth=1;
    sc2ctx.beginPath();sc2ctx.moveTo(PL,y);sc2ctx.lineTo(W-PR,y);sc2ctx.stroke();
    sc2ctx.setLineDash([]);
    sc2ctx.font='5.5px Courier New';sc2ctx.fillStyle='rgba(90,180,232,0.4)';
    sc2ctx.fillText(`${v}`,PL,y-2);
  });
  nets.forEach((net,i)=>{
    const nn=Math.max(0,Math.min(1,(net.rssi+100)/70));
    const bh=Math.max(4,cH*nn);
    const x=PL+i*(bW+gap),y=PT+cH-bh;
    // orange for strong signals, icy blue for weak — like SciChart spectra
    const hot=net.rssi>=-60;
    const topC=hot?'#ff8c42':'#4dd9f5';
    const midC=hot?'rgba(224,90,32,':'rgba(45,138,185,';
    sc2ctx.save();
    sc2ctx.shadowColor=topC;sc2ctx.shadowBlur=hot?16:10;
    const gr=sc2ctx.createLinearGradient(x,y,x,PT+cH);
    gr.addColorStop(0,topC);
    gr.addColorStop(0.3,midC+'cc)');
    gr.addColorStop(0.7,midC+'44)');
    gr.addColorStop(1,midC+'0a)');
    _roundRect(sc2ctx,x,y,bW,bh,2);
    sc2ctx.fillStyle=gr;sc2ctx.fill();
    sc2ctx.restore();
    // bright cap
    sc2ctx.beginPath();sc2ctx.moveTo(x+1,y+1);sc2ctx.lineTo(x+bW-1,y+1);
    sc2ctx.strokeStyle=topC;sc2ctx.lineWidth=1.5;
    sc2ctx.shadowColor=topC;sc2ctx.shadowBlur=8;sc2ctx.stroke();sc2ctx.shadowBlur=0;
    // RSSI
    sc2ctx.font='bold 6px Courier New';sc2ctx.fillStyle=topC;
    sc2ctx.textAlign='center';sc2ctx.fillText(`${net.rssi}`,x+bW/2,y-3);
    // SSID rotated
    sc2ctx.save();sc2ctx.font='6px Courier New';sc2ctx.fillStyle='rgba(90,180,232,0.55)';
    sc2ctx.translate(x+bW/2,PT+cH+4);sc2ctx.rotate(-0.45);
    sc2ctx.fillText((net.ssid||'').slice(0,9),0,0);sc2ctx.restore();
  });
  sc2ctx.textAlign='left';
}

// ══════════════════════════════════════════════════════
// CHANNEL MAP
// ══════════════════════════════════════════════════════
const chc=$('ch-canvas'),chctx=chc.getContext('2d');
function sizeCh(){const p=chc.parentElement;chc.width=p.clientWidth;chc.height=p.clientHeight-28;}
function drawChMap(){
  const W=chc.width,H=chc.height;
  chctx.clearRect(0,0,W,H);
  const nets=Object.values(wifiNets),chC={};
  for(const n of nets){const c=String(n.channel||'?');chC[c]=(chC[c]||0)+1;}
  const ch24=[1,2,3,4,5,6,7,8,9,10,11,12,13,14].map(String).filter(c=>chC[c]);
  const ch5=Object.keys(chC).filter(c=>!ch24.includes(c)&&c!=='?').sort((a,b)=>+a-+b);
  const all=[...ch24,...ch5];if(!all.length)return;
  const PL=6,PR=6,PT=10,PB=20,cH=H-PT-PB,maxC=Math.max(...Object.values(chC));
  const gap=3,bW=Math.max(10,Math.floor((W-PL-PR-(all.length-1)*gap)/all.length));
  let sepX=null;
  // navy bg
  const bg2=chctx.createLinearGradient(0,0,0,H);
  bg2.addColorStop(0,'#0d1b2e');bg2.addColorStop(1,'#091524');
  chctx.fillStyle=bg2;chctx.fillRect(0,0,W,H);
  all.forEach((ch,i)=>{
    const is5=ch5.includes(ch);
    // SciChart: 2.4GHz = orange, 5GHz = icy blue
    const col=is5?'#4dd9f5':'#ff8c42';
    const midC=is5?'rgba(45,138,185,':'rgba(200,90,20,';
    if(is5&&sepX===null)sepX=PL+i*(bW+gap)-4;
    const cnt=chC[ch],nn=cnt/maxC,bh=Math.max(6,cH*nn);
    const x=PL+i*(bW+gap),y=PT+cH-bh;
    chctx.save();
    chctx.shadowColor=col;chctx.shadowBlur=14;
    const gr=chctx.createLinearGradient(x,y,x,PT+cH);
    gr.addColorStop(0,col);
    gr.addColorStop(0.35,midC+'bb)');
    gr.addColorStop(0.75,midC+'33)');
    gr.addColorStop(1,midC+'06)');
    _roundRect(chctx,x,y,bW,bh,3);
    chctx.fillStyle=gr;chctx.fill();
    chctx.restore();
    // dashed outline — SciChart cross-section style
    chctx.save();chctx.setLineDash([2,3]);
    _roundRect(chctx,x,y,bW,bh,3);
    chctx.strokeStyle=col+'88';chctx.lineWidth=1;chctx.stroke();
    chctx.restore();
    chctx.font='bold 7px Courier New';chctx.fillStyle=col;
    chctx.textAlign='center';chctx.fillText(String(cnt),x+bW/2,y-3);
    chctx.font='6.5px Courier New';chctx.fillStyle='rgba(90,180,232,0.5)';
    chctx.fillText(ch,x+bW/2,PT+cH+12);
  });
  chctx.textAlign='left';
  if(sepX!==null){
    chctx.setLineDash([3,6]);chctx.strokeStyle='rgba(77,217,245,.12)';chctx.lineWidth=1;
    chctx.beginPath();chctx.moveTo(sepX,PT+4);chctx.lineTo(sepX,PT+cH-4);chctx.stroke();
    chctx.setLineDash([]);
    chctx.font='bold 6px Courier New';
    chctx.fillStyle='rgba(255,140,66,.5)';chctx.fillText('2.4G',PL+2,PT+cH+18);
    chctx.fillStyle='rgba(77,217,245,.5)';chctx.fillText('5G',sepX+4,PT+10);
  }
}

// ══════════════════════════════════════════════════════
// WIFI TREND (mini panel)
// ══════════════════════════════════════════════════════
const wtlc=$('wifi-tl-canvas'),wtlctx=wtlc.getContext('2d');
function sizeWifiTl(){const p=wtlc.parentElement;wtlc.width=p.clientWidth;wtlc.height=p.clientHeight-28;}
function drawWifiTrend(){
  const W=wtlc.width,H=wtlc.height;
  wtlctx.clearRect(0,0,W,H);
  // SciChart navy bg
  const bg=wtlctx.createLinearGradient(0,0,0,H);
  bg.addColorStop(0,'#0d1b2e');bg.addColorStop(1,'#091524');
  wtlctx.fillStyle=bg;wtlctx.fillRect(0,0,W,H);
  const nets=Object.values(wifiNets).sort((a,b)=>b.rssi-a.rssi).slice(0,6);if(!nets.length)return;
  const PL=26,PR=4,PT=6,PB=6,cH=H-PT-PB,cW=W-PL-PR,mn=-100,mx=-25,rng=mx-mn;
  // dashed grid
  [-90,-75,-60,-45,-30].forEach(v=>{
    const y=PT+cH-(v-mn)/rng*cH;
    wtlctx.strokeStyle='rgba(77,173,200,0.15)';wtlctx.setLineDash([3,5]);wtlctx.lineWidth=1;
    wtlctx.beginPath();wtlctx.moveTo(PL,y);wtlctx.lineTo(W-PR,y);wtlctx.stroke();
    wtlctx.setLineDash([]);
    wtlctx.font='5.5px Courier New';wtlctx.fillStyle='rgba(90,180,232,0.4)';wtlctx.fillText(`${v}`,2,y+3);
  });
  // SciChart waterfall: layer icy-blue fills back-to-front, orange for hottest
  const SCI_COLS=['#ff8c42','#4dd9f5','#5ab4e8','#7ec8e3','#a0d8ef','#c5eaf7'];
  [...nets].reverse().forEach((net,rci)=>{
    const ci=nets.length-1-rci;
    const hist=(wifiHistory[net.bssid]||[]).map(p=>Array.isArray(p)?p[1]:p);
    if(hist.length<2)return;
    const col=SCI_COLS[ci%SCI_COLS.length];
    const pts=hist.map((v,i)=>({x:PL+i/(hist.length-1)*cW,y:PT+cH-(Math.max(mn,Math.min(mx,v))-mn)/rng*cH}));
    // filled area under curve
    wtlctx.beginPath();
    wtlctx.moveTo(pts[0].x,PT+cH);
    pts.forEach(p=>wtlctx.lineTo(p.x,p.y));
    wtlctx.lineTo(pts[pts.length-1].x,PT+cH);
    wtlctx.closePath();
    const fill=wtlctx.createLinearGradient(0,PT,0,PT+cH);
    fill.addColorStop(0,col+'35');fill.addColorStop(0.6,col+'18');fill.addColorStop(1,col+'04');
    wtlctx.fillStyle=fill;wtlctx.fill();
    // dashed outline stroke — SciChart cross-section look
    wtlctx.save();wtlctx.setLineDash(ci===0?[]:[2,3]);
    wtlctx.beginPath();
    pts.forEach((p,i)=>i?wtlctx.lineTo(p.x,p.y):wtlctx.moveTo(p.x,p.y));
    wtlctx.strokeStyle=col;wtlctx.lineWidth=ci===0?2:1.2;
    wtlctx.shadowColor=col;wtlctx.shadowBlur=ci===0?8:3;wtlctx.stroke();
    wtlctx.restore();
    // endpoint dot
    const lp=pts[pts.length-1];
    wtlctx.beginPath();wtlctx.arc(lp.x,lp.y,ci===0?3:2,0,Math.PI*2);
    wtlctx.fillStyle=col;wtlctx.shadowColor=col;wtlctx.shadowBlur=10;wtlctx.fill();wtlctx.shadowBlur=0;
  });
}
