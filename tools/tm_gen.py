#!/usr/bin/env python3
"""Generate the Metro Time Machine artifact (Radiooooo-inspired map + sonification)."""
import json, os
_ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DAT=os.path.join(_ROOT,"data")
D = json.load(open(os.path.join(_DAT,"timemachine_data.json"),encoding="utf-8"))
data_js = json.dumps(D, ensure_ascii=False, separators=(",", ":"))
WORLD = json.load(open(os.path.join(_DAT,"world_rings.json"),encoding="utf-8"))
world_js = json.dumps(WORLD, separators=(",", ":"))
import glob as _glob
NETWORKS = {}
for _f in _glob.glob(os.path.join(_DAT,"networks","*.json")):
    _n = json.load(open(_f))
    NETWORKS[_n["slug"]] = {"city": _n.get("city"), "stations": _n.get("stations", []), "lines": _n.get("lines", [])}
networks_js = json.dumps(NETWORKS, separators=(",", ":"))

HTML = r"""<title>Metro Time Machine</title>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Semi+Condensed:wght@500;600;700&family=Public+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
/* committed night-world palette — painted explicitly so it holds on any host ground */
:root{
  --bg:#070910; --bg2:#0c0f18; --bg3:#141a28;
  --ink:#eef2f9; --ink2:#98a4b8; --ink3:#5c6880;
  --line:#182034; --border:#232c40; --border2:#33405a;
  --now:#ffc24d; --now-dim:#8a6a2a;
  --a-asia:#ef5b7a; --a-eur:#5b8def; --a-nam:#33b7a3; --a-sam:#ec8a3f;
  --a-mec:#c98bdb; --a-oce:#3fc4e6; --a-afr:#a7c94f;
  --shadow:0 10px 40px rgba(0,0,0,.5);
}
*{box-sizing:border-box}
html,body{margin:0;height:100%}
body{background:var(--bg);color:var(--ink);overflow:hidden;
  font-family:"Public Sans",system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
  -webkit-font-smoothing:antialiased;}
.mono{font-family:"IBM Plex Mono",monospace}
button{font-family:inherit;cursor:pointer}
:focus-visible{outline:2px solid var(--now);outline-offset:2px}

#stage{position:fixed;inset:0}
#map{position:absolute;inset:0;width:100%;height:100%;display:block;touch-action:none}

/* top masthead */
.top{position:absolute;top:0;left:0;right:0;padding:16px 20px;pointer-events:none;
  display:flex;justify-content:space-between;align-items:flex-start;gap:12px;z-index:6}
.brand .eye{font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--a-eur)}
.brand h1{font-family:"Barlow Semi Condensed",sans-serif;font-weight:700;letter-spacing:-.01em;
  font-size:clamp(22px,3.4vw,34px);margin:1px 0 0;line-height:1}
.hint{font-size:12.5px;color:var(--ink3);max-width:44ch;line-height:1.4;margin-top:7px}

/* lens control top-right under hint */
.lens{position:absolute;top:16px;right:20px;z-index:7;display:flex;flex-direction:column;align-items:flex-end;gap:8px;pointer-events:auto}
.seg{display:flex;background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:3px;gap:2px}
.seg button{font-family:"IBM Plex Mono",monospace;font-size:11px;letter-spacing:.03em;color:var(--ink2);
  background:none;border:0;border-radius:7px;padding:5px 9px}
.seg button[aria-pressed="true"]{background:var(--bg3);color:var(--ink)}
.legend{background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:9px 11px;font-size:11.5px;color:var(--ink2);
  display:none;max-width:210px}
.legend.on{display:block}
.legend .row{display:flex;align-items:center;gap:7px;margin:3px 0}
.legend .sw{width:11px;height:11px;border-radius:3px;flex-shrink:0}
.legend .ttl{font-family:"IBM Plex Mono",monospace;font-size:10px;letter-spacing:.09em;text-transform:uppercase;color:var(--ink3);margin-bottom:5px}

/* bottom console */
.console{position:absolute;left:0;right:0;bottom:0;z-index:6;padding:14px 20px 18px;
  background:linear-gradient(0deg,rgba(7,9,16,.94) 30%,rgba(7,9,16,0));
  display:flex;align-items:center;gap:18px;flex-wrap:wrap}
.transport{display:flex;align-items:center;gap:12px;flex-shrink:0}
.tbtn{width:52px;height:52px;border-radius:50%;background:var(--now);border:0;color:#1a1206;
  display:grid;place-items:center;box-shadow:0 4px 18px rgba(255,194,77,.3)}
.tbtn svg{width:24px;height:24px}
.taxi{height:38px;padding:0 15px;border-radius:999px;background:var(--bg2);border:1px solid var(--border2);color:var(--ink);
  font-family:"IBM Plex Mono",monospace;font-size:12px;letter-spacing:.04em;display:flex;align-items:center;gap:7px}
.taxi:hover{border-color:var(--now)}
.taxi.on{background:var(--now);color:#1a1206;border-color:var(--now)}
.zoomctl{position:absolute;right:20px;bottom:150px;z-index:8;display:flex;flex-direction:column;gap:6px;align-items:center}
.zoomctl .zlab{font-family:"IBM Plex Mono",monospace;font-size:9.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink3);margin-bottom:1px}
.zoomctl button{width:44px;height:44px;border-radius:11px;background:var(--bg2);border:1px solid var(--border2);color:var(--ink);
  font-family:"IBM Plex Mono",monospace;font-size:22px;line-height:1;display:grid;place-items:center;box-shadow:var(--shadow)}
.zoomctl button:hover{border-color:var(--now);color:var(--now)}
.zoomctl button:active{background:var(--now);color:#1a1206}
.zoomctl #zreset{font-size:16px;opacity:.4}
@media (max-width:640px){.zoomctl{bottom:172px;right:14px}}

.dialwrap{flex:1;min-width:260px}
.dialtop{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:5px}
.yearbig{font-family:"Barlow Semi Condensed",sans-serif;font-weight:700;font-size:30px;line-height:1;letter-spacing:.01em}
.yearbig .mo{font-family:"IBM Plex Mono",monospace;font-size:15px;color:var(--now);margin-left:8px;font-weight:600}
.dialmeta{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--ink3);text-align:right}
.scrub{position:relative;height:26px}
.scrub input{position:absolute;inset:0;width:100%;height:100%;margin:0;opacity:0;cursor:pointer;z-index:3}
.track{position:absolute;left:0;right:0;top:11px;height:4px;border-radius:3px;background:var(--bg3);overflow:hidden}
.trackfill{position:absolute;top:0;left:0;bottom:0;background:linear-gradient(90deg,var(--a-eur),var(--now));border-radius:3px}
.covid{position:absolute;top:9px;height:8px;width:2px;background:var(--a-asia);opacity:.7;border-radius:2px}
.covid::after{content:"2020";position:absolute;top:-15px;left:50%;transform:translateX(-50%);font-family:"IBM Plex Mono",monospace;font-size:8.5px;color:var(--a-asia);white-space:nowrap}
.knob{position:absolute;top:5px;width:16px;height:16px;border-radius:50%;background:var(--now);border:3px solid var(--bg);transform:translateX(-50%);box-shadow:0 0 10px rgba(255,194,77,.5);pointer-events:none}
.ticks{display:flex;justify-content:space-between;font-family:"IBM Plex Mono",monospace;font-size:10px;color:var(--ink3);margin-top:2px}

/* now playing card */
.now{position:absolute;left:20px;bottom:104px;z-index:7;width:334px;max-height:calc(100vh - 190px);overflow-y:auto;
  background:var(--bg2);border:1px solid var(--border);border-radius:14px;padding:15px 16px;box-shadow:var(--shadow);display:none}
.now.on{display:block}
.now .sysname{font-size:13px;color:var(--ink2);margin-top:3px;line-height:1.32}
.now .maplink{display:flex;align-items:center;justify-content:center;gap:5px;margin:13px 0 3px;padding:10px 12px;
  background:var(--now);color:#1a1206;border-radius:9px;font-weight:600;font-size:13.5px;text-decoration:none;
  box-shadow:0 3px 14px rgba(255,194,77,.22)}
.now .maplink:hover{filter:brightness(1.07)}
.now .netbtn{width:100%;margin:13px 0 0;padding:10px 12px;background:var(--bg3);border:1px solid var(--border2);
  color:var(--ink);border-radius:9px;font-weight:600;font-size:13.5px;cursor:pointer;display:none}
.now .netbtn:hover{border-color:var(--now);color:var(--now)}
#netview{position:fixed;inset:0;z-index:30;background:#06080e;display:flex;flex-direction:column}
#netview[hidden]{display:none}
.nvhead{display:flex;justify-content:space-between;align-items:flex-start;padding:16px 22px 10px;gap:14px}
.nvcity{font-family:"Barlow Semi Condensed",sans-serif;font-weight:700;font-size:26px;line-height:1}
.nvsub{font-size:12px;color:var(--ink3);margin-top:5px}
.nvright{display:flex;align-items:flex-start;gap:16px}
.nvlines{display:flex;flex-wrap:wrap;gap:4px;max-width:560px;justify-content:flex-end}
.nvlines .lc{display:flex;align-items:center;gap:5px;font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--ink2);
  background:var(--bg2);border:1px solid var(--border);border-radius:6px;padding:2px 7px}
.nvlines .lc i{width:9px;height:9px;border-radius:2px;display:inline-block}
.nvclose{background:none;border:0;color:var(--ink2);font-size:27px;line-height:1;cursor:pointer}
.nvclose:hover{color:var(--ink)}
#nvCanvas{flex:1;width:100%;display:block;cursor:grab;touch-action:none}
.nvtip{position:fixed;pointer-events:none;z-index:31;background:var(--bg3);border:1px solid var(--border2);border-radius:7px;
  padding:4px 9px;font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--ink);display:none;transform:translate(-50%,-155%);white-space:nowrap}
.nvfoot{padding:8px 22px 14px;font-size:11px;color:var(--ink3);text-align:center}
.now .linesrow{margin-top:13px}
.now .llbl{font-size:10px;letter-spacing:.09em;text-transform:uppercase;color:var(--ink3);margin-bottom:6px}
.now .lines{display:flex;gap:3px;height:15px;border-radius:5px;overflow:hidden}
.now .lines span{flex:1;min-width:6px}
.now .city{font-family:"Barlow Semi Condensed",sans-serif;font-weight:700;font-size:23px;line-height:1;display:flex;align-items:center;gap:9px}
.now .rdot{width:12px;height:12px;border-radius:50%;flex-shrink:0}
.now .loc{font-family:"IBM Plex Mono",monospace;font-size:11px;color:var(--ink3);margin-top:4px}
.now .big{font-family:"Barlow Semi Condensed",sans-serif;font-weight:700;font-size:26px;margin:11px 0 1px;line-height:1}
.now .biglab{font-size:11.5px;color:var(--ink3)}
.now .spark{height:44px;margin:11px 0 3px;position:relative}
.now .stats{display:grid;grid-template-columns:1fr 1fr;gap:7px 12px;margin-top:11px;font-size:12.5px}
.now .stats .k{color:var(--ink3);font-family:"IBM Plex Mono",monospace;font-size:10px;letter-spacing:.06em;text-transform:uppercase}
.now .stats .v{color:var(--ink);font-weight:600}
.now .chips{display:flex;gap:4px;margin-top:11px;flex-wrap:wrap}
.now .chip{width:16px;height:16px;border-radius:4px;border:1px solid rgba(255,255,255,.12)}
.now .close{position:absolute;top:11px;right:12px;background:none;border:0;color:var(--ink3);font-size:17px;line-height:1}
.now .close:hover{color:var(--ink)}

/* intro overlay */
#intro{position:fixed;inset:0;z-index:20;background:radial-gradient(120% 90% at 50% 40%,#0c1220,#05070d);
  display:grid;place-items:center;text-align:center;padding:24px}
#intro .box{max-width:560px}
#intro .eye{font-family:"IBM Plex Mono",monospace;font-size:12px;letter-spacing:.18em;text-transform:uppercase;color:var(--a-eur)}
#intro h2{font-family:"Barlow Semi Condensed",sans-serif;font-weight:700;font-size:clamp(40px,8vw,76px);margin:.14em 0 .1em;line-height:.96;letter-spacing:-.01em;text-wrap:balance}
#intro p{color:var(--ink2);font-size:clamp(15px,2.2vw,18px);line-height:1.6;max-width:52ch;margin:0 auto 26px}
#intro .enter{font-family:"IBM Plex Mono",monospace;font-size:14px;letter-spacing:.06em;color:#1a1206;background:var(--now);
  border:0;border-radius:999px;padding:13px 30px;box-shadow:0 6px 26px rgba(255,194,77,.35)}
.tip{position:absolute;pointer-events:none;z-index:8;background:var(--bg3);border:1px solid var(--border2);border-radius:8px;
  padding:5px 9px;font-family:"IBM Plex Mono",monospace;font-size:11.5px;color:var(--ink);display:none;white-space:nowrap;transform:translate(-50%,-140%)}
@media (max-width:640px){.now{width:calc(100% - 40px)} .hint{display:none} .console{gap:12px}}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>

<div id="stage">
  <canvas id="map"></canvas>
  <div class="top">
    <div class="brand"><div class="eye">World Transit Network Atlas</div><h1>Metro Time Machine</h1>
      <div class="hint">Tune the year, pick a city, hear it — the 2020 dip ripples worldwide. Zoom in (scroll / pinch) or pick a city and <em>fly to its metro</em> — real lines and stations surface right on the map.</div></div>
  </div>
  <div class="lens">
    <div class="seg" id="lensSeg" role="group" aria-label="Colour the world by">
      <button data-lens="region" aria-pressed="true">Region</button>
      <button data-lens="era" aria-pressed="false">Era</button>
      <button data-lens="auto" aria-pressed="false">Driverless</button>
      <button data-lens="own" aria-pressed="false">Ownership</button>
    </div>
    <div class="legend" id="legend"></div>
  </div>

  <div class="now" id="now">
    <button class="close" id="nowClose" aria-label="Close">&times;</button>
    <div class="city"><span class="rdot" id="nCol"></span><span id="nCity"></span></div>
    <div class="sysname" id="nSys"></div>
    <div class="loc mono" id="nLoc"></div>
    <button class="netbtn" id="nNetBtn">&#9678;&nbsp; Fly to its metro on the map</button>
    <a class="maplink" id="nMap" target="_blank" rel="noopener"><span id="nMapTxt">View the official metro map</span> &#8599;</a>
    <div class="linesrow"><div class="llbl mono" id="nLinesLbl">Line colours</div><div class="lines" id="nLines"></div></div>
    <div class="big" id="nBig"></div><div class="biglab" id="nBigL"></div>
    <canvas class="spark" id="nSpark"></canvas>
    <div class="stats" id="nStats"></div>
  </div>

  <div class="zoomctl">
    <div class="zlab">Zoom</div>
    <button id="zin" aria-label="Zoom in" title="Zoom in (scroll up, double-click, or +)">+</button>
    <button id="zout" aria-label="Zoom out" title="Zoom out (scroll down or −)">&minus;</button>
    <button id="zreset" aria-label="Reset view" title="Reset to whole world (0)">&#8862;</button>
  </div>
  <div class="console">
    <div class="transport">
      <button class="tbtn" id="play" aria-label="Play"><svg id="playIcon" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg></button>
      <button class="taxi" id="taxi" aria-pressed="false" title="Auto-tour playable cities">🚕 Taxi</button>
    </div>
    <div class="dialwrap">
      <div class="dialtop">
        <div class="yearbig"><span id="yLbl">2002</span><span class="mo" id="mLbl">JAN</span></div>
        <div class="dialmeta" id="dMeta">33 systems playing · 201 on the map</div>
      </div>
      <div class="scrub">
        <div class="track"><div class="trackfill" id="tFill"></div></div>
        <div class="covid" id="covid"></div>
        <div class="knob" id="knob"></div>
        <input type="range" id="scrub" min="0" max="293" step="1" value="0" aria-label="Year">
      </div>
      <div class="ticks"><span>2002</span><span>2008</span><span>2014</span><span>2020</span><span>2026</span></div>
    </div>
  </div>
  <div class="tip" id="tip"></div>
</div>

<div id="netview" hidden>
  <div class="nvhead">
    <div><div class="nvcity" id="nvCity"></div><div class="nvsub mono" id="nvSub"></div></div>
    <div class="nvright"><div class="nvlines" id="nvLines"></div><button class="nvclose" id="nvClose" aria-label="Close">&times;</button></div>
  </div>
  <canvas id="nvCanvas"></canvas>
  <div class="nvtip" id="nvTip"></div>
  <div class="nvfoot mono">Real line &amp; station geometry from open data · scroll to zoom, drag to pan · hover a station for details</div>
</div>

<div id="intro"><div class="box">
  <div class="eye">World Transit Network Atlas · a musical map</div>
  <h2>Metro Time Machine</h2>
  <p>Two hundred and one metro systems, placed where they are on Earth. Move the dial through the years and each city's ridership becomes a voice — pitch riding the riders. Tune one station, or hail a taxi and let it tour the world. Then watch March 2020 arrive.</p>
  <button class="enter" id="enter">▸ Enter the machine</button>
</div></div>

<script>
const D=__DATA__;
const WORLD=__WORLD__;
const NETWORKS=__NETWORKS__;
const SYS=D.systems, MON0=2002*12;
const RC={"Asia":"#ef5b7a","Europe":"#5b8def","North America":"#33b7a3","South America":"#ec8a3f",
  "Middle East & Central Asia":"#c98bdb","Oceania":"#3fc4e6","Africa":"#a7c94f"};
const MON=["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"];
const $=id=>document.getElementById(id);
const cv=$("map"),ctx=cv.getContext("2d");
let W=0,H=0,DPR=Math.min(2,window.devicePixelRatio||1);

/* --- projection fit to data bounds (simple equirectangular, aspect-preserving) --- */
let lonMin=1e9,lonMax=-1e9,latMin=1e9,latMax=-1e9;
SYS.forEach(s=>{lonMin=Math.min(lonMin,s.lon);lonMax=Math.max(lonMax,s.lon);latMin=Math.min(latMin,s.lat);latMax=Math.max(latMax,s.lat);});
const padL=6,padT=6;
function resize(){
  W=cv.clientWidth;H=cv.clientHeight;cv.width=W*DPR;cv.height=H*DPR;ctx.setTransform(DPR,0,0,DPR,0,0);
  layout();draw();
}
let PROJ={};
function layout(){
  const mL=40,mR=40,mT=86,mB=132;
  const dLon=lonMax-lonMin,dLat=latMax-latMin;
  const availW=W-mL-mR,availH=H-mT-mB;
  const sc=Math.min(availW/dLon, availH/dLat);
  const w=dLon*sc,h=dLat*sc;
  const ox=mL+(availW-w)/2, oy=mT+(availH-h)/2;
  PROJ={sc,ox,oy};
  SYS.forEach(s=>{s._bx=ox+(s.lon-lonMin)*sc; s._by=oy+(latMax-s.lat)*sc;});
  clampPan();
}
/* ridership series lookup */
SYS.forEach(s=>{ s._m={}; s._lo=1e18; s._hi=-1e18;
  if(s.series){ s.series.forEach(([ym,v])=>{const mi=(+ym.slice(0,4))*12+(+ym.slice(5,7)-1)-MON0; s._m[mi]=v; if(v<s._lo)s._lo=v; if(v>s._hi)s._hi=v;});
    s._mi0=(+s.series[0][0].slice(0,4))*12+(+s.series[0][0].slice(5,7)-1)-MON0;
    s._mi1=(+s.series[s.series.length-1][0].slice(0,4))*12+(+s.series[s.series.length-1][0].slice(5,7)-1)-MON0;
  }
  s._r=Math.max(2.2, Math.min(10, 2 + Math.sqrt((s.annual||0)/1e9)*5.5));
});
/* precompute each city's network on-map radius (max degree extent from its centre) */
SYS.forEach(s=>{ const net=NETWORKS[s.slug]; if(!net){s._netR=0;return;}
  let mr=0; const ck=(lo,la)=>{const d=Math.max(Math.abs(lo-s.lon),Math.abs(la-s.lat)); if(d>mr)mr=d;};
  (net.stations||[]).forEach(st=>ck(st.lon,st.lat));
  (net.lines||[]).forEach(l=>(l.paths||[]).forEach(p=>p.forEach(pt=>ck(pt[0],pt[1]))));
  s._netR=Math.max(0.02, mr);
});
function normAt(s,mi){ if(!s.series||s._hi<=s._lo)return null;
  let m=mi; if(m<s._mi0)m=s._mi0; if(m>s._mi1)m=s._mi1;
  let v=s._m[m]; if(v==null){ for(let k=m;k>=s._mi0;k--){if(s._m[k]!=null){v=s._m[k];break;}} }
  if(v==null)return null; return (v-s._lo)/(s._hi-s._lo);
}
function valAt(s,mi){ if(!s.series)return null; let m=mi; if(m<s._mi0)m=s._mi0; if(m>s._mi1)m=s._mi1;
  let v=s._m[m]; if(v==null){for(let k=m;k>=s._mi0;k--){if(s._m[k]!=null){v=s._m[k];break;}}} return v; }

/* --- lens colouring --- */
let lens="region";
function eraColor(y){ if(y==null)return null; const t=Math.max(0,Math.min(1,(y-1900)/125));
  // deep indigo -> bright cyan
  const a=[76,60,130],b=[90,220,235]; return `rgb(${a.map((c,i)=>Math.round(c+(b[i]-c)*t)).join(",")})`; }
function ownColor(o){ if(o==null)return null; const t=o/5; const a=[60,180,150],b=[220,90,190];
  return `rgb(${a.map((c,i)=>Math.round(c+(b[i]-c)*t)).join(",")})`; }
function nodeColor(s){
  if(lens==="region")return RC[s.region]||"#888";
  if(lens==="era")return eraColor(s.opening)||"#2b3550";
  if(lens==="auto")return s.goa==null?"#2b3550":(s.goa>=4?"#ffc24d":s.goa>=3?"#8f7bd8":"#3d4a63");
  if(lens==="own")return ownColor(s.opmodel)||"#2b3550";
  return "#888";
}
function nodeDim(s){ // true = data gap under this lens (render hollow)
  if(lens==="era")return s.opening==null;
  if(lens==="auto")return s.goa==null;
  if(lens==="own")return s.opmodel==null;
  return false;
}
const LEG={
  region:{title:"Region",items:Object.entries(RC).map(([k,v])=>[v,k])},
  era:{title:"First line opened",items:[["#4c3c82","~1900"],["#6f7fb0","1950s"],["#5ab0c8","1990s"],["#5aebeb","2020s"]]},
  auto:{title:"Grade of automation",items:[["#ffc24d","GoA4 · driverless"],["#8f7bd8","GoA3"],["#3d4a63","GoA ≤2"],["#20283a","no data"]]},
  own:{title:"Operating model",items:[["#3cb496","public authority"],["#8a86c0","concession / PPP"],["#dc5abe","private / listed"],["#20283a","no data"]]}
};
function renderLegend(){ const L=LEG[lens]; const el=$("legend");
  if(lens==="region"){el.classList.remove("on");return;} el.classList.add("on");
  el.innerHTML='<div class="ttl">'+L.title+'</div>'+L.items.map(([c,t])=>`<div class="row"><span class="sw" style="background:${c}"></span>${t}</div>`).join("");
}

/* --- draw --- */
let cur=0, hoverS=null, selS=null;
/* --- view transform (zoom + pan) --- */
let view={z:1,px:0,py:0};
const SX=bx=>bx*view.z+view.px, SY=by=>by*view.z+view.py;
function clampPan(){ if(!PROJ.sc)return; const m=90;
  const bxL=PROJ.ox, bxR=PROJ.ox+(lonMax-lonMin)*PROJ.sc, byT=PROJ.oy, byB=PROJ.oy+(latMax-latMin)*PROJ.sc;
  const pxMax=m-bxL*view.z, pxMin=(W-m)-bxR*view.z;
  const pyMax=(86+m)-byT*view.z, pyMin=(H-132-m)-byB*view.z;
  view.px = pxMin>pxMax ? (pxMin+pxMax)/2 : Math.max(pxMin,Math.min(pxMax,view.px));
  view.py = pyMin>pyMax ? (pyMin+pyMax)/2 : Math.max(pyMin,Math.min(pyMax,view.py));
}
function zoomAt(mx,my,nz){ nz=Math.max(1,Math.min(600,nz));
  view.px=mx-(mx-view.px)*(nz/view.z); view.py=my-(my-view.py)*(nz/view.z); view.z=nz;
  if(view.z<=1.001){view.z=1;view.px=0;view.py=0;} else clampPan();
  $("zreset").style.opacity=view.z>1?"1":".4";
}
let _tw=null;
function tweenView(tz,tpx,tpy,ms){ const t0=performance.now(), z0=view.z,px0=view.px,py0=view.py;
  if(_tw)cancelAnimationFrame(_tw);
  (function step(now){ let k=Math.min(1,(now-t0)/ms); const e=k<.5?2*k*k:1-Math.pow(-2*k+2,2)/2;
    view.z=z0+(tz-z0)*e; view.px=px0+(tpx-px0)*e; view.py=py0+(tpy-py0)*e;
    $("zreset").style.opacity=view.z>1?"1":".4"; draw();
    if(k<1){_tw=requestAnimationFrame(step);} else {_tw=null; if(view.z>1.001)clampPan(); draw();} })(t0);
}
function flyToNetwork(slug){ const s=SYS.find(x=>x.slug===slug); if(!s||!s._netR)return;
  const availW=W-80, availH=H-86-132;
  const tz=Math.max(1,Math.min(600, 0.60*Math.min(availW,availH)/(s._netR*2*PROJ.sc)));
  const cx=W/2, cy=(86+H-132)/2;
  tweenView(tz, cx-s._bx*tz, cy-s._by*tz, 750);
}
function draw(){
  ctx.clearRect(0,0,W,H);
  SYS.forEach(s=>{s._x=SX(s._bx);s._y=SY(s._by);});
  const bx=lon=>PROJ.ox+(lon-lonMin)*PROJ.sc, by=lat=>PROJ.oy+(latMax-lat)*PROJ.sc;
  // land base layer (real coastlines + country borders)
  ctx.fillStyle="#0f1626"; ctx.strokeStyle="#27324c"; ctx.lineWidth=1; ctx.lineJoin="round";
  for(const ring of WORLD){ ctx.beginPath();
    for(let i=0;i<ring.length;i++){ const x=SX(bx(ring[i][0])), y=SY(by(ring[i][1])); i?ctx.lineTo(x,y):ctx.moveTo(x,y); }
    ctx.closePath(); ctx.fill(); ctx.stroke(); }
  // graticule
  ctx.strokeStyle="rgba(90,110,150,.07)";ctx.lineWidth=1;ctx.beginPath();
  for(let lon=Math.ceil(lonMin/20)*20; lon<=lonMax; lon+=20){const x=SX(bx(lon));ctx.moveTo(x,SY(by(latMax))-4);ctx.lineTo(x,SY(by(latMin))+4);}
  for(let lat=Math.ceil(latMin/15)*15; lat<=latMax; lat+=15){const y=SY(by(lat));ctx.moveTo(SX(bx(lonMin))-4,y);ctx.lineTo(SX(bx(lonMax))+4,y);}
  ctx.stroke();
  // equator emphasis
  if(latMin<0&&latMax>0){const y=SY(by(0));ctx.strokeStyle="#1c2740";ctx.beginPath();ctx.moveTo(SX(bx(lonMin)),y);ctx.lineTo(SX(bx(lonMax)),y);ctx.stroke();}

  // --- real metro networks, drawn in geographic place as a city grows on screen ---
  ctx.lineJoin="round";ctx.lineCap="round";
  for(const s of SYS){
    const net=NETWORKS[s.slug]; if(!net||!s._netR)continue;
    if(s._x<-320||s._x>W+320||s._y<-320||s._y>H+320)continue;
    const span=s._netR*2*PROJ.sc*view.z;            // network's on-screen px extent
    if(span<55)continue;
    const na=Math.max(0,Math.min(1,(span-55)/120));  // fade in over 55..175px
    const lw=Math.max(1.1,Math.min(6.5,span*0.011));
    for(const ln of (net.lines||[])){ ctx.strokeStyle=ln.color||"#8aa6c8"; ctx.lineWidth=lw; ctx.globalAlpha=na*0.95;
      for(const path of ln.paths){ if(path.length<2)continue; ctx.beginPath();
        for(let i=0;i<path.length;i++){ const X=SX(bx(path[i][0])),Y=SY(by(path[i][1])); i?ctx.lineTo(X,Y):ctx.moveTo(X,Y); } ctx.stroke(); } }
    const sr=Math.max(0.9,Math.min(4.2,span*0.0058));
    if(sr>1){ ctx.fillStyle="#e7edf6"; ctx.strokeStyle="rgba(9,13,21,.85)"; ctx.lineWidth=Math.max(.5,sr*0.4);
      for(const stn of (net.stations||[])){ const X=SX(bx(stn.lon)),Y=SY(by(stn.lat));
        if(X<-15||X>W+15||Y<-15||Y>H+15)continue; ctx.globalAlpha=na; ctx.beginPath();ctx.arc(X,Y,sr,0,7);ctx.fill(); if(sr>1.7)ctx.stroke(); } }
    ctx.globalAlpha=1;
  }

  const mi=Math.floor(cur);
  // nodes: draw dim first, bright playable on top
  const order=[...SYS].sort((a,b)=>(a.series?1:0)-(b.series?1:0));
  order.forEach(s=>{
    const col=nodeColor(s), gap=nodeDim(s);
    const n=normAt(s,mi);
    let r=s._r, glow=0, alpha=gap?0.28:0.9;
    if(s.series){ const nn=n==null?0.12:n; r=s._r*(0.72+0.6*nn); glow=nn; alpha=1; }
    ctx.beginPath();ctx.arc(s._x,s._y,r,0,7);
    if(gap){ ctx.strokeStyle=col;ctx.globalAlpha=alpha;ctx.lineWidth=1;ctx.stroke();ctx.globalAlpha=1; }
    else{
      if(s.series&&glow>0.02){ ctx.shadowColor=col;ctx.shadowBlur=6+14*glow; }
      ctx.fillStyle=col;ctx.globalAlpha=alpha;ctx.fill();ctx.shadowBlur=0;ctx.globalAlpha=1;
    }
    if(s===selS){ ctx.beginPath();ctx.arc(s._x,s._y,r+5,0,7);ctx.strokeStyle="#ffc24d";ctx.lineWidth=2;ctx.stroke();
      ctx.beginPath();ctx.arc(s._x,s._y,Math.max(1.5,r*0.42),0,7);ctx.fillStyle="#fff";ctx.fill(); }
    if(s===hoverS&&s!==selS){ ctx.beginPath();ctx.arc(s._x,s._y,r+4,0,7);ctx.strokeStyle="rgba(255,255,255,.6)";ctx.lineWidth=1.5;ctx.stroke(); }
  });
  // city labels once zoomed in
  if(view.z>3){ ctx.font='600 10.5px "IBM Plex Mono",monospace';ctx.textAlign="left";ctx.textBaseline="middle";
    order.forEach(s=>{ if(s._x>-30&&s._x<W+30&&s._y>60&&s._y<H-120){ ctx.fillStyle=s===selS?"#ffc24d":"rgba(228,236,247,.66)";
      ctx.fillText(s.city, s._x+s._r+4, s._y); } }); }
}

/* --- audio: an immersive world ensemble + a lead voice for the selected city --- */
let AC=null,master=null,bed=null;
const PENT=[0,2,4,7,9,12,14,16,19,21,24];
const OSC={"Asia":"triangle","Europe":"sawtooth","North America":"square","South America":"sine",
  "Middle East & Central Asia":"triangle","Oceania":"sine","Africa":"sawtooth"};
let voice=null, ens=[], ensOn=0;
function _ir(sec,decay){ const n=Math.floor(AC.sampleRate*sec),b=AC.createBuffer(2,n,AC.sampleRate);
  for(let c=0;c<2;c++){const d=b.getChannelData(c);for(let i=0;i<n;i++)d[i]=(Math.random()*2-1)*Math.pow(1-i/n,decay);} return b; }
function initAudio(){ if(AC)return; AC=new (window.AudioContext||window.webkitAudioContext)();
  master=AC.createGain(); master.gain.value=0.6;
  bed=AC.createGain(); bed.gain.value=0;                          // the world swells in on play, fades on pause
  const lp=AC.createBiquadFilter(); lp.type="lowpass"; lp.frequency.value=2800; lp.Q.value=0.5;
  const comp=AC.createDynamicsCompressor(); comp.threshold.value=-22; comp.knee.value=24; comp.ratio.value=6;
  const conv=AC.createConvolver(); conv.buffer=_ir(2.8,2.4);      // synthetic reverb impulse for space
  const wet=AC.createGain(); wet.gain.value=0.34; const dry=AC.createGain(); dry.gain.value=0.92;
  bed.connect(master); master.connect(lp); lp.connect(comp);
  comp.connect(dry); dry.connect(AC.destination);
  comp.connect(conv); conv.connect(wet); wet.connect(AC.destination);
  [55,82.41].forEach((f,i)=>{ const o=AC.createOscillator(),g=AC.createGain();  // low drone floor
    o.type="sine"; o.frequency.value=f; o.detune.value=i?7:-7; g.gain.value=0.045; o.connect(g); g.connect(bed); o.start(); });
  buildEnsemble();
}
function panFor(s){ return Math.max(-1,Math.min(1,(s.lon)/165)); }
function buildEnsemble(){   // the 28 busiest cities become a persistent, panned, year-reactive chord
  const set=[...SYS].filter(s=>s.series).sort((a,b)=>(b.annual||0)-(a.annual||0)).slice(0,28);
  ens=set.map(s=>{ const o=AC.createOscillator(),g=AC.createGain(),p=AC.createStereoPanner();
    o.type=OSC[s.region]||"triangle"; p.pan.value=panFor(s); g.gain.value=0;
    o.connect(g); g.connect(p); p.connect(bed); o.start();
    return {o,g,sys:s,oct:s.annual>1.2e9?0:s.annual>4e8?1:2}; });
}
function updEnsemble(){
  if(!AC||!ens.length)return; const t=AC.currentTime;
  bed.gain.setTargetAtTime(ensOn*0.5, t, 0.3);
  for(const v of ens){ const s=v.sys;
    if(selS&&s.slug===selS.slug){ v.g.gain.setTargetAtTime(0,t,0.12); continue; }  // the lead voice covers it
    const n=normAt(s,Math.floor(cur));
    if(n==null){ v.g.gain.setTargetAtTime(0,t,0.25); continue; }
    const idx=Math.round(n*(PENT.length-1)); const f=110*Math.pow(2,(PENT[idx]+v.oct*12)/12);
    v.o.frequency.setTargetAtTime(f,t,0.09);
    v.g.gain.setTargetAtTime(0.02+0.05*n, t, 0.14);
  }
}
function tune(s){
  if(!AC)return;
  if(voice){voice.osc.stop(AC.currentTime+0.05);voice=null;}
  const o=AC.createOscillator(),g=AC.createGain(),p=AC.createStereoPanner();
  o.type=OSC[s.region]||"triangle"; p.pan.value=panFor(s);
  g.gain.value=0; o.connect(g);g.connect(p);p.connect(master); o.start();
  voice={osc:o,gain:g,sys:s,octave:s.annual>1.2e9?0:s.annual>4e8?1:2};
  if(!s.series){ // annual-only: a single chime pitched by opening year
    const t=s.opening?Math.max(0,Math.min(1,(s.opening-1900)/125)):0.5;
    const idx=Math.round(t*(PENT.length-1)); const f=110*Math.pow(2,(PENT[idx]+voice.octave*12)/12);
    o.frequency.value=f; g.gain.setValueAtTime(0,AC.currentTime); g.gain.linearRampToValueAtTime(0.34,AC.currentTime+0.02);
    g.gain.exponentialRampToValueAtTime(0.001,AC.currentTime+1.8);
  }
}
function updVoice(){   // the selected city sings brighter, over the world bed
  if(!voice||!AC)return; const s=voice.sys; if(!s.series)return;
  const n=normAt(s,Math.floor(cur)); if(n==null){voice.gain.gain.setTargetAtTime(0,AC.currentTime,0.05);return;}
  const idx=Math.round(n*(PENT.length-1)); const f=110*Math.pow(2,(PENT[idx]+voice.octave*12)/12);
  voice.osc.frequency.setTargetAtTime(f,AC.currentTime,0.04);
  voice.gain.gain.setTargetAtTime(0.2+0.18*n,AC.currentTime,0.05);
}

/* --- transport --- */
let playing=false, taxi=false, last=0, taxiT=0;
const SPEED=8; // months / sec
function setYear(){ const mi=MON0+Math.floor(cur); $("yLbl").textContent=Math.floor(mi/12); $("mLbl").textContent=MON[mi%12];
  const f=cur/293; $("tFill").style.width=(f*100)+"%"; $("knob").style.left=(f*100)+"%"; $("scrub").value=Math.floor(cur);
}
function loop(t){
  const dt=(t-last)/1000; last=t;
  if(playing){ cur+=dt*SPEED; if(cur>293){cur=293;playing=false;setPlay();}
    setYear(); }
  if(taxi){ taxiT+=dt; if(taxiT>4.2){ taxiT=0; hopTaxi(); } }
  ensOn = (playing||taxi) ? Math.min(1,ensOn+dt*0.8) : Math.max(0,ensOn-dt*0.7);
  updVoice(); updEnsemble();
  draw();
  if(selS) drawSpark();
  requestAnimationFrame(loop);
}
function setPlay(){ $("playIcon").innerHTML=playing?'<path d="M6 5h4v14H6zM14 5h4v14h-4z"/>':'<path d="M8 5v14l11-7z"/>'; }
$("play").onclick=()=>{ initAudio();AC&&AC.resume(); playing=!playing; if(playing&&cur>=293)cur=0; setPlay(); };

/* taxi */
const playable=SYS.filter(s=>s.series);
function taxiSet(){ // respect lens filter (e.g. driverless only) when one narrows the set
  if(lens==="auto")return playable.filter(s=>s.goa!=null); return playable; }
function hopTaxi(){ const set=taxiSet(); const s=set[Math.floor(Math.abs(Math.sin(cur*12.9898)*43758.5)%set.length)]||playable[0]; select(s); }
$("taxi").onclick=()=>{ initAudio();AC&&AC.resume(); taxi=!taxi; $("taxi").classList.toggle("on",taxi); $("taxi").setAttribute("aria-pressed",taxi);
  if(taxi){ if(!playing){playing=true;setPlay();} taxiT=5; } };

/* selection + now playing */
function fmt(n){ if(n==null)return "—"; n=+n; return n>=1e9?(n/1e9).toFixed(2)+"B":n>=1e6?(n/1e6).toFixed(0)+"M":n>=1e3?(n/1e3).toFixed(0)+"K":n; }
function select(s){ selS=s; initAudio(); AC&&AC.resume(); tune(s); renderNow(); }
function renderNow(){ const s=selS; if(!s){$("now").classList.remove("on");return;} $("now").classList.add("on");
  $("now").scrollTop=0;
  $("nCol").style.background=RC[s.region]||"#888";
  $("nCity").textContent=s.city; $("nSys").textContent=s.system||"";
  $("nLoc").textContent=`${s.country} · ${s.lat.toFixed(1)}, ${s.lon.toFixed(1)} · ${s.region}`;
  const mp=$("nMap");
  if(s.map_url){ mp.style.display="flex"; mp.href=s.map_url;
    $("nMapTxt").textContent = s.src==="community" ? "View the metro map (community)" : "View the official metro map"; }
  else mp.style.display="none";
  const nb=$("nNetBtn");
  if(NETWORKS[s.slug]){ nb.style.display="block"; nb.onclick=()=>flyToNetwork(s.slug); } else nb.style.display="none";
  const pal=s.pal||[];
  $("nLinesLbl").style.display=pal.length?"block":"none";
  $("nLines").style.display=pal.length?"flex":"none";
  $("nLines").innerHTML=pal.map(h=>`<span style="background:${h}" title="${h}"></span>`).join("");
  const v=valAt(s,Math.floor(cur));
  if(s.series){ $("nBig").textContent=fmt(v)+" rides"; $("nBigL").textContent="this month ("+ $("yLbl").textContent+" "+$("mLbl").textContent+")"; $("nSpark").style.display="block"; }
  else{ $("nBig").textContent=fmt(s.annual); $("nBigL").textContent="annual — no monthly series (single tone by age)"; $("nSpark").style.display="none"; }
  const own=s.own?s.own.split("(")[0].trim():null;
  const st=[["Opened",s.opening||"—"],["Automation",s.goa==null?"—":"GoA "+s.goa],
    ["Ownership",own||"—"],["Farebox",s.farebox==null?"—":s.farebox+"%"],
    ["Mode",s.mode],["Annual",fmt(s.annual)]];
  $("nStats").innerHTML=st.map(([k,v])=>`<div><div class="k">${k}</div><div class="v">${v}</div></div>`).join("");
}
$("nowClose").onclick=()=>{ selS=null;$("now").classList.remove("on"); if(voice){voice.osc.stop(AC.currentTime+0.05);voice=null;} };
function drawSpark(){ const s=selS; if(!s||!s.series)return; const c=$("nSpark"),x=c.getContext("2d");
  const w=c.clientWidth,h=c.clientHeight; if(c.width!==w*DPR){c.width=w*DPR;c.height=h*DPR;x.setTransform(DPR,0,0,DPR,0,0);}
  x.clearRect(0,0,w,h);
  const a=s._mi0,b=s._mi1; x.beginPath();
  for(let m=a;m<=b;m++){ const v=valAt(s,m); const nx=(m-a)/(b-a)*w; const ny=h-((v-s._lo)/(s._hi-s._lo))*(h-6)-3; m===a?x.moveTo(nx,ny):x.lineTo(nx,ny); }
  x.strokeStyle=RC[s.region]||"#888";x.lineWidth=1.6;x.stroke();
  const mi=Math.min(b,Math.max(a,Math.floor(cur))); const px=(mi-a)/(b-a)*w;
  x.strokeStyle="#ffc24d";x.lineWidth=1.5;x.beginPath();x.moveTo(px,0);x.lineTo(px,h);x.stroke();
}

/* interaction: hover + click hit-testing */
function pick(mx,my){ let best=null,bd=1e9; for(const s of SYS){ const dx=s._x-mx,dy=s._y-my,d=dx*dx+dy*dy; const rr=(s._r+7)*(s._r+7); if(d<rr&&d<bd){bd=d;best=s;} } return best; }
function relPos(pt){const r=cv.getBoundingClientRect();return [pt.clientX-r.left,pt.clientY-r.top];}
function showTip(s){ const tip=$("tip");
  if(s){ tip.style.display="block";tip.style.left=s._x+"px";tip.style.top=s._y+"px";
    tip.textContent=s.city+(s.series?" · "+fmt(valAt(s,Math.floor(cur))):" · "+fmt(s.annual)); }
  else tip.style.display="none"; }
function doSelect(s){ if(s){ taxi=false;$("taxi").classList.remove("on");$("taxi").setAttribute("aria-pressed","false"); select(s); } }
let drag=null, pinch=null;
cv.addEventListener("mousedown",e=>{ const [x,y]=relPos(e); drag={x,y,px:view.px,py:view.py,moved:false}; });
window.addEventListener("mousemove",e=>{ const [x,y]=relPos(e);
  if(drag){ const dx=x-drag.x,dy=y-drag.y; if(Math.abs(dx)+Math.abs(dy)>3)drag.moved=true;
    if(drag.moved){ if(view.z>1){view.px=drag.px+dx;view.py=drag.py+dy;clampPan();cv.style.cursor="grabbing";} showTip(null);hoverS=null; return; } }
  hoverS=pick(x,y); showTip(hoverS); cv.style.cursor=hoverS?"pointer":(view.z>1?"grab":"default"); });
window.addEventListener("mouseup",e=>{ if(drag&&!drag.moved){ const [x,y]=relPos(e); doSelect(pick(x,y)); } drag=null; });
cv.addEventListener("mouseleave",()=>{hoverS=null;showTip(null);});
window.addEventListener("wheel",e=>{ e.preventDefault(); const [x,y]=relPos(e); zoomAt(x,y,view.z*Math.exp(-e.deltaY*0.0024)); },{passive:false});
cv.addEventListener("dblclick",e=>{ const [x,y]=relPos(e); const s=pick(x,y); if(s&&NETWORKS[s.slug]&&s._netR){flyToNetwork(s.slug);} else zoomAt(x,y,view.z*2.2); });
window.addEventListener("keydown",e=>{ if(e.target&&e.target.tagName==="INPUT")return; if(!$("netview").hidden)return; const cx=W/2,cy=(86+H-132)/2;
  if(e.key==="+"||e.key==="="){zoomAt(cx,cy,view.z*1.5);}
  else if(e.key==="-"||e.key==="_"){zoomAt(cx,cy,view.z/1.5);}
  else if(e.key==="0"){view={z:1,px:0,py:0};$("zreset").style.opacity=".4";} });
// touch: 1-finger pan, 2-finger pinch, tap to select
function pinchInfo(e){const [x1,y1]=relPos(e.touches[0]),[x2,y2]=relPos(e.touches[1]);return {d:Math.hypot(x2-x1,y2-y1),cx:(x1+x2)/2,cy:(y1+y2)/2};}
cv.addEventListener("touchstart",e=>{ if(e.touches.length===1){const [x,y]=relPos(e.touches[0]);drag={x,y,px:view.px,py:view.py,moved:false};pinch=null;}
  else if(e.touches.length===2){drag=null;pinch=pinchInfo(e);} },{passive:false});
cv.addEventListener("touchmove",e=>{ e.preventDefault();
  if(e.touches.length===2&&pinch){ const p=pinchInfo(e); zoomAt(p.cx,p.cy,view.z*(p.d/pinch.d)); pinch=p; }
  else if(e.touches.length===1&&drag){ const [x,y]=relPos(e.touches[0]); const dx=x-drag.x,dy=y-drag.y; if(Math.abs(dx)+Math.abs(dy)>3)drag.moved=true;
    if(drag.moved&&view.z>1){view.px=drag.px+dx;view.py=drag.py+dy;clampPan();} } },{passive:false});
cv.addEventListener("touchend",e=>{ if(drag&&!drag.moved&&e.changedTouches.length){ const [x,y]=relPos(e.changedTouches[0]); doSelect(pick(x,y)); } drag=null;pinch=null; });
// zoom buttons
$("zin").onclick=()=>zoomAt(W/2,(86+H-132)/2,view.z*1.9);
$("zout").onclick=()=>zoomAt(W/2,(86+H-132)/2,view.z/1.9);
$("zreset").onclick=()=>{view={z:1,px:0,py:0};$("zreset").style.opacity=".4";};

/* scrub */
$("scrub").addEventListener("input",e=>{ cur=+e.target.value; setYear(); if(voice)updVoice(); });

/* lens */
document.querySelectorAll("#lensSeg button").forEach(b=>b.onclick=()=>{
  document.querySelectorAll("#lensSeg button").forEach(x=>x.setAttribute("aria-pressed",x===b?"true":"false"));
  lens=b.dataset.lens; renderLegend(); draw();
});

/* ---- inline network view (real line + station geometry) ---- */
const nv={cv:$("nvCanvas"),z:1,px:0,py:0,W:0,H:0,proj:null,net:null,drag:null,hover:null};
nv.ctx=nv.cv.getContext("2d");
function nvFit(){ const net=nv.net; if(!net||!net.stations.length)return; let lo1=1e9,lo2=-1e9,la1=1e9,la2=-1e9;
  net.stations.forEach(s=>{lo1=Math.min(lo1,s.lon);lo2=Math.max(lo2,s.lon);la1=Math.min(la1,s.lat);la2=Math.max(la2,s.lat);});
  const mX=70,mY=46,dLon=(lo2-lo1)||1,dLat=(la2-la1)||1;
  const sc=Math.min((nv.W-2*mX)/dLon,(nv.H-2*mY)/dLat);
  nv.proj={lo1,la2,sc,ox:mX+((nv.W-2*mX)-dLon*sc)/2,oy:mY+((nv.H-2*mY)-dLat*sc)/2}; }
function nvResize(){ nv.W=nv.cv.clientWidth;nv.H=nv.cv.clientHeight;nv.cv.width=nv.W*DPR;nv.cv.height=nv.H*DPR;nv.ctx.setTransform(DPR,0,0,DPR,0,0); nvFit(); nvDraw(); }
function NPX(lon){return (nv.proj.ox+(lon-nv.proj.lo1)*nv.proj.sc)*nv.z+nv.px;}
function NPY(lat){return (nv.proj.oy+(nv.proj.la2-lat)*nv.proj.sc)*nv.z+nv.py;}
function nvDraw(){ const c=nv.ctx; if(!nv.net||!nv.proj)return; c.clearRect(0,0,nv.W,nv.H);
  nv.net.lines.forEach(ln=>{ c.strokeStyle=ln.color||"#8aa"; c.lineWidth=Math.max(1.5,2.4*Math.min(2.2,nv.z)); c.lineJoin="round"; c.lineCap="round";
    (ln.paths||[]).forEach(path=>{ c.beginPath(); for(let i=0;i<path.length;i++){const x=NPX(path[i][0]),y=NPY(path[i][1]); i?c.lineTo(x,y):c.moveTo(x,y);} c.stroke(); }); });
  const mr=nv.maxR||1, weighted=mr>1;
  nv.net.stations.forEach(s=>{ const x=NPX(s.lon),y=NPY(s.lat),hov=s===nv.hover; let r,col;
    if(weighted){ const norm=s.riders?Math.sqrt(s.riders/mr):0, t=Math.max(0,Math.min(1,norm));
      r=(hov?2.6:0)+1.9+6.6*norm;
      col=hov?"#ffc24d":`rgb(${Math.round(96+150*t)},${Math.round(112+148*t)},${Math.round(132+128*t)})`;
      if(s.riders&&norm>0.45){c.shadowColor=col;c.shadowBlur=5+13*norm;} }
    else { r=hov?5:3.1; col=hov?"#ffc24d":"rgba(228,238,250,.92)"; }
    c.beginPath();c.arc(x,y,r,0,7);c.fillStyle=col;c.fill();c.shadowBlur=0;
    c.lineWidth=1;c.strokeStyle="rgba(11,14,22,.85)";c.stroke(); }); }
function nvPick(mx,my){ let best=null,bd=1e9; for(const s of nv.net.stations){const dx=NPX(s.lon)-mx,dy=NPY(s.lat)-my,d=dx*dx+dy*dy; if(d<81&&d<bd){bd=d;best=s;}} return best; }
function openNetwork(slug){ const net=NETWORKS[slug]; if(!net)return; nv.net=net; nv.z=1;nv.px=0;nv.py=0;nv.hover=null;
  nv.maxR=Math.max(1,...net.stations.map(s=>s.riders||0));
  const wtd=net.stations.some(s=>s.riders);
  $("nvCity").textContent=net.city; $("nvSub").textContent=net.stations.length+" stations · "+(net.lines.length?net.lines.length+" lines":"stations only")+(wtd?" · dot size = annual ridership":"");
  $("nvLines").innerHTML=net.lines.map(l=>`<span class="lc"><i style="background:${l.color}"></i>${l.route}</span>`).join("");
  $("netview").hidden=false; nvResize(); }
function nvClose(){ $("netview").hidden=true; nv.net=null; $("nvTip").style.display="none"; }
$("nvClose").onclick=nvClose;
$("nNetBtn"); // ensure element referenced
nv.cv.addEventListener("wheel",e=>{ e.preventDefault(); e.stopPropagation(); const r=nv.cv.getBoundingClientRect(),mx=e.clientX-r.left,my=e.clientY-r.top;
  const nz=Math.max(1,Math.min(32,nv.z*Math.exp(-e.deltaY*0.0016))); nv.px=mx-(mx-nv.px)*(nz/nv.z);nv.py=my-(my-nv.py)*(nz/nv.z);nv.z=nz; if(nv.z<=1){nv.z=1;nv.px=0;nv.py=0;} nvDraw(); },{passive:false});
nv.cv.addEventListener("mousedown",e=>{ const r=nv.cv.getBoundingClientRect(); nv.drag={x:e.clientX-r.left,y:e.clientY-r.top,px:nv.px,py:nv.py,moved:false}; });
window.addEventListener("mousemove",e=>{ if(!nv.net||$("netview").hidden)return; const r=nv.cv.getBoundingClientRect(),mx=e.clientX-r.left,my=e.clientY-r.top;
  if(nv.drag){ const dx=mx-nv.drag.x,dy=my-nv.drag.y; if(Math.abs(dx)+Math.abs(dy)>3)nv.drag.moved=true;
    if(nv.drag.moved){ nv.px=nv.drag.px+dx;nv.py=nv.drag.py+dy;$("nvTip").style.display="none";nvDraw();return; } }
  const h=nvPick(mx,my); if(h!==nv.hover){nv.hover=h;nvDraw();} const tip=$("nvTip");
  if(h){ tip.style.display="block";tip.style.left=(r.left+NPX(h.lon))+"px";tip.style.top=(r.top+NPY(h.lat))+"px";tip.textContent=h.name+(h.riders?"  ·  "+fmt(h.riders)+"/yr":"");nv.cv.style.cursor="pointer"; }
  else{ tip.style.display="none";nv.cv.style.cursor=nv.z>1?"grab":"default"; } });
window.addEventListener("mouseup",()=>{ nv.drag=null; });
document.addEventListener("keydown",e=>{ if(e.key==="Escape"&&!$("netview").hidden)nvClose(); });

/* intro / start */
$("enter").onclick=()=>{ initAudio(); AC&&AC.resume(); $("intro").style.display="none";
  if(cur>=293)cur=0; playing=true; setPlay(); };   // the world starts singing + scrubbing on entry
window.addEventListener("resize",()=>{ resize(); if(!$("netview").hidden)nvResize(); });
resize(); setYear(); renderLegend(); last=performance.now(); requestAnimationFrame(loop);
</script>
"""
open(os.path.join(_ROOT,"index.html"), "w", encoding="utf-8").write(HTML.replace("__DATA__", data_js).replace("__WORLD__", world_js).replace("__NETWORKS__", networks_js))
print("wrote index.html from", len(NETWORKS), "networks")
