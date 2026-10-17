

    def search(self, t0_cyc, cycle_start_str):
        t0 = time.time()
        candidates_rough = []
        for f0_idx in range(int(50 / 3.125), self.audio_in.nFreqs - 8 * BPT):
            time.sleep(0)
            freq_idxs = f0_idx + self.base_freq_idxs
            p = self.audio_in.tfgrid[0, :, f0_idx:f0_idx+8*BPT]
            new_origin = {'score':0}
            for h0_idx in range(H0_RANGE[0], H0_RANGE[1], HPS):
                vals = p[h0_idx + self.hop_idxs_Costas + 36 * HPS, :].ravel()
                sync_score = np.dot(vals, self.csync_flat) / np.max(vals)
                test_origin = {'f0_idx': f0_idx, 'h0_idx':h0_idx, 'score':sync_score}
                if test_origin['score'] > new_origin['score']:
                    new_origin = test_origin
            if new_origin['score'] > MIN_PRE_SCORE:
                candidates_rough.append(new_origin)
        candidates = []
        t1 = time.time()
        for c in candidates_rough:
            time.sleep(0)
            new_origin = {'score':0}
            h0_idx_rough = c['h0_idx']
            f0_idx = c['f0_idx']
            freq_idxs = f0_idx + self.base_freq_idxs
            p = self.audio_in.tfgrid[0, :, f0_idx:f0_idx+8*BPT]
            for h0_idx in range(h0_idx_rough - int(HPS/2), h0_idx_rough + int(HPS/2)):
                vals = p[h0_idx + self.hop_idxs_Costas + 36 * HPS, :].ravel()
                sync_score = np.dot(vals, self.csync_flat) / np.max(vals)
                test_origin = {'f0_idx': f0_idx, 'h0_idx':h0_idx, 'score':sync_score}
                if test_origin['score'] > new_origin['score']:
                    new_origin = test_origin
            if new_origin['score'] > MIN_SCORE:                        
                f0_idx = new_origin['f0_idx']
                freq_idxs = f0_idx + self.base_freq_idxs
                hops = [(new_origin['h0_idx'] + h) % HPC for h in self.base_payload_hops]
                p_idx = np.ix_(hops, freq_idxs)
                tsec = new_origin['h0_idx'] / (SYM_RATE * HPS)
                dt = tsec - 0.5
                fHz = 3.125 * f0_idx
                abs_t0 = t0_cyc + tsec
                new_origin.update({'f0_idx': f0_idx, 'cs':cycle_start_str, 'p_idx':p_idx, 'fHz': fHz, 'dt': dt, 'abs_t0':abs_t0, 
                                   'decode_info': None, 'decode_result':None, 'saved_llrs':[]})
                candidates.append(new_origin)            
                
        candidates.sort(key = lambda c: -c['score'])
        candidates = candidates[:MAX_CANDS]
        candidates.sort(key = lambda c: int(c['h0_idx']))
        t2 = time.time()
        print(f"{t1-t0:6.2f} {t2-t1:6.2f} {t2-t0:6.2f} {len(candidates)}")
        return candidates


