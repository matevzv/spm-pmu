#!/usr/bin/env python3

import socketserver
import serial
import sys
import io

from time import sleep
from datetime import datetime
from synchrophasor.frame import *
from pmu import Pmu

seconds_in_week = 604800
gps_to_unix = 315964800

ser = serial.Serial("/dev/ttyMFD1",
                    baudrate=115200,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_ODD,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=1)

sio = io.TextIOWrapper(io.BufferedRWPair(ser, ser))

pmu_id = 1410

header = HeaderFrame(pmu_id, 'JSI SPM PMU')

cfg2 = ConfigFrame2(pmu_id,  # PMU_ID
                   1000000,  # TIME_BASE
                   1,  # Number of PMUs included in data frame
                   "Random Station",  # Station name
                   1410,  # Data-stream ID(s)
                   (True, True, True, True),  # Data format - POLAR; PH - REAL; AN - REAL; FREQ - REAL;
                   3,  # Number of phasors
                   1,  # Number of analog values
                   1,  # Number of digital status words
                   ["VA", "VB", "VC", "ANALOG1", "BREAKER 1 STATUS",
                    "BREAKER 2 STATUS", "BREAKER 3 STATUS", "BREAKER 4 STATUS", "BREAKER 5 STATUS",
                    "BREAKER 6 STATUS", "BREAKER 7 STATUS", "BREAKER 8 STATUS", "BREAKER 9 STATUS",
                    "BREAKER A STATUS", "BREAKER B STATUS", "BREAKER C STATUS", "BREAKER D STATUS",
                    "BREAKER E STATUS", "BREAKER F STATUS", "BREAKER G STATUS"],  # Channel Names
                   [(0, 'v'), (0, 'v'),
                    (0, 'v')],  # Conversion factor for phasor channels - (float representation, not important)
                   [(1, 'pow')],  # Conversion factor for analog channels
                   [(0x0000, 0xffff)],  # Mask words for digital status words
                   50,  # Nominal frequency
                   1,  # Configuration change count
                   50)  # Rate of phasor data transmission)

pmu = Pmu(header, cfg2, pmu_id=pmu_id)

while True:
    try:
        serial_data = sio.readline()

        data = serial_data.strip().split(',')
        soc = int(data[1])*seconds_in_week+gps_to_unix+int(data[2])-18
        frasec = int(data[3])*20*1000
        v1 = float(data[4])
        v2 = float(data[5])
        v3 = float(data[6])
        th1 = float(data[8])
        th2 = float(data[9])
        th3 = float(data[10])

        pmu.send_data(soc=soc,
                    frasec=frasec,
                    phasors=[(v1, th1),
                            (v2, th2),
                            (v3, th3)],
                    analog=[9.91],
                    digital=[0x0001])

    except KeyboardInterrupt:
        print('Interrupted')
        sys.exit()
    except:
        print("Serial data/send error!")
        continue
