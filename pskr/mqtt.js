import {squareIsInHome} from './geo.js';
import {squaresArr} from './config.js';
import {addSpot} from './tileGrid.js'
import mqtt from 'https://unpkg.com/mqtt/dist/mqtt.esm.js';

var mqttClient = null;

export function connectToFeed() {
    //pskr/filter/v2/{band}/{mode}/{sendercall}/{receivercall}/{senderlocator}/{receiverlocator}/{sendercountry}/{receivercountry}
    mqttClient = mqtt.connect("wss://mqtt.pskreporter.info:1886");
    mqttClient.onSuccess = subscribe();
    mqttClient.on("message", (filter, message) => {
        onMessage(message.toString());
    });
}

function subscribe() {
    // find the topics for the level 4 squares we need to subscribe to in order to get messages for our squares in squaresArr
    let topics = new Set;
    for (let i = 0; i < squaresArr.length; i++) {
        topics.add('pskr/filter/v2/+/+/+/+/' + squaresArr[i].substring(0, 4) + '/+/+/#');
        topics.add('pskr/filter/v2/+/+/+/+/+/' + squaresArr[i].substring(0, 4) + '/+/#');
    }
    // now subscribe to the topics
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
    });

	let sh = squareIsInHome(spot.sl);
	let rh = squareIsInHome(spot.rl);
	if(sh || rh) addSpot(spot, sh, rh);
}
