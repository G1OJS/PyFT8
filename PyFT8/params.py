params = {'MIN_LLR_SD': 0.6,
          'HPS': 4, 'BPT':2,
          'SYM_RATE': 6.25,
          'SAMP_RATE': 12000,
          'T_CYC':15,
          'PAYLOAD_SYMBOLS': 79-7,
          'LDPC_CONTROL': (45, 12) }

params.update({ 'H0_RANGE': [-7 * params['HPS'], 22 * params['HPS']],
                'H_SEARCH_0': 28.75 * params['HPS'],
                'H_SEARCH_1': 68.75 * params['HPS']
               })
