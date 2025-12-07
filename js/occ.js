
let spectrum_width = 0;

export function update_spectrum(spectrum_power) {
	const spectrum = document.getElementById("Spectrum");
	spectrum.innerHTML = "";
	spectrum_power.forEach(v => {
		const cell = document.createElement("div");
		const brightness = Math.round(v * 255);
		cell.style.background = `rgb(${brightness},${brightness/2},0)`;
		spectrum.appendChild(cell);
	});
	spectrum_width = spectrum.offsetWidth;
}
export function update_freq_marker(marker_class, freq) {
	const spectrum = document.getElementById("Spectrum");
	const marker = document.querySelector(marker_class);
	const left = (document.getElementById("SpectrumContainer").clientWidth-spectrum_width)/2;
	const toPx = f => left + ((f - 0) / (3500 - 0)) * spectrum_width;
	marker.style.left = `${toPx(freq)}px`;
	for (const tick of document.querySelectorAll('.tickMarker')){
		let f = parseInt(tick.dataset.freq);
		tick.style.left = `${toPx(f)}px`;
	}
}