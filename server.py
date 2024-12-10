#!/usr/bin/python
import socket, threading
import base64, json

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from Crypt import open_key, sign_data

class Server:
	sock : socket.socket
	alice_socket: socket.socket
	bob_socket: socket.socket
	self_private_key: rsa.RSAPrivateKey
	self_public_key: 	rsa.RSAPublicKey
	alice_public_key: rsa.RSAPublicKey
	bob_public_key:		rsa.RSAPublicKey 
	HOST, SERV_PORT = '127.0.0.1', 65432
	threads = []

	def __init__(self):
		self.self_private_key = open_key("private", "trent/trent_private")
		self.self_public_key 	= open_key("public", 	"trent/trent_public")
		self.alice_public_key = open_key("public", 	"trent/alice_public")
		self.bob_public_key 	= open_key("public", 	"trent/bob_public")
		self.alice_socket = None
		self.bob_socket = None
		try:
			self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self.sock.bind((self.HOST, self.SERV_PORT))
			self.sock.listen()
			while True:
				conn, addr = self.sock.accept()
				thread = threading.Thread(target=Server.on_client, args=(self, conn, addr))
				self.threads.append((thread, conn))
				thread.start()
		except:
			for thread, conn in self.threads:
				conn.close()
				thread.join()
			self.sock.close()
		
	def on_client(self, client_socket:socket.socket, addr):
		try:
			while True:
				data = b''
				while len(data) < 1:
					data = client_socket.recv(4096).decode()

				print(f'debug: from {addr}')
				data = json.loads(data)
				if data["type"] == "hello":
					print("debug: hello code")
					if data["data"] == "ALICE":
						self.alice_socket = client_socket
						self.alice_socket.send(f'Hi Alice.\n'.encode())
					elif data["data"] == "BOB":
						self.bob_socket = client_socket
						self.bob_socket.send(f'Hi Bob.\n'.encode())
					else:
						print("Unknown user!")
						return
				elif data["type"] == "get key":
					print("debug: get key code")
					if data["ind"] == "BOB":
						public_key = self.bob_public_key
					elif data["ind"] == "ALICE":
						public_key = self.alice_public_key
					else:
						print("Unknown user!")
						message = {
							"type": "error",
							"data": "Unknown user!"}
						client_socket.send(json.dumps(message).encode())
						return
					
					key_b64 = base64.b64encode(public_key.public_bytes(
							encoding=serialization.Encoding.PEM, 
							format=serialization.PublicFormat.SubjectPublicKeyInfo)).decode()
					signature = sign_data(self.self_private_key, key_b64)
					message = {
						"type": 			"key",
						"signature": 	signature,
						"key":  			key_b64
					}
					client_socket.send(json.dumps(message).encode())
				elif data["type"] == "message" or data["type"] == "session":
					print("debug: message or session code")
					if data["ind"] == "ALICE":
						self.bob_socket.send(json.dumps(data).encode())
					elif data["ind"] == "BOB":
						self.alice_socket.send(json.dumps(data).encode())
				elif data["type"] == "close":
					print("debug: close code")
					if client_socket == self.alice_socket:
						self.alice_socket.close()
						self.alice_socket = None
					else:
						self.bob_socket.close()
						self.bob_socket = None
				elif data["type"] == "other":
					print("debug: other code")
					message = {
						"type": "other",
						"data": f'I KNOW ALL ABOUT YOU {addr}'
					}
					client_socket.send(json.dumps(message).encode())

		except:
			client_socket.close()

	def __del__(self):
		for thread, conn in self.threads:
			conn.close()
			thread.join()
		if self.alice_socket != None:
			self.alice_socket.close()
		if self.bob_socket != None:
			self.bob_socket.close()
		self.sock.close()

server = Server()