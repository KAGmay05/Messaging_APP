import struct
import zlib

header_format = "!6s6sHHHHHH"
header_size = struct.calcsize(header_format)

def encode(receiver, sender, ethertype, type, num_frag, total_frag, file_id, data: bytes):
    
    length = len(data)

    sender_mac= bytes.fromhex(sender.replace(":", ""))
    receiver_mac = bytes.fromhex(receiver.replace(":", ""))

    header = struct.pack(
        header_format,
        receiver_mac,
        sender_mac,
        ethertype,
        type,
        num_frag,
        total_frag,
        file_id,
        length
    )

    crc = zlib.crc32(header + data) & 0xFFFFFFFF
    frame = header + data + struct.pack("!I", crc)
    return frame
  
def decode(frame: bytes):
    header = frame[:header_size]
    info_crc = frame[header_size:]

    receiver, sender, ethertype, type, num_frag, total_frag, file_id, length  = struct.unpack(
        header_format, header)
    
    info = info_crc[:length]
    crc = struct.unpack("!I", info_crc[length:length+4])[0]

    new_crc = zlib.crc32(header + info) & 0xFFFFFFFF

    # rectificar si es un error
    if crc != new_crc:
        raise ValueError("Invalid CRC")
    
    return{
        "sender": ":".join(f"{b:02x}" for b in sender),
        "receiver": ":".join(f"{b:02x}" for b in receiver),
        "ethertype": ethertype,
        "type": type,
        "num_frag": num_frag,
        "total_frag": total_frag,
        "file_id": file_id,
        "length": length,
        "data": info
    }
