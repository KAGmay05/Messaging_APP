import struct
import zlib

header_format = "!HHHHHH6s6s"
header_size = struct.calcsize(header_format)

def encode(ethertype, type, num_frag, total_frag, sender, receiver, data: bytes):
    
    length = len(data)

    sender_mac = sender.encode("utf-8")[:6].ljust(6, b"\x00")
    receiver_mac = receiver.encode("utf-8")[:6].ljust(6, b"\x00")

    header = struct.pack(
        header_format,
        ethertype,
        type,
        num_frag,
        total_frag,
        length,
        sender_mac,
        receiver_mac
    )
    # verificar si hay para checksum
    crc = zlib.crc32(header + data) & 0xFFFF
    frame = header + data + struct.pack("!H", crc)
    return frame
  
def decode(frame: bytes):
    header = frame[:header_size]
    info_crc = frame[header_size:]

    ethertype, type, num_frag, total_frag, length, sender, receiver = struct.unpack(
        header_format, header)
    
    # por que -2
    info = info_crc[:-2]
    crc = struct.unpack("!H", info_crc[-2:])

    new_crc = zlib.crc32(header + info) & 0xFFFF

    # rectificar si es un error
    if crc != new_crc:
        raise ValueError("Invalid CRC")
    
    # ver si se devuelve asi o como carlos
    return{
         ethertype,
         type,
         num_frag,
         total_frag,
         length,
         sender.decode(errors="ignore").strip("\x00"),
         receiver.decode(errors="ignore").strip("\x00"),
         info
    }
