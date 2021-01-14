import argparse
import json
from serial import Serial
from ubxtranslator.core import Parser
from ubxtranslator.predefined import NAV_CLS
from pandas import Timestamp, Timedelta # Use pandas time objects for nanosecond precision
import os
import threading


parser = argparse.ArgumentParser(description="Log UBX-NAV-PVT from device to JSONL file")
parser.add_argument("-p", help="Serial device")
parser.add_argument("-b", help="Baudrate", type=int, default=460800)
parser.add_argument("-a", help="Log all message types, without this only PVT is logged", action="store_true")
parser.add_argument("-v", help="Verbose, prints errors", action="store_true")


UBLOX_LATLONG_SCALE = 1e-7
UBLOX_ACC_SCALE = 1e-3


def inputThreadFn(a_list):
    input()
    aList.append(True)


def parseUBX(payload):
    raw = {}
    for field in payload._fields:
        value = getattr(payload, field)
        if type(value) != int:
            # Flatten bit fields
            for field2 in value._fields:
                raw[field2] = getattr(value, field2)
        else:
            raw[field] = value
    return raw


def run(args):
    outputFile = "./output/gps-" + Timestamp.now().strftime("%Y-%m-%d-%H-%M-%S") + ".jsonl"
    os.makedirs("./output", exist_ok = True)
    device = Serial(args.p, args.b, timeout=10)
    parser = Parser([NAV_CLS])
    print("Starting to listen for UBX packets")
    print("Press ENTER to stop recording...")
    aList = []
    threading.Thread(target = inputThreadFn, args=(a_list,)).start()
    with open(outputFile, "w") as writer:
        try:
            while not aList:
                try:
                    msg, msg_name, payload = parser.receive_from(device)
                    raw = parseUBX(payload)
                    entry = {
                        "messageType": msg_name,
                        "original": raw
                    }
                    if msg_name == "PVT": # UBX-NAV-PVT (0x01 0x07), Position Velocity Time msg
                        # Only add time if it's valid
                        if raw["validTime"]:
                            # nano can be negative, so add it via Timedelta
                            ts = Timestamp(
                                year = raw["year"],
                                month = raw["month"],
                                day = raw["day"],
                                hour = raw["hour"],
                                minute = raw["min"],
                                second = raw["sec"]
                            ) + Timedelta(value = raw["nano"], unit = "nanoseconds")
                        else:
                            ts = None
                        entry["time"] = ts.timestamp()
                        entry["lat"] = raw["lat"] * UBLOX_LATLONG_SCALE
                        entry["lon"] = raw["lon"] * UBLOX_LATLONG_SCALE
                        entry["acc"] = raw["hAcc"] * UBLOX_ACC_SCALE

                    if args.a or msg_name == "PVT":
                        writer.write(json.dumps(entry) + "\n")

                except (ValueError, IOError) as err:
                    if args.v:
                        print(err)
        finally:
            device.close()


if __name__ == "__main__":
    args = parser.parse_args()
    run(args)
    print("Done!")
