#!/usr/bin/python
import socket, threading
import base64, json, logging

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
		logging.basicConfig(filename='trent/system.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s\n')
		logging.info("Server start")
		
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
				data = json.loads(data)
				logging.info(f'Get data from {addr}:\n{data}')
				if data["type"] == "hello":
					print("debug: hello code")
					if data["data"] == "ALICE":
						self.alice_socket = client_socket
						message = {
							"type": "message",
							"ind":	"Server",
							"data":	f'Hi Alice'
						}
						self.alice_socket.send(json.dumps(message).encode())
						logging.info(f'Send data to ALICE:\n{message}')
					elif data["data"] == "BOB":
						self.bob_socket = client_socket
						message = {
							"type": "message",
							"ind":	"Server",
							"data":	f'Hi Bob'
						}
						self.bob_socket.send(json.dumps(message).encode())
						logging.info(f'Send data to BOB:\n{message}')
					else:
						print("Unknown user!")
						message = {
							"type": "error",
							"data": "Unknown user!"}
						logging.error(f'Unknown user for hello: {data["data"]}')
						client_socket.send(json.dumps(message).encode())
						return
				elif data["type"] == "get key":
					print("debug: get key code")
					if data["ind"] == "BOB":
						public_key = self.bob_public_key
						from_ = "ALICE" 
					elif data["ind"] == "ALICE":
						public_key = self.alice_public_key
						from_ = "BOB"
					else:
						print("Unknown user!")
						message = {
							"type": "error",
							"data": "Unknown user!"}
						client_socket.send(json.dumps(message).encode())
						logging.error(f'Unknown user for get key: {data["ind"]}')
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
					logging.info(f'Send data to {from_}:\n{message}')
				elif data["type"] == "message" or data["type"] == "session":
					print("debug: message or session code")
					if data["ind"] == "ALICE":
						self.bob_socket.send(json.dumps(data).encode())
						logging.info(f'Send data to {data["ind"]}:\n{message}')
					elif data["ind"] == "BOB":
						self.alice_socket.send(json.dumps(data).encode())
						logging.info(f'Send data to {data["ind"]}:\n{message}')
					else:
						logging.error(f'Unknown sender!!')
				elif data["type"] == "close":
					print("debug: close code")
					if client_socket == self.alice_socket:
						self.alice_socket.close()
						self.alice_socket = None
						logging.info(f'ALICE close session')
					else:
						self.bob_socket.close()
						self.bob_socket = None
						logging.info(f'BOB close session')
				elif data["type"] == "other":
					print("debug: other code")
					message = {
						"type": "other",
						"data": f'I KNOW ALL ABOUT YOU {addr}'
					}
					client_socket.send(json.dumps(message).encode())
					logging.info(f'Unknown code from {addr}')

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
		logging.info(f'Close server')

server = Server()