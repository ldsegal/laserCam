#!/bin/bash
cpu=$(</sys/class/thermal/thermal_zone0/temp)
echo "GPU $(/usr/bin/vcgencmd measure_temp)"
echo "CPU temp=$((cpu/1000))'C"