import tarfile
import random

def file_to_bytes(path):
    with open(path, "rb") as f:
        return f.read()
    
def bytes_to_file(bytes, name):
    with open(name, "wb") as f:
        return f.write(bytes)

def folder_to_tar(folder_path, tar_path):
    with tarfile.open(tar_path, "w") as tar:
        tar.add(folder_path, arcname=".")

def tar_to_folder(tar_path, output_folder):
    with tarfile.open(tar_path, "r") as tar:
        tar.extractall(path=output_folder)

def fragment_data(data, chunk_size=1400):
    for i in range(0, len(data), chunk_size):
        yield data[i:i+chunk_size]

def id():
    return random.randrange(0,255)
