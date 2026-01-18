
### Test scripts
As I'm still exploring decoding techniques, I'm necessarily developing tools to expose what's going on in the signal's jouney from received audio to printed text. These tools aren't polished, though I'm trying to do that as I go along.

There are two threads to this currently; [test_compare_vs_wsjtx.py](https://github.com/G1OJS/PyFT8/blob/main/tests/test_compare_vs_wsjtx.py) and its companion [test_compare_vs_wsjtx_plot.py](https://github.com/G1OJS/PyFT8/blob/main/tests/test_compare_vs_wsjtx_plot.py) allow decoding either live on air or from a wav file, and gather information to produce plots like this:
<img width="1000" height="600" alt="40m midday" src="https://github.com/user-attachments/assets/dd45506a-5b2f-417a-910a-fb0466122cd7" />

I'm also developing a test wrapper in [test_loopback_performance.py](https://github.com/G1OJS/PyFT8/blob/main/tests/test_loopback_performance.py) that calls the main PyFT8 code having generated an FT8 audio stream with a random level of noise added to it, in Montecarlo fashion, and produces results like this:

<img width="1489" height="495" alt="decoder_performance_full_decoder_varying_amplitudes_osd_50_30" src="https://github.com/user-attachments/assets/2f84db63-8593-43fb-a10e-5fc1fc65f5f2" />
<img width="1489" height="495" alt="proxy_plots_full_decoder_varying_amplitudes_osd_50_30" src="https://github.com/user-attachments/assets/f58ac019-8787-4e91-bf39-2ea00fff25f8" />
<img width="1487" height="495" alt="test_timings_full_decoder_varying_amplitudes_osd_50_30" src="https://github.com/user-attachments/assets/e2dcdf47-3bc8-424f-b9ed-c86510a0941c" />
