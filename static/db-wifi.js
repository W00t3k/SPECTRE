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
    const a=((net.bssid.split(':').reduce((s,v)=>s+parseInt(v,16),0))%360+360)%360;
    const dn=Math.max(.1,Math.min(.92,(net.rssi+100)/70)),dist=R*(1-dn+.08);
    const bx=cx+dist*Math.cos((a-90)*Math.PI/180),by=cy+dist*Math.sin((a-90)*Math.PI/180);
    const d=Math.hypot(mx-bx,my-by);if(d<bestD){bestD=d;best=net;}
  }
  if(best&&bestD<22)inspectWifi(best.bssid);
});

function drawRadar(){
  const W=rc.width,H=rc.height,cx=W/2,cy=H/2,R=Math.min(cx,cy)-12,now=performance.now();
  rctx.clearRect(0,0,W,H);rctx.fillStyle='#05050f';rctx.fillRect(0,0,W,H);
  for(let i=1;i<=4;i++){
    rctx.beginPath();rctx.arc(cx,cy,R*i/4,0,Math.PI*2);
    rctx.strokeStyle=i===4?'#0e1f30':'#091520';rctx.lineWidth=i===4?1.5:1;rctx.stroke();
    rctx.font='7px Courier New';rctx.fillStyle='#253545';
    rctx.fillText(`${-90+15*i}`,cx+R*i/4+2,cy-2);
  }
  rctx.setLineDash([3,8]);rctx.strokeStyle='#091520';rctx.lineWidth=1;
  for(let a=0;a<360;a+=45){const r=a*Math.PI/180;rctx.beginPath();rctx.moveTo(cx,cy);rctx.lineTo(cx+Math.cos(r)*R,cy+Math.sin(r)*R);rctx.stroke();}
  rctx.setLineDash([]);
  for(let i=60;i>=0;i--){
    const a=(radarAngle-i*2)*Math.PI/180,prev=(radarAngle-(i+1)*2)*Math.PI/180;
    rctx.beginPath();rctx.moveTo(cx,cy);rctx.arc(cx,cy,R,prev-Math.PI/2,a-Math.PI/2);
    rctx.closePath();rctx.fillStyle=`rgba(0,255,200,${Math.pow(1-i/60,1.6)*.4})`;rctx.fill();
  }
  for(let i=ripples.length-1;i>=0;i--){
    const rip=ripples[i];rip.r+=1.5;rip.alpha*=0.91;
    if(rip.alpha<0.02){ripples.splice(i,1);continue;}
    rctx.beginPath();rctx.arc(rip.bx,rip.by,rip.r,0,Math.PI*2);
    rctx.strokeStyle=`${rip.col},${rip.alpha})`;rctx.lineWidth=1.2;rctx.stroke();
  }
  for(const net of Object.values(wifiNets)){
    const ad=((net.bssid.split(':').reduce((s,v)=>s+parseInt(v,16),0))%360+360)%360;
    const dn=Math.max(.1,Math.min(.92,(net.rssi+100)/70)),dist=R*(1-dn+.08);
    const brad=(ad-90)*Math.PI/180,bx=cx+dist*Math.cos(brad),by=cy+dist*Math.sin(brad);
    const isOpen=net.security==='Open'||net.security==='--'||net.security==='NONE';
    const isSel=net.bssid===selectedWifi;
    const diff=Math.abs(((radarAngle-ad)%360+360)%360);
    if(diff<12){
      if(diff<2)ripples.push({bx,by,r:5,alpha:.7,col:isOpen?'rgba(255,0,150,':'rgba(0,255,136,'});
    }
    if(isOpen){rctx.beginPath();rctx.arc(bx,by,10,0,Math.PI*2);rctx.strokeStyle=`rgba(255,0,150,${.3+.2*Math.sin(now/350)})`;rctx.lineWidth=1.5;rctx.stroke();}
    if(isSel){rctx.beginPath();rctx.arc(bx,by,12,0,Math.PI*2);rctx.strokeStyle=`rgba(0,255,200,${.5+.3*Math.sin(now/180)})`;rctx.lineWidth=2;rctx.stroke();}
    const col=rssiColor(net.rssi),pr=isSel?5+1.5*Math.sin(now/200):4;
    rctx.beginPath();rctx.arc(bx,by,pr,0,Math.PI*2);rctx.fillStyle=col;rctx.shadowColor=col;rctx.shadowBlur=isSel?16:8;rctx.fill();rctx.shadowBlur=0;
    const lbl=net.ssid.length>12?net.ssid.slice(0,11)+'…':net.ssid;
    rctx.font=(isSel?'bold ':'')+`8px Courier New`;rctx.fillStyle='rgba(255,255,255,.72)';
    rctx.shadowColor='#000';rctx.shadowBlur=3;rctx.fillText(lbl,bx+8,by-5);rctx.shadowBlur=0;
  }
  const sa=(radarAngle-90)*Math.PI/180;
  rctx.beginPath();rctx.moveTo(cx,cy);rctx.lineTo(cx+Math.cos(sa)*R,cy+Math.sin(sa)*R);
  const g=rctx.createLinearGradient(cx,cy,cx+Math.cos(sa)*R,cy+Math.sin(sa)*R);
  g.addColorStop(0,'rgba(0,255,200,.1)');g.addColorStop(1,'rgba(0,255,200,.95)');
  rctx.strokeStyle=g;rctx.lineWidth=2;rctx.shadowColor='#00ffc8';rctx.shadowBlur=7;rctx.stroke();rctx.shadowBlur=0;
  rctx.beginPath();rctx.arc(cx,cy,4,0,Math.PI*2);rctx.fillStyle='#00ffc8';rctx.shadowColor='#00ffc8';rctx.shadowBlur=10;rctx.fill();rctx.shadowBlur=0;
}

// ══════════════════════════════════════════════════════
// SIGNAL BARS
// ══════════════════════════════════════════════════════
const sc2=$('sig-canvas'),sc2ctx=sc2.getContext('2d');
function sizeSig(){const p=sc2.parentElement;sc2.width=p.clientWidth;sc2.height=p.clientHeight-28;}
function drawSigBars(){
  const W=sc2.width,H=sc2.height;sc2ctx.clearRect(0,0,W,H);sc2ctx.fillStyle='#05050f';sc2ctx.fillRect(0,0,W,H);
  const nets=Object.values(wifiNets).sort((a,b)=>b.rssi-a.rssi).slice(0,22);if(!nets.length)return;
  const PL=8,PR=6,PT=8,PB=22,cH=H-PT-PB,n=nets.length,bW=Math.max(6,Math.floor((W-PL-PR)/n)-2);
  [-90,-75,-60,-45,-30].forEach(v=>{
    const y=PT+cH*(1-Math.max(0,Math.min(1,(v+100)/70)));
    sc2ctx.strokeStyle='#0a1a26';sc2ctx.setLineDash([3,5]);sc2ctx.lineWidth=1;
    sc2ctx.beginPath();sc2ctx.moveTo(PL,y);sc2ctx.lineTo(W-PR,y);sc2ctx.stroke();sc2ctx.setLineDash([]);
    sc2ctx.font='6px Courier New';sc2ctx.fillStyle='#253545';sc2ctx.fillText(`${v}`,PL+1,y-2);
  });
  nets.forEach((net,i)=>{
    const nn=Math.max(0,Math.min(1,(net.rssi+100)/70)),bh=Math.max(3,cH*nn),x=PL+i*(bW+2),col=rssiColor(net.rssi);
    sc2ctx.shadowColor=col;sc2ctx.shadowBlur=7;
    const gr=sc2ctx.createLinearGradient(x,PT+cH-bh,x,PT+cH);gr.addColorStop(0,col);gr.addColorStop(1,col+'33');
    sc2ctx.fillStyle=gr;sc2ctx.fillRect(x,PT+cH-bh,bW,bh);sc2ctx.shadowBlur=0;
    sc2ctx.save();sc2ctx.font='6px Courier New';sc2ctx.fillStyle='#5a7a8a';
    sc2ctx.translate(x+bW/2,PT+cH+3);sc2ctx.rotate(-0.5);
    sc2ctx.fillText(net.ssid.length>7?net.ssid.slice(0,6)+'…':net.ssid,0,0);sc2ctx.restore();
  });
}

// ══════════════════════════════════════════════════════
// CHANNEL MAP
// ══════════════════════════════════════════════════════
const chc=$('ch-canvas'),chctx=chc.getContext('2d');
function sizeCh(){const p=chc.parentElement;chc.width=p.clientWidth;chc.height=p.clientHeight-28;}
function drawChMap(){
  const W=chc.width,H=chc.height;chctx.clearRect(0,0,W,H);chctx.fillStyle='#05050f';chctx.fillRect(0,0,W,H);
  const nets=Object.values(wifiNets),chC={};
  for(const n of nets){const c=String(n.channel||'?');chC[c]=(chC[c]||0)+1;}
  const ch24=[1,2,3,4,5,6,7,8,9,10,11,12,13,14].map(String).filter(c=>chC[c]);
  const ch5=Object.keys(chC).filter(c=>!ch24.includes(c)&&c!=='?').sort((a,b)=>+a-+b);
  const all=[...ch24,...ch5];if(!all.length)return;
  const PL=6,PR=6,PT=8,PB=18,cH=H-PT-PB,maxC=Math.max(...Object.values(chC));
  const bW=Math.max(8,Math.floor((W-PL-PR)/all.length)-2);
  let sepX=null;
  all.forEach((ch,i)=>{
    const is5=ch5.includes(ch),col=is5?'#ff0096':'#00ffc8';
    if(is5&&sepX===null)sepX=PL+i*(bW+2)-3;
    const cnt=chC[ch],bh=Math.max(4,cH*(cnt/maxC)),x=PL+i*(bW+2);
    chctx.shadowColor=col;chctx.shadowBlur=7;
    const gr=chctx.createLinearGradient(x,PT+cH-bh,x,PT+cH);gr.addColorStop(0,col);gr.addColorStop(1,col+'44');
    chctx.fillStyle=gr;chctx.fillRect(x,PT+cH-bh,bW,bh);chctx.shadowBlur=0;
    chctx.font='bold 7px Courier New';chctx.fillStyle=col;chctx.fillText(String(cnt),x+bW/2-3,PT+cH-bh-2);
    chctx.font='6px Courier New';chctx.fillStyle='#5a7a8a';chctx.fillText(ch,x+bW/2-3,PT+cH+11);
  });
  if(sepX!==null){chctx.setLineDash([4,6]);chctx.strokeStyle='#2a3a4a';chctx.lineWidth=1;
    chctx.beginPath();chctx.moveTo(sepX,PT);chctx.lineTo(sepX,PT+cH);chctx.stroke();chctx.setLineDash([]);
    chctx.font='6px Courier New';chctx.fillStyle='#00ffc8';chctx.fillText('2.4G',PL,PT+cH+16);
    chctx.fillStyle='#ff0096';chctx.fillText('5G',sepX+3,PT+8);}
}

// ══════════════════════════════════════════════════════
// WIFI TREND (mini panel)
// ══════════════════════════════════════════════════════
const wtlc=$('wifi-tl-canvas'),wtlctx=wtlc.getContext('2d');
function sizeWifiTl(){const p=wtlc.parentElement;wtlc.width=p.clientWidth;wtlc.height=p.clientHeight-28;}
function drawWifiTrend(){
  const W=wtlc.width,H=wtlc.height;wtlctx.clearRect(0,0,W,H);wtlctx.fillStyle='#05050f';wtlctx.fillRect(0,0,W,H);
  const nets=Object.values(wifiNets).sort((a,b)=>b.rssi-a.rssi).slice(0,6);if(!nets.length)return;
  const PL=28,PR=4,PT=6,PB=6,cH=H-PT-PB,cW=W-PL-PR,mn=-100,mx=-25,rng=mx-mn;
  [-90,-75,-60,-45,-30].forEach(v=>{
    const y=PT+cH-(v-mn)/rng*cH;
    wtlctx.strokeStyle='#0a1a26';wtlctx.setLineDash([3,5]);wtlctx.lineWidth=1;
    wtlctx.beginPath();wtlctx.moveTo(PL,y);wtlctx.lineTo(W-PR,y);wtlctx.stroke();wtlctx.setLineDash([]);
    wtlctx.font='6px Courier New';wtlctx.fillStyle='#253545';wtlctx.fillText(`${v}`,2,y+3);
  });
  nets.forEach((net,ci)=>{
    const hist=(wifiHistory[net.bssid]||[]).map(p=>Array.isArray(p)?p[1]:p);
    if(hist.length<2)return;
    const col=TCOLS[ci%TCOLS.length];
    wtlctx.beginPath();
    hist.forEach((v,i)=>{const x=PL+i/(hist.length-1)*cW,y=PT+cH-(v-mn)/rng*cH;i?wtlctx.lineTo(x,y):wtlctx.moveTo(x,y);});
    wtlctx.strokeStyle=col;wtlctx.lineWidth=1.5;wtlctx.shadowColor=col;wtlctx.shadowBlur=3;wtlctx.stroke();wtlctx.shadowBlur=0;
  });
}
