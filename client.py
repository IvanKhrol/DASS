#!/usr/bin/python
import socket
import json, base64, time, re

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

from Crypt import open_key, generate_session_keys,  \
									sign_data, verify_signature, \
									encrypt_AES, encrypt_RSA, \
									decrypt_AES, decrypt_RSA

from GOST3412 import Kuznechik

class Client:
	HOST: str = '127.0.0.1'
	PORT : int = 0
	name: str
	sock: socket.socket
	self_private_key: 	rsa.RSAPrivateKey	= None
	self_public_key: 		rsa.RSAPublicKey	= None
	trent_public_key: 	rsa.RSAPublicKey	= None
	other_public_key:		rsa.RSAPublicKey 	= None
	session_key:				bytes 						= None
	pair_private_key: 	rsa.RSAPrivateKey = None
	pair_public_key: 		rsa.RSAPublicKey 	= None
	time_stamp: 				int								= None
	lifetime:						int 							= 120
	cipher:							Kuznechik					= None

	def __init__(self, name:str, serv_addr:str = '127.0.0.1', serv_port:int = 65432):
		self.name = name
		self.sock = socket.socket()
		self.sock.connect((serv_addr, serv_port))
		if(name == "ALICE"):
			self.self_private_key = open_key("private", "alice/alice_private")
			self.self_public_key 	= open_key("public", "alice/alice_public")
			self.trent_public_key = open_key("public", "alice/trent_public")
		else:
			self.self_private_key = open_key("private", "bob/bob_private")
			self.self_public_key 	= open_key("public", "bob/bob_public")
			self.trent_public_key = open_key("public", "bob/trent_public")
		pass
	
	def generate_session_message(self):
		if self.other_public_key is not None:
			# Regen key if lifetime left
			if self.time_stamp is None or int(time.time()) - self.time_stamp > self.lifetime:
				print("debug: gen session keys")
				self.session_key, self.pair_private_key, self.pair_public_key = generate_session_keys()
				self.time_stamp = int(time.time())
			time_stamp_encrypt = base64.b64encode(encrypt_AES(self.session_key, str(self.time_stamp).encode())).decode()

			public_pair_key_b64 = base64.b64encode(self.pair_public_key .public_bytes(
								encoding=serialization.Encoding.PEM, 
								format=serialization.PublicFormat.SubjectPublicKeyInfo)).decode()
			private_pair_key_b64 = base64.b64encode(self.pair_private_key.private_bytes(
				encoding=serialization.Encoding.PEM,
				format=serialization.PrivateFormat.TraditionalOpenSSL,
				encryption_algorithm=serialization.NoEncryption())).decode()
			
			data_pair_key = \
				"lifetime:" 		+ str(self.lifetime) + \
				"private_key:"	+ private_pair_key_b64 	+ \
				"public_key: " 	+ public_pair_key_b64 
			signature_pair_key = sign_data(self.self_private_key, data_pair_key)

			session_key_encrypt 		= encrypt_RSA(self.other_public_key, self.session_key)
			signature_session_key 	= sign_data(self.pair_private_key, session_key_encrypt)
			message = {
				"type": 									"session",
				"ind":										name,
				"time_stamp": 						time_stamp_encrypt,
				"signature_pair_key": 		signature_pair_key,
				"data_pair_key": 					data_pair_key,
				"signature_session_key":	signature_session_key,
				"session_key":						session_key_encrypt
			}
			self.cipher = Kuznechik(self.session_key)
			return message
		else:
			raise ValueError('Need public key from other client')

	def encrypt(self):
		if self.session_key is None or int(time.time()) - self.time_stamp > self.lifetime:
				print(f'The session key is either not generated or not valid')
		else:
			path = self.name.lower() + "/testdata"
			m = 16

			with open(path, 'r') as f:
				data = f.read()
			f.close()

			n = len(data)
			blks = [data[i:i+m] for i in range(0, n - n%m, m)]
			if n % m != 0:
				last = data[n-n%m:]
				for _ in range(m - n%m):
					last += '\0'
				blks.append(last)
			encrypt = b''.join([bytes(self.cipher.encrypt(blk.encode())) for blk in blks])

			path += "_encrypt"
			with open(path, 'wb') as f:
				f.write(encrypt)
			f.close()
			print("End encrypt")

	def encrypt(self):
		if self.session_key is None or int(time.time()) - self.time_stamp > self.lifetime:
				print(f'The session key is either not generated or not valid')
		else:
			path = self.name.lower() + "/testdata"
			m = 16

			with open(path, 'r') as f:
				data = f.read()
			f.close()

			n = len(data)
			blks = [data[i:i+m] for i in range(0, n - n%m, m)]
			if n % m != 0:
				last = data[n-n%m:]
				for _ in range(m - n%m):
					last += '\0'
				blks.append(last)
			encrypt = b''.join([bytes(self.cipher.encrypt(blk.encode())) for blk in blks])

			path += "_encrypt"
			with open(path, 'wb') as f:
				f.write(encrypt)
			f.close()
			print("End encrypt")
		
	def decrypt(self):
		if self.session_key is None or int(time.time()) - self.time_stamp > self.lifetime:
				print(f'The session key is either not generated or not valid')
		else:
			path = self.name.lower() + "/testdata_encrypt"
			m = 16

			with open(path, 'rb') as f:
				encrypt = f.read()
			f.close()
			n = len(encrypt)
			blks = [encrypt[i:i+m] for i in range(0, n-n%m, m)]
			decrypt = ''.join([''.join([chr(x) for x in self.cipher.decrypt(blk)]) for blk in blks])
			print(decrypt.encode())
			path = self.name.lower() + "/testdata_decrypt"
			with open(path, 'w') as f:
				f.write(decrypt)
			f.close()
			print("End decrypt")

	def send(self, code:str)->None:
		isWaitAnswer = True
		if code.lower() == "hello":
			message = {
				"type": "hello",
				"data": self.name}
		elif code.lower() == "get key":
			ind = "ALICE" if name == "BOB" else "BOB"
			message = {
				"type": "get key",
				"ind":	ind}
		elif code.lower() == "session":
			message = self.generate_session_message()
			isWaitAnswer = False
		elif code.lower() == "message":
			data = input("Input message: ")
			message = {
				"type": "message",
				"ind":	name,
				"data": data
			}
			isWaitAnswer = False
		elif code.lower() == "key": 
			if self.session_key is None or int(time.time()) - self.time_stamp > self.lifetime:
				print(f'The session key is either not generated or not valid')
			else:
				print(f'Session key is valid\n',
					f'Key: {self.session_key}\n',
					f'Time left: {self.lifetime - (int(time.time()) - self.time_stamp)}s')
			return False
		elif code.lower() == "encrypt": 
			self.encrypt()
			return False
		elif code.lower() == "decrypt": 
			self.decrypt()
			return False
		elif code.lower() == "close":
			message = {"type": "close"}
		elif code.lower() == "wait":
			answer = client.recv()
			client.parsing_msg(answer)
			return False
		else:
			message = {
				"type": "other",
				"data": code}
		self.sock.send(json.dumps(message).encode())
		return isWaitAnswer
			

	def recv(self)->str:
		return self.sock.recv(4096).decode()
	
	def check_session_message(self, data):
		time_stamp_encrypt 		= data["time_stamp"]
		signature_pair_key 		= data["signature_pair_key"]
		data_pair_key			 		= data["data_pair_key"]
		signature_session_key = data["signature_session_key"]
		session_key_encrypt		= data["session_key"]

		if self.other_public_key is not None:
			if verify_signature(self.other_public_key, signature_pair_key, data_pair_key):
				print("Pair key verify success.")
				pattern = r"lifetime:(\d+)private_key:(.+?)public_key:(.+)"
				match = re.match(pattern, data_pair_key)

				if match:
					self.lifetime	= int(match.group(1))
					private_key 	= match.group(2)
					public_key 		= match.group(3)
				else:
					print("data_pair_key is wrong format. Close session...")
					raise ValueError('data_pair_key is wrong format.')
				
				self.pair_private_key = serialization.load_pem_private_key(
					base64.b64decode(private_key),
					password=None, 
					backend=default_backend())
				self.pair_public_key = serialization.load_pem_public_key(
					base64.b64decode(public_key), 
					default_backend())
			else:
				print("Pair key verify fails. Close session...")
				raise ValueError('Pair key verify fails.')
			
			if verify_signature(self.pair_public_key, signature_session_key, session_key_encrypt):
				print("Session key verify success.")
				self.session_key = decrypt_RSA(self.self_private_key, session_key_encrypt)
			else:
				print("Session key verify fails. Close session...")
				raise ValueError('Session key verify fails.')
			
			self.time_stamp = int(decrypt_AES(self.session_key, time_stamp_encrypt.encode()))
			if int(time.time()) - self.time_stamp < self.lifetime:
				print("Session correct ")
				self.cipher = Kuznechik(self.session_key)
		else:
			raise ValueError('Need public key from other client')
	
	def parsing_msg(self, msg:str)->None:
		data = json.loads(msg)
		if data["type"] == "key":
			if verify_signature(self.trent_public_key, data["signature"], data["key"]):
				self.other_public_key = serialization.load_pem_public_key(
					base64.b64decode(data["key"]), 
					default_backend())
				print("Key verify success. Now you can generate session key.")
			else:
				print("Key verify fails. Close session...")
				raise ValueError('Key verify fails.')
		elif data["type"] == "message":
			print(f'Message from {data["ind"]}: {data["data"]}')
		elif data["type"] == "session":
			print(f'Start check session parameters')
			self.send("get key")
			answer = client.recv()
			client.parsing_msg(answer)
			self.check_session_message(data)
		elif data["type"] == "other":
			print("Server answer: ", data["data"])
		elif data["type"] == "error":
			print("Server error: ", data["data"])
			raise ValueError("Server error: " + data["data"])

	def __del__(self):
		print("End session")
		self.sock.close()

name  = input("Enter your name: ")
# name = "ALICE"
client = Client(name)

try:
	client.send("HELLO")
	answer = client.recv()
	client.parsing_msg(answer)

	msg = input("Enter code for send message: ")
	# msg = "get key"
	while msg != "exit" and msg != "quit":
		tmp = client.send(msg)
		if(tmp):
			answer = client.recv()
			client.parsing_msg(answer)
		msg = input("Enter code for send message: ")
	client.send("CLOSE")
except BaseException as err:
	client.send("CLOSE")
	print(f'something went wrong: {err}')