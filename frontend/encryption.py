import hashlib
import os
import tarfile
import io
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend

def openssl_kdf(password, salt, key_len, iv_len):
    """
    Implements OpenSSL's EVP_BytesToKey for deriving key and IV from a password.
    """
    dtot = b""
    d = b""
    while len(dtot) < (key_len + iv_len):
        d = hashlib.md5(d + password + salt).digest()
        dtot += d
    return dtot[:key_len], dtot[key_len:key_len + iv_len]

def encrypt_data(data: bytes, password: str) -> bytes:
    """
    Encrypts data using AES-256-CBC with a salt, compatible with OpenSSL.
    """
    salt = os.urandom(8)
    key, iv = openssl_kdf(password.encode(), salt, 32, 16)
    
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(data) + padder.finalize()
    
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()
    
    return b"Salted__" + salt + ciphertext

def decrypt_data(encrypted_data: bytes, password: str) -> bytes:
    """
    Decrypts data encrypted with OpenSSL-compatible AES-256-CBC.
    """
    if not encrypted_data.startswith(b"Salted__"):
        raise ValueError("Invalid encrypted data format (missing Salted__ prefix)")
    
    salt = encrypted_data[8:16]
    ciphertext = encrypted_data[16:]
    
    key, iv = openssl_kdf(password.encode(), salt, 32, 16)
    
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded_data = decryptor.update(ciphertext) + decryptor.finalize()
    
    unpadder = padding.PKCS7(128).unpadder()
    return unpadder.update(padded_data) + unpadder.finalize()

def compress_data(data: bytes, filename: str) -> bytes:
    """
    Compresses data into a .tar.gz format in memory.
    """
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:gz") as tar:
        info = tarfile.TarInfo(name=filename)
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    return out.getvalue()

def decompress_data(tar_gz_data: bytes) -> bytes:
    """
    Decompresses .tar.gz data and returns the first file's content.
    """
    with tarfile.open(fileobj=io.BytesIO(tar_gz_data), mode="r:gz") as tar:
        for member in tar.getmembers():
            f = tar.extractfile(member)
            if f:
                return f.read()
    raise ValueError("No files found in compressed archive")
