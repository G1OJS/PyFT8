
import mqtt from 'https://unpkg.com/mqtt/dist/mqtt.esm.js';

var mqttClient = null;
let hearing_me = new Set;

export function connectToFeed() {
	//pskr/filter/v2/{band}/{mode}/{sendercall}/{receivercall}/{senderlocator}/{receiverlocator}/{sendercountry}/{receivercountry}
	mqttClient = mqtt.connect("wss://mqtt.pskreporter.info:1886");
	mqttClient.onSuccess = subscribe();
	mqttClient.on("message", (filter, message) => {
		onMessage(message.toString());
	});
}

function subscribe() {
	let topics = new Set;
	topics.add('pskr/filter/v2/+/FT8/'+myCall+'/#');
	Array.from(topics).forEach((t) => {
		console.log("Subscribe to " + t);
		mqttClient.subscribe(t, (error) => {
			if (error) {console.error('subscription failed to ' + t, error)} 
		});
	});
}

function onMessage(msg) {
	const spot = {};
	msg.slice(1, -1).replaceAll('"', '').split(',')
	.forEach(function (v) {
		let kvp = v.split(":");
		spot[kvp[0]] = kvp[1];
		if(! hearing_me.has(spot.rc)) {add_hearing_me_list(spot.rc);}
		hearing_me.add(spot.rc);
	});
}

function add_hearing_me_list(call){
	let grid = document.getElementById('Hearing_me_list');
	let row = grid.appendChild(document.createElement("div"));
	row.className='grid_row';
	const cell_div = document.createElement("div");
	cell_div.textContent = call;
	cell_div.className='grid_cell';
	row.appendChild(cell_div);
	grid.scrollTop = grid.scrollHeight;
}

let myCall = "";
let spectrum_width = 0;
let txFreq = null;
let rxFreq = null;
function update_spectrum(spectrum_power) {
	const spectrum = document.getElementById("Spectrum");
	spectrum.innerHTML = "";
	spectrum_power.forEach(v => {
		const cell = document.createElement("div");
		const brightness = Math.round(v * 255);
		cell.style.background = `rgb(${brightness},${brightness/2},0)`;
		spectrum.appendChild(cell);
	});
	spectrum_width = spectrum.offsetWidth;
	update_freq_markers();
}
function update_freq_markers() {
	const spectrum = document.getElementById("Spectrum");
	const txMarker = document.querySelector(".txMarker");
	const rxMarker = document.querySelector(".rxMarker");
	const left = (document.getElementById("SpectrumContainer").clientWidth-spectrum_width)/2;
	const toPx = f => left + ((f - 0) / (3500 - 0)) * spectrum_width;
	if(txFreq) txMarker.style.left = `${toPx(txFreq)}px`;
	if(rxFreq) rxMarker.style.left = `${toPx(rxFreq)}px`;
	for (const tick of document.querySelectorAll('.tickMarker')){
		let f = parseInt(tick.dataset.freq);
		tick.style.left = `${toPx(f)}px`;
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
	const fields = [dd.cyclestart_str.split('_')[1], dd.snr, dd.freq, dd.call_a, dd.call_b, dd.grid_rpt, ''];
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
		update_freq_markers(rxFreq = dd.freq);
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
		for (const el of document.querySelectorAll('.grid_row')) {
			if(!el.classList.contains('header')) {el.remove()}
		}
		for (const el of document.querySelectorAll('.grid_row')) {
			if(!el.classList.contains('header')) {el.remove()}
		}
		hearing_me = new Set;
	}
}

const websocket = new WebSocket("ws://localhost:5678/");
websocket.onmessage = (event) => {
	const dd = JSON.parse(event.data)
	if(!dd) return;

	if(dd.topic == 'add_band_button')   {add_band_button(dd.band_name, dd.band_freq)}
	if(dd.topic == 'set_myCall') 		{
		myCall = dd.myCall;
		document.getElementById('myCall').innerText = myCall;
	}
	if(dd.topic == 'set_rxfreq') 		{rxFreq = parseInt(dd.freq); update_freq_markers();}
	if(dd.topic == 'set_txfreq') 		{txFreq = parseInt(dd.freq); update_freq_markers();}
	if(dd.topic == 'decode_queue') {
		document.getElementById('n_ldpc_load').innerText = dd.n_ldpc_load
		document.getElementById('n_candidates').innerText = dd.n_candidates
	}
	if(dd.topic == "freq_occ_array") 	{update_spectrum(dd.histogram)}
	if(dd.topic == 'decode_dict')		{
		if (dd.priority) {add_decode_row(dd, 'priority_decodes')}
		add_decode_row(dd, 'all_decodes')
	}
	
	if(dd.topic == 'msg') {add_decode_row(dd, 'priority_decodes')}
	
	if(dd.topic == 'connect_pskr_mqtt'){connectToFeed();}
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

setInterval(update_clock, 250);

