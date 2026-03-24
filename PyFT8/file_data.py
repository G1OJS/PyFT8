import os
import pickle

class File_data:
    def __init__(self, file):
        self.file = file
        self.data = {'dummy':0}
        if(os.path.exists(self.file)):
            self.load()
        self.save()
        
    def load(self):
        with open(f"{self.file}","rb") as f:
            self.data = pickle.load(f)

    def save(self):
        with open(f"{self.file}","wb") as f:
            pickle.dump(self.data, f)


if __name__ == "__main__":
    data = File_data(r"C:\Users\drala\Documents\Projects\GitHub\G1OJS\PyFT8_cfg\PyFT8_cd.pkl")
    print(data.data)
