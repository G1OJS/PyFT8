import {connectToFeed, hearing_me, add_row_hearing_me_list} from './hearing_me.js';
import {update_spectrum, update_freq_marker} from './occ.js';

let myCall = "";
let myBand = "";
let txFreq = null;
let rxFreq = null;
let current_band = null;

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

function update_hearing_me_list(){
	let grid = document.getElementById('Hearing_me_list');
	for (const el of grid.querySelectorAll('.grid_row:not(.header)')) {el.remove()}
	for (const hm of hearing_me){
		let b = hm.split('_')[0]
		let c = hm.split('_')[1]
		console.log(b, c, current_band);
		if(b == myBand | myBand == '') {add_row_hearing_me_list(c)}
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
	if(dd.call_a == "CQ" && dd.call_b != myCall) {
		row.classList.add("cq");
	}
	
	if(dd.call_a == myCall) {
		row.classList.add('sentTomyCall')
	}
	if(dd.call_b == myCall) {
		row.classList.add('sentBymyCall')
	}
	
	const snr_fmt = (parseInt(dd.snr)<0? "":"+") + dd.snr
	let fields = null;
	if(document.URL.includes("compare")){
		fields = [dd.cyclestart_str.split('_')[1], dd.decode_delay, snr_fmt, dd.freq, dd.dt, dd.call_a, dd.call_b, dd.grid_rpt,dd.n_its, dd.ncheck_initial,''];
	} else {
		fields = [dd.cyclestart_str.split('_')[1], snr_fmt, dd.freq, dd.call_a, dd.call_b, dd.grid_rpt, ''];
	}
	fields.forEach((field, idx) => {
		const cell_div = document.createElement("div");
		cell_div.textContent = field;
		cell_div.className='grid_cell';
		if(grid_id == 'all_decodes' && idx == 6){
			if (hearing_me.has(dd.call_b)){
				console.log(dd.call_b,"hearing me");
				cell_div.innerText = "X"
				cell_div.classList.add('hearing_me');
			}			
		}
		row.appendChild(cell_div);
	});

	grid.scrollTop = grid.scrollHeight;

	row.addEventListener("click", e => {
		update_freq_marker('.rxMarker', parseInt(dd.freq));
		websocket.send(JSON.stringify({	
			topic: "ui.clicked-message", 
			cyclestart_str: dd.cyclestart_str,
			call_a:dd.call_a, call_b: dd.call_b, 
			grid_rpt: dd.grid_rpt, snr:dd.snr, freq: dd.freq
		}));
	}); 
}
	
function handle_button_click(action){
	console.log(action);
	websocket.send(JSON.stringify({topic: "ui." + action}));
	if(action.search('set-band')==0) {
		console.log("Clear grids"); 
		myBand = action.split("-")[2];
		for (const el of document.querySelectorAll('.grid_row:not(.header)')) {el.remove()}
	}
}

const websocket = new WebSocket("ws://localhost:5678/");
websocket.onmessage = (event) => {
	const dd = JSON.parse(event.data)
	if(!dd) return;

	if(dd.topic == 'connect_pskr_mqtt')	{connectToFeed();}
	if(dd.topic == 'loading_metrics') 	{updateLoadingMetrics(dd)}
	if(dd.topic == 'add_band_button')   {add_band_button(dd.band_name, dd.band_freq)}
	if(dd.topic == 'set_band') 			{current_band = dd.band}
	if(dd.topic == 'set_rxfreq') 		{update_freq_marker('.rxMarker', parseInt(dd.freq));}
	if(dd.topic == 'set_txfreq') 		{update_freq_marker('.txMarker', parseInt(dd.freq));}
	if(dd.topic == "freq_occ_array") 	{update_spectrum(dd.histogram)}
	
	if(dd.topic == 'set_myCall') {
		myCall = dd.myCall;
		document.getElementById('myCall').innerText = myCall;
	}
	
	if(dd.topic == 'decode_dict') {
		if(document.URL.includes("tcvr")){
			if (dd.priority) {add_decode_row(dd, 'priority_decodes')}
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
	
function add_band_button(band_name, band_freq){
	let parentEl = document.getElementById('buttons');
	let btn = parentEl.appendChild(document.createElement("button"));
	btn.className = 'button';
	btn.innerText = band_name;
	btn.dataset.action = `set-band-${band_name}-${band_freq}`;
	btn.addEventListener("click", (event) => { handle_button_click(event.target.dataset.action)});
}

document.addEventListener("DOMContentLoaded", (event) => { 
	document.getElementById('buttons').addEventListener("click", (event) => { 
		handle_button_click(event.target.dataset.action)
	});
});

function updateLoadingMetrics(data) {
	let bar_data = [data.n_demapped/(data.n_synced+0.001), data.n_for_ldpc/(data.n_demapped+0.001), data.n_decoded/(data.n_for_ldpc+0.001)]
	for (const i of[0,1,2]){
		document.getElementById("bar-"+i).style.transform =
		`scaleY(${1-bar_data[i]})`;
	}
	document.getElementById('n_candidates').innerText = data.n_synced;
}

setInterval(update_clock, 250);
if(document.URL.includes("tcvr")) {setInterval(update_hearing_me_list, 1000)}



