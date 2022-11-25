"""
@file main.py
Something to read a couple of current transformers to see how much power we're
using.  This is an ESP32 version which is designed to use a simple custom PCB
that has 10 ohm current-to-voltage resistors which connect to 100A --> 50mV
current transformers. 

@author JR Ridgely
@date   2022-Sep-16 Modified for new custom boards
@copyright (c) 2022 by JR Ridgely and released under the Lesser GNU Public
        License Version 2. 
"""

import gc
import math
import socket
import uasyncio as asyncio
from machine import ADC, Pin
from mqtt_as import MQTTClient, config
from sys import platform, implementation
from utime import sleep_ms, ticks_us, ticks_diff
# from micropython import alloc_emergency_exception_buf

import esp32_time
import timed_adcs


## The pin used for the phase A ADC: 33 for breadboard and MegaWatt4
PH_A_PIN = 33

## The pin used for the phase B ADC: 35 for breadboard, 32 for MegaWatt4
PH_B_PIN = 32

## The pin used for the extra CT: 35 for the MegaWatt4
PH_X_PIN = 35

# GPIO pin 32 is connected to the reference voltage divider on breadboard only

## The MQTT topic to which we're broadcasting energy usage on phases A and B
MQTT_TOPIC = b"travisty/energy/main"

## The MQTT topic for the extra channel
EXTRA_TOPIC = b"travisty/energy/extra"

## The number of minutes between transmitted readings
MIN_PER_READING = 2

## The size of the buffer into which to read the ADC
BUF_SIZE = 1000

## The rate in Hertz at which to read the ADC for finding RMS voltage. At 6000
#  Hz, we get 100 readings per wave, which seems pretty generous
READ_RATE = 6000

## The MQTT server ("broker") to which messages are sent
MQTT_SERVER = '192.168.2.87'

## The AC voltage. We don't have measurement capability now, so assume ~120V
AC_VOLTAGE = 120.0

## The current time and power levels in a string; it's shared between tasks
current_power = None

## The extra power measurement in a string; it's shared between tasks
current_extra = None


async def measure_task():
    """ Get measurements periodically.
    """
    global current_power, current_extra

    # Create ADCs for the pins connected to current transformers A and B
    timedADCs = timed_adcs.Timed_ADCs(ADC(Pin(PH_A_PIN), atten=ADC.ATTN_11DB),
                                      ADC(Pin(PH_B_PIN), atten=ADC.ATTN_11DB),
                                      ADC(Pin(PH_X_PIN), atten=ADC.ATTN_11DB),
                                      READ_RATE,
                                      BUF_SIZE)

    # Watch what minute it is to decide when to record and reset the averages
    next_minute = esp32_time.minutes_now() + 1

    # Keep track of what day it is to detect midnight
    today = esp32_time.time_now()[2]
    print(f"Beginning on day {today} of time {esp32_time.time_now()}.")

    # For averaging sets of readings from phases A, B, and Extra
    sum_amps = [0.0, 0.0, 0.0]
    count = 0

    while True:
        timedADCs.read_timed()
        while not timedADCs.ready:
            await asyncio.sleep_ms(1)
        amps = timedADCs.get_amps_RMS()
#         print(f"{esp32_time.time_str()},{amps[0]:.1f},{amps[1]:.1f}")
        sum_amps[0] += amps[0]
        sum_amps[1] += amps[1]
        sum_amps[2] += amps[2]
        count += 1

        # Check if it's time to compute and save average power values
        if esp32_time.minutes_now() >= next_minute:
            # Get readings for the main phases A and B and the extra phase
            averages = [(sum_amps[i] / count) * AC_VOLTAGE for i in range(3)]
            sum_amps = [0.0, 0.0, 0.0]
            count = 0
            next_minute += MIN_PER_READING
            # Put current power usage into a string. When it has been sent to
            # the MQTT broker, the string will be replaced with None
            current_power = \
                f"{esp32_time.time_str()},{averages[0]:.2f},{averages[1]:.2f}"
            print(current_power, end=' ')
            current_extra = f"{esp32_time.time_str()},{averages[2]:.2f}"
            print(current_extra, end='')
            gc.collect()

        await asyncio.sleep_ms(1000)


def callback(topic, msg, retained):
    """
    MQTT callback, not used (I think).
    """
    print((topic, msg, retained))


async def conn_han(client):
    """
    Connection handler?  Something like that.
    """
    await client.subscribe('foo_topic', 1)


async def mqtt_task(client):
    """
    Task that sends MQTT messages about power usage.
    @param client An MQTT client of class MQTTClient which has been set up
    """
    global current_power, current_extra

    print('Starting mqtt_task()...', end='')
    await client.connect()
    print("connected.")
    n = 0
    while True:
        await asyncio.sleep(5)

        if current_power:
            print(f"Sending '{current_power}'")
            # If WiFi is down the following will pause for the duration.
            # Parameters are topic, data of topic, quality of service
            await client.publish(MQTT_TOPIC,
                                 current_power.encode(),
                                 qos = 1)
            current_power = None

        if current_extra:
            await client.publish(EXTRA_TOPIC,
                                 current_extra.encode(),
                                 qos = 1)
            current_extra = None

        else:
            print('-', end='')


async def check_WiFi_task(station):
    """
    Check if the WiFi is still connected. If not, try to reconnect using the
    @c web_up() and @c web_down() functions in @c boot.py.
    """
    while True:
        await asyncio.sleep_ms(60000)          # Check every minute

        if not station.isconnected():
            web_down(station)
            await asyncio.sleep_ms(1000)
            web_up()
        else:
            print("WiFi OK")


async def main(mqtt_client, station):
    """!
    Get the task functions running, then twiddle thumbs until Control-C'ed.
    @param mqtt_client An object of class MQTTClient to be passed to MQTT task
    @param station The WLAN station which should be talking over WiFi
    """
    asyncio.create_task(measure_task())
    asyncio.create_task(mqtt_task(mqtt_client))
    asyncio.create_task(check_WiFi_task(station))

    while True:
        await asyncio.sleep_ms(1000)


if __name__ == "__main__":

#     # Allocate space for interrupt callback complaints
#     alloc_emergency_exception_buf(128)

    # Get the network going and synchronize the RTC
    net_station = web_up()
    esp32_time.sync_time()

    # Set up the MQTT client object to be passed to the MQTT task
    config['ssid'] = mycerts.ssid
    config['wifi_pw'] = mycerts.password
    config['subs_cb'] = callback
    config['connect_coro'] = conn_han
    config['server'] = MQTT_SERVER
    MQTTClient.DEBUG = True             # Optional: print diagnostic messages
    mqtt_client = MQTTClient(config)

    try:
        asyncio.run(main(mqtt_client, net_station))

    except KeyboardInterrupt:
        print("Control-C ", end='')

    finally:
        asyncio.new_event_loop()             # Clear retained state
        web_down(net_station)
        print("Exiting")

