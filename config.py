import os

HOME_DIR = os.path.expanduser("~")
LLAMA_CPP_PATH = "/usr/local/bin/llama-server"
MODEL_DIR = os.path.join(HOME_DIR, "models")
CACHE_DIR = os.path.join(HOME_DIR, ".cache/llama")
SLOTS_DIR = "/tmp/llama_slots"

GPU_CARDS = [
    # Format: (sysfs_card_id, display_name, vulkan_device_id)
    ("card1", "RX 470", 1),    # card1 = RX 470 = Vulkan device 1
    ("card2", "RX 6600", 0)    # card2 = RX 6600 = Vulkan device 0
]
