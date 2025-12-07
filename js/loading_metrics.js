

export function updateLoadingMetrics(data) {
	let bar_data = [data.n_synced/500, data.n_demapped/500, data.n_decoded/500, data.n_decode_success/75]
	for (const i of[0,1,2,3]){
		document.getElementById("bar-"+i).style.transform =
		`scaleY(${1-bar_data[i]})`;
	}
	document.getElementById('n_candidates').innerText = data.n_synced;
	document.getElementById('n_in_ldpc').innerText = data.n_in_ldpc;
}
