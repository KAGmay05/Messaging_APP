import struct
import zlib
import security

header_format = "!6s6sHHHHHH"
header_size = struct.calcsize(header_format)

def encode(receiver, sender, ethertype, type, num_frag, total_frag, file_id, data: bytes):

    sender_mac= bytes.fromhex(sender.replace(":", ""))
    receiver_mac = bytes.fromhex(receiver.replace(":", ""))

    protected_data = security.secure_encrypt(data)
    length = len(protected_data)

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

    crc = zlib.crc32(header + protected_data) & 0xFFFFFFFF
    frame = header + protected_data + struct.pack("!I", crc)
    return frame
  
def decode(frame: bytes):
    header = frame[:header_size]
    info_crc = frame[header_size:]

    receiver, sender, ethertype, type, num_frag, total_frag, file_id, length  = struct.unpack(
        header_format, header)
    
    protected_data = info_crc[:length]
    crc = struct.unpack("!I", info_crc[length:length+4])[0]

    new_crc = zlib.crc32(header + protected_data) & 0xFFFFFFFF

    if crc != new_crc:
        raise ValueError("Invalid CRC")
    
    try:
        info = security.secure_decrypt(protected_data)
    except ValueError as e:
        print(e)
        return None
        
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
