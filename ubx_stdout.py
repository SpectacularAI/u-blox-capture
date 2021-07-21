import argparse
import json
from serial import Serial
from ubxtranslator.ubxtranslator.core import Parser
from ubxtranslator.ubxtranslator.predefined import NAV_CLS
from pandas import Timestamp, Timedelta # Use pandas time objects for nanosecond precision
import os
import threading
from gps_converter import buildMeasurement
from ubx_logger import parseUBX


parser = argparse.ArgumentParser(description="Print UBX-NAV-* solution to stdout")
parser.add_argument("device", help="Serial device")
parser.add_argument("-b", help="Baudrate", type=int, default=460800)
parser.add_argument("-v", help="Verbose, prints errors", action="store_true")
parser.add_argument("--incomplete", help="Allow printing incomplete solutions", action="store_true")


def outputSolution(solution):
    measurement = buildMeasurement(solution)
    output = [
        # measurement["time"],
        measurement["lat"],
        measurement["lon"],
        measurement["altitude"],
        measurement["verticalAccuracy"],
        measurement["accuracy"],
    ]
    print(' '.join(str(val) for val in output))


def run(args):
    device = Serial(args.device, args.b, timeout=10)
    parser = Parser([NAV_CLS])
    aList = []
    currentiTOW = -1
    currentSolution = {}
    try:
        while not aList:
            try:
                msg, msg_name, payload = parser.receive_from(device)
                raw = parseUBX(payload)

                # Start new solution
                if raw["iTOW"] != currentiTOW:
                    if args.incomplete and currentSolution: # Output partial solution
                        outputSolution(currentSolution)
                    currentSolution = {}

                # Add payload to current solution
                currentSolution[msg_name] = raw
                currentiTOW = raw["iTOW"]

                # All three desired payloads received, output them
                if all (k in currentSolution for k in ("HPPOSLLH","TIMEUTC","PVT")):
                    outputSolution(currentSolution)
                    currentSolution = {}

            except (ValueError, IOError) as err:
                if args.v:
                    print(err)
    finally:
        device.close()


if __name__ == "__main__":
    args = parser.parse_args()
    run(args)
