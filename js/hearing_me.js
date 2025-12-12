import mqtt from 'https://unpkg.com/mqtt/dist/mqtt.esm.js';
import {myCall, mySquare, currentBand, add_decode_row} from './PyFT8_UI.js'

var mqttClient = null;
let hearing_me = new Set;
export {hearing_me};

export function connectToFeed() {
	mqttClient = mqtt.connect("wss://mqtt.pskreporter.info:1886");
	mqttClient.onSuccess = subscribe();
	mqttClient.on("message", (filter, message) => {
		onMessage(message.toString());
	});
}

function subscribe() {
	//pskr/filter/v2/{band}/{mode}/{sendercall}/{receivercall}/{senderlocator}/{receiverlocator}/{sendercountry}/{receivercountry}
	let topics = new Set;
	let myCall = document.getElementById('myCall').innerText
	topics.add('pskr/filter/v2/+/FT8/'+myCall+'/#');
	topics.add('pskr/filter/v2/+/FT8/+/+/'+mySquare+'/#');
	topics.add('pskr/filter/v2/+/FT8/+/+/+/'+mySquare+'/#');
	Array.from(topics).forEach((t) => {
		console.log("Subscribe to " + t);
		mqttClient.subscribe(t, (error) => {
			if (error) {console.error('subscription failed to ' + t, error)} 
		});
	});
}

function onMessage(msg) {
	//  "sq": 30142870791,"f": 21074653,"md": "FT8","rp": -5, "t": 1662407712,"t_tx": 1662407697,
	//  "sc": "SP2EWQ",  "sl": "JO93fn42","rc": "CU3AT",  "rl": "HM68jp36",  "sa": 269,  "ra": 149,  "b": "15m"
	const spot = {};
	msg.slice(1, -1).replaceAll('"', '').split(',').forEach( function (v) {let kvp = v.split(":"); spot[kvp[0]] = kvp[1];} );
	if(spot.sc == myCall) {
		hearing_me.add(spot.b + "_" + spot.rc + "_" + spot.rp);
	}
	if(spot.b == currentBand && spot.md == "FT8"){
		let f = parseInt(spot.f) %10000; 
		f -= (currentBand=="80m")? 3000:4000;
		let dd = {'cyclestart_str':'000000_000000', 'call_a':spot.rc, 'call_b':spot.sc, 'grid_rpt':spot.rp, 'snr':'', 'freq':f, 'decoder':'PSKR'};
		//add_decode_row(dd, 'all_decodes');
	}
}

