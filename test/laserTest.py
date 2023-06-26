import RPi.GPIO as gpio
from time import sleep

LASER = 14
gpio.setmode(gpio.BCM)
gpio.setup(LASER, gpio.OUT)

gpio.output(LASER, gpio.HIGH)
print("ON")

sleep(3)

gpio.output(LASER, gpio.LOW)
print("OFF")

gpio.cleanup(LASER)
