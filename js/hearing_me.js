import mqtt from 'https://unpkg.com/mqtt/dist/mqtt.esm.js';

var mqttClient = null;
let hearing_me = new Set;
export {hearing_me}

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
	let myCall = document.getElementById('myCall').innerText
	topics.add('pskr/filter/v2/+/FT8/'+myCall+'/#');
	Array.from(topics).forEach((t) => {
		console.log("Subscribe to " + t);
		mqttClient.subscribe(t, (error) => {
			if (error) {console.error('subscription failed to ' + t, error)} 
		});
	});
}

//  "sq": 30142870791,"f": 21074653,"md": "FT8","rp": -5, "t": 1662407712,"t_tx": 1662407697,
//  "sc": "SP2EWQ",  "sl": "JO93fn42","rc": "CU3AT",  "rl": "HM68jp36",  "sa": 269,  "ra": 149,  "b": "15m"

function onMessage(msg) {
	const spot = {};
	msg.slice(1, -1).replaceAll('"', '').split(',').forEach( function (v) {let kvp = v.split(":"); spot[kvp[0]] = kvp[1];} );
	hearing_me.add(spot.b + "_" + spot.rc);
}

function add_row_hearing_me_list(callsign){
	let grid = document.getElementById('Hearing_me_list');
	let row = grid.appendChild(document.createElement("div"));
	row.className='grid_row';
	const cell_div = document.createElement("div");
	cell_div.textContent = callsign;
	cell_div.className='grid_cell';
	row.appendChild(cell_div);
	grid.scrollTop = grid.scrollHeight;
}
