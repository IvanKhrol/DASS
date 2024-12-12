import base64
import secrets

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature

def open_key(key_type:str, key_path:str)->(rsa.RSAPublicKey | rsa.RSAPrivateKey | None):
	if(key_type == "public"):
		with open(key_path, 'rb') as f:
			return serialization.load_pem_public_key(f.read())
	elif(key_type == "private"):
		with open(key_path, 'rb') as f:
			return serialization.load_pem_private_key(f.read(), password=None)
	else:
		return None


def sign_data(private_key:rsa.RSAPrivateKey, data:str)->str:
	signature = private_key.sign(
		data.encode(),
		padding.PSS(
			mgf=padding.MGF1(algorithm=hashes.SHA256()),
			salt_length=padding.PSS.MAX_LENGTH,
		),
		hashes.SHA256(),
	)
	return base64.b64encode(signature).decode()

def verify_signature(public_key:rsa.RSAPublicKey, signature:str, data:str)->bool:
	try:
		public_key.verify(
			base64.b64decode(signature),
			data.encode(),
			padding.PSS(
				mgf=padding.MGF1(algorithm=hashes.SHA256()),
				salt_length=padding.PSS.MAX_LENGTH,
			),
			hashes.SHA256(),
		)
		return True
	except InvalidSignature:
		return False

def encrypt_RSA(public_key:rsa.RSAPublicKey, data)->str:
	encrypted = public_key.encrypt(
		data,
		padding.OAEP(
				mgf=padding.MGF1(algorithm=hashes.SHA256()),
				algorithm=hashes.SHA256(),
				label=None,
		),
	)
	return base64.b64encode(encrypted).decode()


def decrypt_RSA(private_key:rsa.RSAPrivateKey, data:str)->bytes:
	data = base64.b64decode(data)
	decrypted = private_key.decrypt(
		data,
		padding.OAEP(
			mgf=padding.MGF1(algorithm=hashes.SHA256()),
			algorithm=hashes.SHA256(),
			label=None,
		),
	)
	return decrypted

def encrypt_AES(K:bytes, plaintext:bytes)->bytes:
	"""Encrypts plaintext using AES-GCM; prepends IV to ciphertext."""

	# Generate a random IV
	iv = secrets.token_bytes(12)  # AES-GCM needs a 12-byte IV

	cipher = Cipher(algorithms.AES(K), modes.GCM(iv), backend=default_backend())
	encryptor = cipher.encryptor()

	ciphertext = encryptor.update(plaintext) + encryptor.finalize()
	tag = encryptor.tag

	return iv + ciphertext + tag


def decrypt_AES(K:bytes, ciphertext_with_iv:bytes)->str:
	"""Decrypts ciphertext (with prepended IV) using AES-GCM."""
	ciphertext_with_iv = base64.b64decode(ciphertext_with_iv)
	iv = ciphertext_with_iv[:12]
	ciphertext = ciphertext_with_iv[12:-16]  # remove IV and tag
	tag = ciphertext_with_iv[-16:]

	cipher = Cipher(algorithms.AES(K), modes.GCM(iv, tag), backend=default_backend())
	decryptor = cipher.decryptor()

	plaintext = decryptor.update(ciphertext) + decryptor.finalize()
	return plaintext.decode()


def generate_session_keys():
	"""Generates a 256-bit session key K and an RSA key pair K_p."""

	# Generate 256-bit session key K
	K = secrets.token_bytes(32)  # 32 bytes = 256 bits

	# Generate RSA key pair K_p (adjust key_size as needed)
	private_key_kp = rsa.generate_private_key(
			public_exponent=65537, key_size=1024
	)
	public_key_kp = private_key_kp.public_key()

	#Convert Keys to PEM format for storage.  This is essential for usage in real applications and should be done when storing keys for later retrieval.

	# private_key_pem_kp = private_key_kp.private_bytes(
	# 		encoding=serialization.Encoding.PEM,
	# 		format=serialization.PrivateFormat.TraditionalOpenSSL,
	# 		encryption_algorithm=serialization.NoEncryption()
	# )

	# public_key_pem_kp = public_key_kp.public_bytes(
	# 		encoding=serialization.Encoding.PEM,
	# 		format=serialization.PublicFormat.SubjectPublicKeyInfo,
	# )

	return K, private_key_kp, public_key_kp