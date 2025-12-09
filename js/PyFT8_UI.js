import {connectToFeed, is_hearing_me, update_hearing_me_list} from './hearing_me.js';
import {update_spectrum, update_freq_marker} from './occ.js';

let myCall = "";
let currentBand = "20m";
let txFreq = null;
let rxFreq = null;

export {myCall, currentBand}

function setMyCall(call){
	myCall = call;
	document.getElementById('myCall').innerText = myCall;
}

function setCurrentBand(band){
	currentBand = band;
	for (const el of document.querySelectorAll('.grid_row:not(.header)')) {el.remove()}
	document.getElementById('currentBand').innerText = currentBand;
	if(document.URL.includes("compare")){
		n_wsjtx_decodes.innerText = 0;
		n_PyFT8_decodes.innerText = 0;
	}
}

function update_clock() {
	const t = new Date;
	const utc = ("0" + t.getUTCHours()).slice(-2) + ":" + ("0" + t.getUTCMinutes()).slice(-2) + ":" + ("0" + t.getUTCSeconds()).slice(-2);
	document.getElementById("clock").innerHTML = utc + " UTC";
	let t_cyc = t.getUTCSeconds() %15;
	if(t_cyc > 12.6) {
		for (const el of document.querySelectorAll(".transmitting_button")) {el.classList.add("cq"); el.classList.remove("cq_faded"); }
	}
	if(t_cyc > 1.5 && t_cyc <11) {
		for (const el of document.querySelectorAll(".transmitting_button")) {el.classList.remove("cq"); el.classList.add("cq_faded"); }
		for (const el of document.querySelectorAll(".cq")) {el.classList.remove("cq"); el.classList.add("cq_faded"); }
		for (const el of document.querySelectorAll(".sentTomyCall")) {el.classList.remove("sentTomyCall"); el.classList.add("sentTomyCall_faded"); }
	} 
	for (const el of document.querySelectorAll(".sentBymyCall")) {
		const t_tx_hms = el.firstChild.innerHTML;
		const d = new Date();
		const secs_today = d.getHours() * 3600 + d.getMinutes() * 60 + d.getSeconds();
		const t_tx_secs = parseInt(t_tx_hms.slice(0,2))*3600+ parseInt(t_tx_hms.slice(2,4))*60 + parseInt(t_tx_hms.slice(4,6))
		const t = secs_today - t_tx_secs 
		if(t < 0) {el.classList.add("flash")} else {el.classList.remove("flash")} 
		if(t>0 && t < 12.6) {el.classList.add("highlight")} else {el.classList.remove("highlight")} 
	}
}

function add_decode_row(decode_dict, grid_id) {
	let dd = decode_dict;
	console.log(dd);
	let grid = document.getElementById(grid_id)
	let row = grid.appendChild(document.createElement("div"));
	row.className='grid_row';
	let cs = dd.cyclestart_str;
	if (cs.charAt(cs.length-1) == '5'){row.classList.add('odd')} else {row.classList.add('even')}
	if(dd.call_a == "CQ" && dd.call_b != myCall) {row.classList.add("cq");}
	if(dd.call_a == myCall) {row.classList.add('sentTomyCall')}
	if(dd.call_b == myCall) {row.classList.add('sentBymyCall')}
	
	const snr_fmt = (parseInt(dd.snr)<0? "":"+") + dd.snr
	let fields = null;
	if(document.URL.includes("compare")){
		fields = [dd.cyclestart_str.split('_')[1], dd.decode_delay, snr_fmt, dd.freq, dd.dt, dd.call_a, dd.call_b, dd.grid_rpt,dd.n_its, dd.ncheck_initial,''];
	} else {
		fields = [dd.cyclestart_str.split('_')[1], snr_fmt, dd.freq, dd.call_a, dd.call_b, dd.grid_rpt, dd.hearing_me];
	}
	fields.forEach((field, idx) => {
		const cell_div = document.createElement("div");
		cell_div.textContent = field;
		cell_div.className='grid_cell';			
		row.appendChild(cell_div);
	});

	row.addEventListener("click", e => {
		update_freq_marker('.rxMarker', parseInt(dd.freq));
		websocket.send(JSON.stringify({	
			topic: "ui.clicked-message", 
			cyclestart_str: dd.cyclestart_str,
			call_a:dd.call_a, call_b: dd.call_b, 
			grid_rpt: dd.grid_rpt, snr:dd.snr, freq: dd.freq
		}));
	}); 
	
	grid.scrollTop = grid.scrollHeight;
}
	
const websocket = new WebSocket("ws://localhost:5678/");
websocket.onmessage = (event) => {
	const dd = JSON.parse(event.data)
	if(!dd) return;
	
	if(dd.topic == 'set_myCall') 		{setMyCall(dd.myCall)}
	if(dd.topic == 'set_band') 			{setCurrentBand(dd.band)}
	if(dd.topic == 'connect_pskr_mqtt')	{connectToFeed();}
	if(dd.topic == 'loading_metrics') 	{updateLoadingMetrics(dd)}
	if(dd.topic == 'add_action_button') {add_action_button(dd.caption, dd.action, dd.class)}
	if(dd.topic == 'set_rxfreq') 		{update_freq_marker('.rxMarker', parseInt(dd.freq));}
	if(dd.topic == 'set_txfreq') 		{update_freq_marker('.txMarker', parseInt(dd.freq));}
	if(dd.topic == "freq_occ_array") 	{update_spectrum(dd.histogram)}
	
	if(dd.topic == 'decode_dict') {
		if(document.URL.includes("tcvr")){
			if (dd.priority) {add_decode_row(dd, 'priority_decodes')}
			dd.hearing_me = is_hearing_me(dd.call_b)? "X":"";	
			add_decode_row(dd, 'all_decodes')
		}
		if(document.URL.includes("compare")){
			const n_PyFT8_decodes = document.getElementById('n_PyFT8_decodes');
			const pc_PyFT8_decodes = document.getElementById('pc_PyFT8_decodes');
			const n_wsjtx_decodes = document.getElementById('n_wsjtx_decodes');
			const t = new Date / 1000;
			let decode_delay = t%15
			decode_delay -= decode_delay > 11 ? 15:0
			dd.decode_delay = Math.round(100*decode_delay)/100 ;
			if (dd.source == 'WSJTX') {
				add_decode_row(dd, 'wsjtx_decodes');
				n_wsjtx_decodes.innerText = 1+parseInt(n_wsjtx_decodes.innerText);
			} else {
				add_decode_row(dd, 'PyFT8_decodes');
				n_PyFT8_decodes.innerText = 1+parseInt(n_PyFT8_decodes.innerText);
			}
			let w = parseInt(n_wsjtx_decodes.innerText)
			let p = parseInt(n_PyFT8_decodes.innerText)
			if(w>0){
				let pc = Math.round(100*p/w);
				pc_PyFT8_decodes.innerText = pc + '%';
			}
		}
	}
	
}
	
function add_action_button(caption, action, classname){
	console.log("Add button "+caption+" "+action);
	let parentEl = document.getElementById('buttons');
	let btn = parentEl.appendChild(document.createElement("button"));
	btn.className = classname;
	btn.innerText = caption;
	btn.dataset.action = action;
	btn.addEventListener("click", (event) => { websocket.send(JSON.stringify({topic: "ui." + event.target.dataset.action})) });
}

function updateLoadingMetrics(metrics_dict) {
	let metrics_area = document.getElementById("metrics_area");
	if (metrics_area.children.length == 0) {
		console.log("create metrics area")
		let html = "";
		
		for (const [k, v] of Object.entries(metrics_dict)){
			if(k!='topic'){
				html = html + "<div class='bar-container'><div class='bar-bg'><div id='"
				html = html + k + "' class='bar'></div></div><span class='label'>" + k + "</span></div>"
			}
		}
		metrics_area.innerHTML = html;
	}
	for (const [k, v] of Object.entries(metrics_dict)){
		if(k!='topic'){
			document.getElementById(k).style.transform =`scaleY(${1-v})`;
		}
	}
}


setInterval(update_clock, 250);
if(document.URL.includes("tcvr")) {setInterval(update_hearing_me_list, 1000)}



