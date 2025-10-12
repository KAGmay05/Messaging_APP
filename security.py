import os
import hmac
import hashlib

SECURE_KEY = os.getenv("SECURE_KEY", "clave-por-defecto").encode()

def xor(data: bytes, key:bytes) -> bytes:
    key_length = len(key)
    return bytes ([b ^ key[i % key_length] for i, b in enumerate(data)])

def secure_encrypt(payload: bytes) -> bytes:
    va = os.urandom(4)
    ciphertext = xor(payload, SECURE_KEY + va)
    mac = hmac.new(SECURE_KEY, va + ciphertext, hashlib.sha256).digest()
    return va + ciphertext + mac

def secure_decrypt(payload: bytes) -> bytes:
    if len(payload) < 36:
        raise ValueError("Frame demasiado corto para desencriptar")
    
    va = payload[:4]
    mac_received = payload[-32:]
    chiphertext = payload[4:-32]

    mac_expected = hmac.new(SECURE_KEY, va + chiphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(mac_received, mac_expected):
        raise ValueError("MAC no coincide, datos corruptos o modificados")
    
    return xor(chiphertext, SECURE_KEY + va)