import time

chunks = []

while True:
    chunks.append(" " * (256 * 1024 * 1024))
    time.sleep(0.5)