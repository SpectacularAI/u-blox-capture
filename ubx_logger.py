import argparse
import json
from serial import Serial
from ubxtranslator.ubxtranslator.core import Parser
from ubxtranslator.ubxtranslator.predefined import NAV_CLS
from pandas import Timestamp, Timedelta # Use pandas time objects for nanosecond precision
import os
import threading
import time


parser = argparse.ArgumentParser(description="Log UBX-NAV-* messages from device to JSONL file")
parser.add_argument("device", help="Serial device")
parser.add_argument("-b", help="Baudrate", type=int, default=460800)
parser.add_argument("-v", help="Verbose, prints errors", action="store_true")


def inputThreadFn(aList):
    input()
    aList.append(True)


def parseUBX(payload):
    raw = {}
    for field in payload._fields:
        value = getattr(payload, field)
        if type(value) != int:
            obj = {}
            for field2 in value._fields:
                obj[field2] = getattr(value, field2)
            raw[field] = obj
        else:
            raw[field] = value
    return raw


def run(args):
    outputFile = "./output/ubx-" + Timestamp.now().strftime("%Y-%m-%d-%H-%M-%S") + ".jsonl"
    os.makedirs("./output", exist_ok = True)
    device = Serial(args.device, args.b, timeout=10)
    parser = Parser([NAV_CLS])
    print("Starting to listen for UBX packets")
    print("Press ENTER to stop recording...")
    aList = []
    threading.Thread(target = inputThreadFn, args=(aList,)).start()
    with open(outputFile, "w") as writer:
        try:
            while not aList:
                try:
                    msg, msg_name, payload = parser.receive_from(device)
                    raw = parseUBX(payload)
                    entry = {
                        "type": msg_name,
                        "payload": raw,
                        "monoTime": time.monotonic()
                    }
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
