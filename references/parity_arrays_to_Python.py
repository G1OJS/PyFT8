with open("ldpc_174_91_c_parity.f90",'r') as f:
    obj_idx = 0
    for l in f.readlines():
        if(l.startswith('data')):
            name = ['Mn','Nm','nrw'][obj_idx]
            print(f"\n\n{name} = [")
            obj_idx +=1
        elif(l == ""):
            continue
        else:
            print(f"[{l.replace(', &\n','],').replace(',    &','],').replace('/',']]')}")
