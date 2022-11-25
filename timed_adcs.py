"""
@file timed_adcs.py
This file contains a class which runs a couple of ADCs quickly to measure the
RMS current in two phases of a split-phase power system...such as in a home.
"""

import math
from array import array
from machine import Timer
from gc import collect, mem_free


## The conversion from microvolts to amps in the current transformers. This
#  assumes we're using ADC.read_uv() to get an ADC reading.
#  100A --> 50mA --10 ohms--> 0.50V == 500000uV
UV_TO_AMPS = 100 / 500000


class Timed_ADCs:
    """
    A quick and dirty recreation of the ADC.read_timed() method with 3 channels
    for a split-phase current transformer pair and one extra transformer.
    """

    def __init__(self, adc_A, adc_B, adc_X, rate, buf_size, timer_num=-1):
        """
        Create a handy ADC reader.
        @param adc_A The ADC object for channel A, created as a machine.ADC
        @param adc_B The ADC for channel B
        @param adc_X The ADC for the extra channel
        @param rate The number of readings per second
        @param buf_size The size of the buffers for collected data
        @param timer_num The number of the hardware timer to use; uses a virtual
               timer by default
        """
        self.adcA = adc_A
        self.adcB = adc_B
        self.adcX = adc_X
        self.rate = rate
        self.buf_size = buf_size

        # There have been some memory allocation problems; clean up the heap
        # before allocating memory for these arrays
        collect()
        print(f"Allocating for 3x{buf_size} arrays, {mem_free()} bytes free")
        self.bufA = array('I', 0 for x in range(buf_size))
        self.bufB = array('I', 0 for x in range(buf_size))
        self.bufX = array('I', 0 for x in range(buf_size))
        self.timer = Timer(timer_num)
        self.index = 0
        self.ready = False


    def adc_callback(self, dummy):
        """
        Callback which reads the ADC and stores one reading.
        @param dummy Some internal thing which we ignore
        """
        if self.index >= self.buf_size:
            self.timer.deinit()
            self.ready = True
        else:
            self.bufA[self.index] = self.adcA.read_uv()
            self.bufB[self.index] = self.adcB.read_uv()
            self.bufX[self.index] = self.adcX.read_uv()
            self.index += 1


    def read_timed(self):
        """
        Begins reading an ADC a bunch of times at a given rate. The reads are
        controlled by a timer with a callback, so we just start the timer here.
        """
        self.ready = False
        self.index = 0
        self.timer.init(freq=self.rate, mode=Timer.PERIODIC,
                        callback=self.adc_callback)


    def get_RMS(self):
        """
        Compute the RMS values of the data sets in the current reading buffers,
        finding the averages first.
        """
        avgA = sum(self.bufA) / self.buf_size
        avgB = sum(self.bufB) / self.buf_size
        avgX = sum(self.bufX) / self.buf_size
        sumA = 0
        sumB = 0
        sumX = 0
        for item in self.bufA:
            diffy = item - avgA
            sumA += diffy * diffy
        for item in self.bufB:
            diffy = item - avgB
            sumB += diffy * diffy
        for item in self.bufX:
            diffy = item - avgX
            sumX += diffy * diffy
        return (math.sqrt(sumA / self.buf_size),
                math.sqrt(sumB / self.buf_size),
                math.sqrt(sumX / self.buf_size))


    def get_amps_RMS(self):
        """
        Compute and return the AC RMS amperage measured by each current sensor.
        The factor @c UV_TO_AMPS is used to convert measured microvolts to amps.
        @return A two-tuple of currents, one for each phase
        """
        uv_rms = self.get_RMS()
        return (uv_rms[0] * UV_TO_AMPS, uv_rms[1] * UV_TO_AMPS,
                uv_rms[2] * UV_TO_AMPS)


    def __repr__(self):
        """
        Print the Timed ADC object, showing its parameters and data.
        """
        astring = (f"Timed ADC: {self.buf_size} pts, {self.rate} Hz\n" +
                   f"  A {sum(self.bufA) / self.buf_size} avg, " +
                   f"    {self.get_RMS()} RMS, " +
                   f"    {", ".join([str(x) for x in self.bufA[:3]])}..."
                   )
        return astring

