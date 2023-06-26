from picamera import PiCamera
from time import sleep

PATH = "/home/leo/laserCam/test"
FILE = "testImage.jpg"

cam = PiCamera()

cam.start_preview()

print("Say cheese...")
sleep(2)

cam.capture(f"{PATH}/{FILE}")

print("*click*")
print(f"Wrote \"{FILE}\" to {PATH}")

cam.stop_preview()
cam.close()
