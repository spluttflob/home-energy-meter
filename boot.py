# This file is executed on every boot (including wake-boot from deepsleep)

import mycerts
import network
from time import sleep_ms


def web_up():
    """
    Connect.
    @returns The network station, hopefully up and running
    """
    station = network.WLAN(network.STA_IF)

    if station.isconnected():
        print(f"Already connected as {station.ifconfig()[0]}")

    else:
        while True:
            try:
                print("Connecting to interwebs.", end='')
                station.active(True)
                station.connect(mycerts.ssid, mycerts.password)
                for count in range(60):
                    if not station.isconnected():
                        print('.', end='')
                        sleep_ms(1000)
                        count += 1
                    else:
                        print(f"connected as {station.ifconfig()[0]}")
                        return station
                
                # If we get here, we've timed out, so start over
                print("timeout; retry.")
                station.disconnect()
                station.active(False)
                sleep_ms(1000)

            except KeyboardInterrupt:
                station.disconnect()
                station.active(False)
                print("canceled.")


def web_down(station):
    """
    Shut down the web connection.
    """
    if station:
        station.disconnect()
        station.active(False)
    else:
        print("web_down(): No active WiFi station")

