import socket
import logging

from src.config import ARTNET_IP, ARTNET_PORT, ARTNET_UNIVERSE

class ArtNetCore:
    def __init__(self, target_ip: str = ARTNET_IP, port: int = ARTNET_PORT):
        self.target_ip = target_ip
        self.port = port
        self.default_universe = ARTNET_UNIVERSE
        self.is_playing = False
        self.output_enabled = False
        
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
        self.logger.info("ArtNetCore target configured: %s:%s universe=%s", self.target_ip, self.port, self.default_universe)

    def set_playing_state(self, state: bool):
        """Locks or unlocks the socket for the Player module."""
        self.is_playing = state
        self.logger.info(f"ArtNetCore is_playing state changed to: {self.is_playing}")

    def set_output_enabled(self, enabled: bool):
        """Enable or disable transmission to the physical Art-Net node."""
        self.output_enabled = enabled
        self.logger.info(f"ArtNetCore output_enabled changed to: {self.output_enabled}")

    def send_frame(self, dmx_data: bytearray, universe: int | None = None, source: str = "sender"):
        """
        Broadcasts a DMX frame.
        Blocks 'sender' or ad-hoc requests if the player is currently running.
        """
        # 1. State Verification (The Lock)
        if not self.output_enabled:
            self.logger.debug("Frame dropped: physical Art-Net output is disabled.")
            return

        if universe is None:
            universe = self.default_universe

        if self.is_playing and source not in {"player", "system"}:
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
        dynamic_header = universe.to_bytes(2, byteorder='little') + length.to_bytes(2, byteorder='big')

        # 4. Construct Final Packet and Send
        packet = self._static_header + dynamic_header + dmx_data
        
        try:
            self.sock.sendto(packet, (self.target_ip, self.port))
        except Exception as e:
            self.logger.error(f"Failed to send Art-Net packet: {e}")

# Singleton instance to be imported by sender.py and player.py
artnet_node = ArtNetCore()