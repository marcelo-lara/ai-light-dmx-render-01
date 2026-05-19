from .artnet_core import artnet_node

def start_show():
    # 1. Lock the core
    artnet_node.set_playing_state(True)
    
    # 2. High-resolution 50FPS streaming loop
    for frame_data in pre_rendered_buffer:
        artnet_node.send_frame(frame_data, universe=0, source="player")
        time.sleep(0.02) # (Simplified timing)
        
    # 3. Unlock the core when finished
    artnet_node.set_playing_state(False)