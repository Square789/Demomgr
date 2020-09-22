
import os
import queue
import socket
socket.setdefaulttimeout(10)
import struct

from demomgr.threads._threadsig import THREADSIG
from demomgr.threads._base import _StoppableBaseThread
from demomgr import constants as CNST

class RCONPacketSizeError(ValueError):
	pass

AUTH = 3
AUTH_RESPONSE = 2
EXECCOMMAND = 2
RESPONSE_VALUE = 0

class RCONPacket:
	def __init__(self, id_, type_, body):
		self.size = len(body) + 10
		self.id = id_
		self.type = type_
		self.body = body

	def as_bytes(self):
		return struct.pack(f"<iii{len(self.body)}scc",
			self.size,
			self.id,
			self.type,
			self.body,
			b"\x00",
			b"\x00"
		)

class RCONThread(_StoppableBaseThread):
	"""
	Thread for establishing a RCON connection to a game and sending
	a command.
	"""
	def __init__(self, queue_out, command, password, port):
		"""
		Thread takes an output queue and as the following args:
			command <Str>: Command to send to the game.
			password <Str>: Password to authenticate with the game.
			port <Int>: Port the game will be open under.
		"""
		self.command = command
		self.password = password
		self.port = port

		super().__init__(None, queue_out)

	def run(self):
		try:
			encoded_pwd = self.password.encode("utf-8")
			encoded_cmd = self.command.encode("utf-8")
		except UnicodeError:
			self.queue_out_put(THREADSIG.FAILURE); return

		self.queue_out_put(THREADSIG.INFO_IDX_PARAM, 0, "Connecting to TF2...")
		try:
			self._socket = socket.create_connection((socket.getfqdn(), self.port), 3)
		except socket.timeout:
			self.queue_out_put(THREADSIG.INFO_IDX_PARAM, 0, "Timeout. Is TF2 running with -usercon?")
			self.queue_out_put(THREADSIG.FAILURE); return
		except Exception as e:
			self.queue_out_put(THREADSIG.INFO_IDX_PARAM, 0, "Failure establishing connection.")
			self.queue_out_put(THREADSIG.FAILURE); return

		if self.stoprequest.is_set():
			self.queue_out_put(THREADSIG.ABORTED)
			self.__failurestop(); return

		self.queue_out_put(THREADSIG.INFO_IDX_PARAM, 0, "Connected to TF2")
		self.queue_out_put(THREADSIG.INFO_IDX_PARAM, 1, "Authenticating...")
		try:
			authpacket = RCONPacket(622521, AUTH, encoded_pwd)
		except RCONPacketSizeError:
			self.queue_out_put(THREADSIG.INFO_IDX_PARAM, 1, "Failure building auth packet.")
			self.__failurestop(); return

		try:
			self.send_packet(authpacket)
		except Exception as e:
			self.queue_out_put(THREADSIG.INFO_IDX_PARAM, 1, "Failure sending auth packet.")
			self.__failurestop(); return

		if self.stoprequest.is_set():
			self.queue_out_put(THREADSIG.ABORTED)
			self.__failurestop(); return

		try:
			authresponse = self.read_packet() #SERVERDATA_RESPONSE_VALUE
			if authresponse.id != 622521:
				self.queue_out_put(THREADSIG.INFO_IDX_PARAM, 1, "Auth response id mismatch.")
				self.__failurestop(); return

			authresponse = self.read_packet() #SERVERDATA_AUTH_RESPONSE
			if authresponse.id == -1:
				self.queue_out_put(THREADSIG.INFO_IDX_PARAM, 1, "Bad password.")
				self.__failurestop(); return

		except Exception as e:
			self.queue_out_put(THREADSIG.INFO_IDX_PARAM, 1, "Error while authenticating.")
			self.__failurestop(); return

		if self.stoprequest.is_set():
			self.queue_out_put(THREADSIG.ABORTED)
			self.__failurestop(); return

		self.queue_out_put(THREADSIG.INFO_IDX_PARAM, 1, "Successfully authenticated.")
		self.queue_out_put(THREADSIG.INFO_IDX_PARAM, 2, "Sending command...")
		try:
			command_req = RCONPacket(1337, EXECCOMMAND, encoded_cmd)
			self.send_packet(command_req)
		except Exception as e:
			self.queue_out_put(THREADSIG.INFO_IDX_PARAM, 1, "Error while sending command.")
			self.__failurestop(); return

		self.queue_out_put(THREADSIG.INFO_IDX_PARAM, 2, "Command sent!")
		self._socket.close()
		self.queue_out_put(THREADSIG.SUCCESS)

	def read_packet(self):
		"""
		Read an outstanding rcon packet. Am too lazy for multi-package support,
		so it's not supported.
		"""
		packet_header = self._socket.recv(12)

		# print("HEADER :", packet_header)
		packet_size, packet_id, packet_type = struct.unpack("<iii", packet_header)
		body = self._socket.recv(packet_size - 8)
		# print("message received")
		# print("RCVD:   ", _.as_bytes())
		return RCONPacket(packet_id, packet_type, body)

	def send_packet(self, packet):
		"""
		Sends bytes to the socket.
		"""
		# print("SENDING:", packet.as_bytes())
		self._socket.sendall(packet.as_bytes())

	def __failurestop(self):
		self.socket.close()
		self.queue_out_put(THREADSIG.FAILURE)
