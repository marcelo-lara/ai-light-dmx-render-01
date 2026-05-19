from .artnet_core import artnet_node

def test_fixture(dmx_data):
    # This will automatically be dropped by artnet_core 
    # if a song is currently playing.
    artnet_node.send_frame(dmx_data, universe=0, source="sender")