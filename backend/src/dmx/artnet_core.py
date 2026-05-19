import socket
import struct
import logging

class ArtNetCore:
    def __init__(self, target_ip="<broadcast>", port=6454):
        self.target_ip = target_ip
        self.port = port
        self.is_playing = False
        
        # Setup UDP Socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        # Pre-compile the static part of the Art-Net Header
        # ID ("Art-Net\x00") [8 bytes]
        # OpCode (OpDmx 0x5000 - Little Endian) [2 bytes]
        # Protocol Version (14 - Big Endian) [2 bytes]
        # Sequence (0) [1 byte]
        # Physical (0) [1 byte]
        self._static_header = b'Art-Net\x00\x00\x50\x00\x0e\x00\x00'
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("ArtNetCore")

    def set_playing_state(self, state: bool):
        """Locks or unlocks the socket for the Player module."""
        self.is_playing = state
        self.logger.info(f"ArtNetCore is_playing state changed to: {self.is_playing}")

    def send_frame(self, dmx_data: bytearray, universe: int = 0, source: str = "sender"):
        """
        Broadcasts a DMX frame.
        Blocks 'sender' or ad-hoc requests if the player is currently running.
        """
        # 1. State Verification (The Lock)
        if self.is_playing and source != "player":
            # Silently drop the packet to prevent UI/API errors, 
            # but log it for debugging if needed.
            self.logger.debug("Frame dropped: Player is active. Ad-hoc updates are locked.")
            return

        # 2. Payload Validation
        # DMX payloads must be even, and max 512 bytes
        length = len(dmx_data)
        if length > 512:
            dmx_data = dmx_data[:512]
            length = 512
        elif length % 2 != 0:
            dmx_data += b'\x00'
            length += 1

        # 3. Assemble Dynamic Header (Universe & Length)
        # Universe [2 bytes Little Endian]
        # Length [2 bytes Big Endian]
        dynamic_header = struct.pack('<H >H', universe, length)

        # 4. Construct Final Packet and Send
        packet = self._static_header + dynamic_header + dmx_data
        
        try:
            self.sock.sendto(packet, (self.target_ip, self.port))
        except Exception as e:
            self.logger.error(f"Failed to send Art-Net packet: {e}")

# Singleton instance to be imported by sender.py and player.py
artnet_node = ArtNetCore()