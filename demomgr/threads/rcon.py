
import queue
import socket
import struct

from demomgr.threads._threadsig import THREADSIG
from demomgr.threads._base import _StoppableBaseThread

AUTH = 3
AUTH_RESPONSE = 2
EXECCOMMAND = 2
RESPONSE_VALUE = 0

MAKE_SURE = "Is TF2 running with -usercon and net_start?"

class RCONPacketSizeError(ValueError):
	pass

class RCONPacket:
	def __init__(self, id_, type_, body):
		self.size = len(body) + 10
		self.id = id_
		self.type = type_
		self.body = body

	def as_bytes(self):
		return struct.pack(
			f"<iii{len(self.body)}scc",
			self.size,
			self.id,
			self.type,
			self.body,
			b"\x00",
			b"\x00",
		)

class RCONThread(_StoppableBaseThread):
	"""
	Thread for establishing a RCON connection to a game and sending
	a command.
	The thread is designed to run continuously and receive commands
	as encoded strings through an input queue.
	If it fails at any point, it will disconnect.

	Sent to the output queue:
		SUCCESS(0) when the stoprequest is set after the thread has
				connected to the game.

		FAILURE(0) on any socket operation failure.

		ABORTED(0) when the stoprequest is set before the thread has
				connected to the game.

		CONNECTED(0) when the thread successfully connects to the game.

		INFO_IDX_PARAM(2) for text to display (#TODO issue #31)
			- Slot index to display the text on.
			- Text to display.
	"""
	def __init__(self, queue_in, queue_out, password, port):
		"""
		Thread takes an input queue, an output queue and the following args:
			password <Str>: Password to authenticate with the game.
			port <Int>: Port the game will be open under.
		"""
		self.password = password
		self.port = port

		self._socket = None

		super().__init__(queue_in, queue_out)

	def run(self):
		try:
			encoded_pwd = self.password.encode("utf-8")
		except UnicodeError:
			self.queue_out_put(THREADSIG.FAILURE)
			return

		self.queue_out_put(THREADSIG.INFO_IDX_PARAM, 0, f"Connecting to TF2 (port {self.port})...")
		try:
			potential_targets = socket.getaddrinfo(socket.getfqdn(), self.port, socket.AF_INET)
		except OSError as error:
			self.queue_out_put(
				THREADSIG.INFO_IDX_PARAM,
				0,
				f"Obscure error getting machine address: {error}"
			)
			self.queue_out_put(THREADSIG.FAILURE)
			return

		for idx, value in enumerate(potential_targets):
			af, type_, proto, _, addr = value
			self._socket = error = None
			self.queue_out_put(
				THREADSIG.INFO_IDX_PARAM,
				0,
				f"Connecting to candidate {idx}/{len(potential_targets) - 1} (port {self.port})"
			)

			try:
				self._socket = socket.socket(af, type_, proto)
				self._socket.settimeout(3)
				self._socket.connect(addr)
			except OSError as e:
				error = e
				if self._socket is not None:
					self._socket.close()

			if self.stoprequest.is_set():
				self.queue_out_put(THREADSIG.ABORTED)
				return

			if error is None:
				break # Success

		if error is not None:
			self.queue_out_put(
				THREADSIG.INFO_IDX_PARAM, 0,
				f"Failure establishing connection. {MAKE_SURE}: {error}"
			)
			self.queue_out_put(THREADSIG.FAILURE)
			return

		if self.stoprequest.is_set():
			self.__stopsock(THREADSIG.ABORTED)
			return

		self.queue_out_put(THREADSIG.INFO_IDX_PARAM, 0, "Connected to TF2")
		self.queue_out_put(THREADSIG.INFO_IDX_PARAM, 1, "Authenticating...")
		try:
			authpacket = RCONPacket(622521, AUTH, encoded_pwd)
		except RCONPacketSizeError:
			self.queue_out_put(THREADSIG.INFO_IDX_PARAM, 1, "Password way too large.")
			self.__stopsock(THREADSIG.FAILURE)
			return

		try:
			self.send_packet(authpacket)
		except Exception as e:
			self.queue_out_put(
				THREADSIG.INFO_IDX_PARAM,
				1,
				f"Failure sending auth packet. {MAKE_SURE}: {e}"
			)
			self.__stopsock(THREADSIG.FAILURE)
			return

		if self.stoprequest.is_set():
			self.__stopsock(THREADSIG.ABORTED)
			return

		try:
			authresponse = self.read_packet() #SERVERDATA_RESPONSE_VALUE
			if authresponse.id != 622521:
				self.queue_out_put(THREADSIG.INFO_IDX_PARAM, 1, "Auth response id mismatch.")
				self.__stopsock(THREADSIG.FAILURE)
				return

			authresponse = self.read_packet() #SERVERDATA_AUTH_RESPONSE
			if authresponse.id == -1:
				self.queue_out_put(THREADSIG.INFO_IDX_PARAM, 1, "Bad password.")
				self.__stopsock(THREADSIG.FAILURE)
				return

		except Exception as e:
			self.queue_out_put(
				THREADSIG.INFO_IDX_PARAM,
				1,
				f"Error while authenticating. {MAKE_SURE}: {e}"
			)
			self.__stopsock(THREADSIG.FAILURE)
			return

		if self.stoprequest.is_set():
			self.__stopsock(THREADSIG.ABORTED)
			return

		self.queue_out_put(THREADSIG.CONNECTED)
		self.queue_out_put(THREADSIG.INFO_IDX_PARAM, 1, "Successfully authenticated.")

		while True:
			try:
				command = self.queue_inp.get(True, 0.1)
			except queue.Empty:
				if self.stoprequest.is_set():
					self.__stopsock(THREADSIG.SUCCESS)
					return
				continue

			self.queue_out_put(THREADSIG.INFO_IDX_PARAM, 2, "Sending command...")
			try:
				self.send_packet(RCONPacket(1337, EXECCOMMAND, command))
				# NOTE: There may be an infinite wait here where the thread can not be stopped
				resp = self.read_packet()
				if resp.id != 1337:
					self.queue_out_put(THREADSIG.INFO_IDX_PARAM, 2, "Bad command response id.")
					self.__stopsock(THREADSIG.FAILURE)
					return
				self.queue_out_put(THREADSIG.INFO_IDX_PARAM, 2, "Command sent!")
			except Exception as e:
				self.queue_out_put(THREADSIG.INFO_IDX_PARAM, 2, f"Error while sending command: {e}")
				self.__stopsock(THREADSIG.FAILURE)
				return

	def read_packet(self):
		"""
		Read an outstanding rcon packet. Am too lazy for multi-package support,
		so it's not supported.
		"""
		packet_header = self._socket.recv(12)

		packet_size, packet_id, packet_type = struct.unpack("<iii", packet_header)
		body = self._socket.recv(packet_size - 8)
		return RCONPacket(packet_id, packet_type, body)

	def send_packet(self, packet):
		"""
		Sends bytes to the socket.
		"""
		self._socket.sendall(packet.as_bytes())

	def __stopsock(self, signal):
		if self._socket is not None:
			self._socket.close()
			self._socket = None

		self.queue_out_put(signal)
