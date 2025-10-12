import tarfile
import random

def file_to_bytes(path):
    with open(path, "rb") as f:
        return f.read()
    
def bytes_to_file(bytes, name):
    with open(name, "wb") as f:
        return f.write(bytes)

def fragment_data(data, chunk_size=1400):
    for i in range(0, len(data), chunk_size):
        yield data[i:i+chunk_size]

def id():
    return random.randrange(0,255)
