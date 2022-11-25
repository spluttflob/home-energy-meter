"""
@file esp32_time.py
This file contains utilities to help an ESP32 keep real time using its RTC and
an NTP server on the Web.
"""

import ntptime
from utime import time, gmtime, localtime, sleep_ms

## The local time offset, which should be standard time. It's negative for
#  longitudes West of Greenwich, such as North America. Daylight time will be
#  accounted for by the @c time_now() function. 
LOCAL_OFFSET = -8


def daylight_time(dtime):
    """!
    Look at the day, month, and day of week to determine if we're on daylight
    or standard time. Use day of week numbers from time.localtime() in which
    Sunday is day 6 and Monday is day 0 of the week. Method copied from
    @c task_gps.cpp by the same author, using method found at
    @c https://stackoverflow.com/questions/5590429/ ...
    @c calculating-daylight-saving-time-from-only-date/5590518
    with adjustments for @c TimeLib not using same weekday numbers as @c utime.

    @b FEATURE: This method doesn't account for the way Daylight Time changes
    at 2AM - 3AM rather than at midnight.

    @param dtime Iterable containing date and time in time.localtime() format
    @returns @c True if we're in daylight time and @c False if in standard time
    """
    day = dtime[2]
    month = dtime[1]
    weekday = dtime[6]

    # January, February, and December are entirely standard time
    if month < 3 or month > 11:
        return False

    # April through October are entirely daylight time
    if month > 3 and month < 11:
        return True

    # Find the day of the month of the previous Sunday; it's today if today is
    # Sunday
    previousSunday = day - ((weekday + 1) % 7)

    # In March, we are daylight if previous sunday was on or after the 8th
    if month == 3:
        return previousSunday >= 8 

    # In november we must be before the first sunday to be daylight time.
    # That means the previous sunday must be before the 1st
    return previousSunday <= 0


def sync_time():
    """
    Use NTP time to synchronize the RTC to a good approximation of real time.
    """
    print("Getting time from NTP server...", end='')

    while True:
        try:
            ntptime.settime()         # server="pool.ntp.org", timezone=-8,
        except OSError:
            print(".", end='')
            sleep_ms(1000)
        else:
            break

    print(f"local date is {date_str()} and local time is {time_str()}.")


def time_now():
    """
    Get time corrected for the timezone and Daylight Savings.
    """
    local_offset = LOCAL_OFFSET
    if daylight_time(gmtime(time())):
        local_offset += 1
    return localtime(time() + local_offset * 3600)


def minutes_now():
    """
    Find out how many minutes into today we currently are.
    """
    now = time_now()
    return now[3] * 60 + now[4]


def time_str():
    """
    Get a string containing the local time.
    """
    now = time_now()
    return f"{now[3]:02d}:{now[4]:02d}:{now[5]:02d}"


def date_str():
    """
    Get a string containing the current local date.
    """
    now = time_now()
    return f"{now[0]}-{now[1]:02d}-{now[2]:02d}"

