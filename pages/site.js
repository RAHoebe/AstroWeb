const $=id=>document.getElementById(id);
function selectButtons(host,options,choose,initial=0){
  const buttons=options.map((label,index)=>{
    const button=document.createElement('button');button.type='button';button.textContent=label;
    button.onclick=()=>{buttons.forEach((b,i)=>b.setAttribute('aria-pressed',String(index===i)));choose(index);};
    host.append(button);return button;
  });buttons[initial].click();
}
const groups=['Capture films','Journeys','Maps','Google TV'];
selectButtons($('groups'),groups,index=>{
  const list=films.filter(f=>f[1]===groups[index]);$('playlist').replaceChildren();
  const buttons=list.map((f,i)=>{
    const b=document.createElement('button');b.type='button';
    const im=new Image();im.src='media/'+f[0]+'-poster.webp';im.alt='';im.loading='lazy';
    const txt=document.createElement('span'),title=document.createElement('strong'),meta=document.createElement('small');
    title.textContent=f[2];meta.textContent=f[3];txt.append(title,meta);const arrow=document.createElement('span');arrow.className='arrow';arrow.textContent='›';
    b.append(im,txt,arrow);$('playlist').append(b);
    b.onclick=()=>{buttons.forEach((item,j)=>item.setAttribute('aria-pressed',String(i===j)));
      const p=$('player');p.pause();p.poster=im.src;p.src='media/'+f[0]+'.mp4';p.load();
      $('film-type').textContent=f[3];$('film-title').textContent=f[2];$('film-description').textContent=f[4];
      $('film-credit').textContent=f[5];$('film-download').href=p.src;
    };return b;
  });buttons[0].click();
});
const screens=[
 ['TV viewer','tv-viewer','All available actions fit one row; rotate and fullscreen are the two icons at the far right.'],
 ['TV Explore','tv-explore','Explore stays with the open capture: its capture night and tonight, or the named features within that photograph.'],
 ['TV viewing modes','tv-viewing-modes','Only Evening programme and Photo frame remain. Both start at a random capture, without a picker.'],
 ['TV light journey','tv-light-journey','The animation has its own space above the remote instructions and source credit.'],
 ['Stars in 3D','viewer-space','Actual star crops linked to Gaia DR3, unfolded into a distance diagram with a logarithmic depth axis.'],
 ['Light journey','viewer-cosmic','A light pulse travels from the object to Earth; your own photo appears at arrival.'],
 ['Sky mosaic','viewer-mosaic','Overlapping registered captures form a visual mosaic, with every contributing capture date visible.'],
 ['Solar comparison','viewer-solar','Sun-only comparison with dated SDO imagery and SunPy coordinates.'],
 ['Capture calendar','calendar-month','The collection-wide calendar shows capture days, portrait previews and darkness windows.'],
 ['TV calendar day','calendar-tv-day','Remote control selects a photo on the capture-day timeline. OK opens that exact capture.'],
 ['Google TV','tv-gallery','Five portrait posters share one row. The title, date and object summary sit above them.'],
 ['Web gallery','web-gallery','The web collection adapts to the width of the browser. Hover or focus a poster for a film preview.'],
 ['Studio','studio','Position the zoom frames on the original capture, compare rendered versions and choose a gallery film.'],
 ['Object discovery','discovery','Explore catalogued objects in the original image and use a selected object as a Studio zoom point.'],
 ['TV maps','tv-maps','Open a map with the remote. The available choices follow the selected object.'],
 ['TV archive journey','tv-hubble','A fullscreen Hubble journey maintains the destination image’s orientation.']
];
selectButtons($('screen-tabs'),screens.map(s=>s[0]),i=>{const s=screens[i];$('screen-img').src='media/'+s[1]+'.webp';$('screen-img').alt=s[2];$('screen-caption').textContent=s[2];});
// Download links in the installation section identify the supported releases.
const web=document.querySelector('#downloads [data-product="web"]').href;
const tvRelease=document.querySelector('#downloads [data-product="tv"]').href;
const tvVersion=tvRelease.split('/').pop().replace(/^tv-v/,'');
const tv=tvRelease.replace('/releases/tag/','/releases/download/')+'/';
const guides=[
 ['Local network','Keep it inside your home',`<p>Put the computer or NAS and Google TV on the same trusted LAN. The server stores the originals, database and films. The remote plays the collection directly over Wi-Fi or Ethernet.</p><ol><li>Download the <a href="${web}">web release</a>. On the server, put <code>ASTROWEB_LAN_IP=192.168.1.50</code> in a local <code>.env</code> file, substituting your actual private address. Create <code>data/</code> with write access for UID/GID 10001.</li><li>Build the server, create the Studio password and start it:</li></ol><pre>docker compose -f compose.lan.yaml build
docker compose -f compose.lan.yaml run --rm astroweb python -m astroweb admin
docker compose -f compose.lan.yaml up -d</pre><p>Open <code>http://192.168.1.50:8090</code> in a browser on the LAN. For a different address, add a local DNS record named <code>astroweb.home.arpa</code> on your router pointing to that address. On Google TV, install the <a href="${tv}AstroWeb-TV-LAN-${tvVersion}.apk">LAN APK</a> and enter <code>http://astroweb.home.arpa:8090</code> or the example IP. No reverse proxy, public domain, port forwarding or Google Assistant is needed. HTTP assumes a trusted home network.</p><p><strong>Offline operation.</strong> The LAN file defaults to <code>ASTROWEB_OFFLINE=1</code>. Local uploads, rendering and cached media work. New survey tiles, Gaia matches, archive and mission imagery require prior downloads. To prepare them online, set the variable to <code>0</code>, recreate the container, open the desired journeys, then switch back to <code>1</code> and recreate it again. Download software and dependencies before disconnecting. This setting controls AstroWeb’s external HTTP requests; Google TV system services have their own network settings.</p>`],
 ['Computer','Run it on a PC',`<p>Download the <a href="${web}">source archive</a> and extract it. Install Python 3.11–3.13 and FFmpeg with libx264. The Windows starter creates the virtual environment and installs the listed requirements.</p><ol><li>On Windows run <code>Start-AstroWeb.cmd</code>. On macOS or Linux use the commands below.</li><li>Open <code>http://127.0.0.1:8090/admin</code> on the same computer to create your first Studio password of at least 11 characters.</li><li>Upload a capture, render a film, then open the gallery.</li></ol><pre>python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m astroweb serve</pre><p>Loopback is local to the PC. Use the Local network setup to share the collection with another device.</p>`],
 ['NAS','Run it on a NAS',`<p>Use a NAS with Docker Compose or Synology Container Manager. Keep the <code>data</code> bind mount on persistent storage and include it in your backups.</p><ol><li>Extract the web release into a project directory. Create its writable <code>data</code> directory for UID/GID 10001.</li><li>For home use, follow <strong>Local network</strong>. For HTTPS, set <code>ASTROWEB_PUBLIC_HOST</code> to your domain and adapt the storage path in <code>compose.synology.yaml</code>.</li><li>Build the image, initialize the password, then start the project. For the HTTPS option, configure a certificate and a reverse proxy from that hostname to <code>127.0.0.1:8090</code>.</li></ol><pre>docker compose -f compose.yaml -f compose.synology.yaml build
docker compose -f compose.yaml -f compose.synology.yaml run --rm astroweb python -m astroweb admin
docker compose -f compose.yaml -f compose.synology.yaml up -d</pre>`],
 ['Web hosting','Choose a host that can render',`<p>Choose a Linux VPS or managed host that supports a continuously running Python service, FFmpeg/libx264, persistent writable storage and the image-processing dependencies. Confirm upload limits and background-job support with the provider.</p><ol><li>Install the web release as on a PC, or build its Docker image. Set <code>ASTROWEB_DATA</code> to persistent storage.</li><li>Run <code>python -m astroweb admin</code> in the same environment and data directory. Run one AstroWeb service under a service manager or Docker.</li><li>Set <code>ASTROWEB_HOSTS</code> to the accepted hostname(s), set <code>ASTROWEB_HTTPS=1</code>, and route HTTPS to the local service. Set proxy upload and read timeouts to accommodate FITS uploads and first-time renders.</li></ol><p>This GitHub Pages site serves static examples. Rendering and Studio run on your own host.</p>`],
 ['Google TV','Install the viewing app',`<p>The TV app is read-only. Choose the <a href="${tv}AstroWeb-TV-${tvVersion}.apk">HTTPS APK</a> for your HTTPS server or the <a href="${tv}AstroWeb-TV-LAN-${tvVersion}.apk">LAN APK</a> for the local-network setup. Both are signed sideload builds.</p><ol><li>Install Android Platform Tools on a computer on the same network. Enable developer options and wireless debugging on the TV. On TVs offering pairing, choose “Pair device with pairing code”.</li><li>Pair and connect using the two addresses shown by the TV. The pairing port and connection port can differ.</li></ol><pre>adb pair TV_IP:PAIRING_PORT
adb connect TV_IP:CONNECTION_PORT
adb -s TV_IP:CONNECTION_PORT install -r AstroWeb-TV-${tvVersion}.apk</pre><p>Use the LAN filename if applicable. Open AstroWeb TV, enter your server’s address and select Connect. Browse with the D-pad, press OK to open a capture, and Back to return. Voice is optional. Wireless pairing support varies by Android TV version. <a href="https://developer.android.com/tools/adb">Android installation reference ↗</a></p>`]
];
selectButtons($('install-tabs'),guides.map(i=>i[0]),i=>{$('install-content').innerHTML='<h3>'+guides[i][1]+'</h3>'+guides[i][2];});
const dialog=$('lightbox'),slot=$('lightbox-content');
function show(el){slot.replaceChildren(el);dialog.showModal();$('close').focus();}
$('watch').onclick=()=>{const v=document.createElement('video');v.src='media/overview.mp4';v.poster='media/elephant.webp';v.controls=true;v.playsInline=true;const captions=document.createElement('track');captions.kind='captions';captions.label='English';captions.srclang='en';captions.src='production/overview.vtt';captions.default=true;v.append(captions);show(v);v.play().catch(()=>{});};
for(const button of document.querySelectorAll('[data-print]'))button.onclick=()=>{const im=new Image();im.src='media/'+button.dataset.print+'.webp';im.alt=button.querySelector('img').alt;show(im);};
$('expand').onclick=()=>{const i=new Image();i.src=$('screen-img').src;i.alt=$('screen-img').alt;show(i);};
$('close').onclick=()=>dialog.close();dialog.onclick=e=>{if(e.target===dialog)dialog.close();};dialog.onclose=()=>{slot.querySelector('video')?.pause();slot.replaceChildren();};
