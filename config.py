import os

HOME_DIR = os.path.expanduser("~")
LLAMA_CPP_PATH = "/usr/local/bin/llama-server"
MODEL_DIR = os.path.join(HOME_DIR, "models")
CACHE_DIR = os.path.join(HOME_DIR, ".cache/llama")
SLOTS_DIR = "/tmp/llama_slots"

GPU_CARDS = [
    ("card1", "RX 480"),
    ("card2", "RX 6600")
]
