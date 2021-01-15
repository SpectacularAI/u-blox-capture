import argparse
import json
from serial import Serial
from ubxtranslator.core import Parser
from ubxtranslator.predefined import NAV_CLS
from pandas import Timestamp, Timedelta # Use pandas time objects for nanosecond precision
import os
import threading


parser = argparse.ArgumentParser(description="Convert UBX-NAV-PVT and UBX-NAV-HPPOSLLH into accurate GPS coordinates")
parser.add_argument("file", help="ubx JSONL file")
parser.add_argument("-low", help="Force to use low precision location", action="store_true")


UBLOX_LATLON_SCALE = 1e-7
UBLOX_LATLON_HP_SCALE = 1e-2
UBLOX_ACC_SCALE = 1e-3
MM_TO_METERS = 1e-3


def extractTimestamp(raw):
    if raw["valid"]["validTime"]:
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
    return ts


def extractHighPrecisionLocation(raw):
    # Precise latitude in deg * 1e-7 = lat + (latHp * 1e-2)
    lat = (raw["lat"] + raw["latHp"] * UBLOX_LATLON_HP_SCALE) * UBLOX_LATLON_SCALE
    lon = (raw["lon"] + raw["lonHp"] * UBLOX_LATLON_HP_SCALE) * UBLOX_LATLON_SCALE
    # Precise height in mm = hMSL + (hMSLHp * 0.1)
    alt = (raw["hsML"] + raw["hMSLHp"] * 0.1) * MM_TO_METERS
    acc = raw["hAcc"] * MM_TO_METERS
    accV = raw["vAcc"] * MM_TO_METERS
    return (lat, lon, alt, acc, accV)


def extractLocation(raw):
    lat = raw["lat"] * UBLOX_LATLON_SCALE
    lon = raw["lon"] * UBLOX_LATLON_SCALE
    alt = raw["hsML"] * MM_TO_METERS
    acc = raw["hAcc"] * MM_TO_METERS
    accV = raw["vAcc"] * MM_TO_METERS
    return (lat, lon, alt, acc, accV)


def run(args):
    inputFile = os.path.splitext(args.file)
    outputFile = inputFile[0] + "-gps" + inputFile[1]
    print("Starting processing")

    # Group data based on iTOW, they belong to same navigation solution
    useHighPrecision = False
    itowGroups = {}
    with open(args.file) as f:
        try:
            msg = json.load(f.readline())
            msgType = msg["type"]
            if  msgType == "HPPOSLLH": useHighPrecision = True
            if msgType == "PVT" or msgType == "HPPOSLLH" or msgType == "TIMEUTC":
                itow = msg["iTOW"]
                group = itowGroups.get(itow)
                if not group:
                    group = {"iTOW": itow}
                    itowGroups[itow] = group
                group[msgType] = msg
        except err:
            print(err)

    if args.low:
        useHighPrecision = False

    # Convert groups into GPS coordinates
    coordinates = []
    for itow in itowGroups:
        group = itowGroups[itow]
        ts = None
        if group.get("PVT"):
            ts = extractTimestamp(group.get("PVT"))
        if not ts and group.get("TIMEUTC"):
            ts = extractTimestamp(group.get("TIMEUTC"))
        if not ts:
            print("Valid timestamp missing, skipping iTOW={}".format(itow))
            continue

        if group.get("HPPOSLLH"):
            if useHighPrecision:
                lat, lon, alt, acc, accV = extractHighPrecisionLocation(group.get("HPPOSLLH"))
            else:
                lat, lon, alt, acc, accV = extractLocation(group.get("HPPOSLLH"))
        elif not useHighPrecision and group.get("PVT"):
            lat, lon, alt, acc, accV = extractLocation(group.get("PVT"))

        if not acc:
            print("Valid location missing, skipping iTOW={}".format(itow))
            continue

        coordinates.append({
            "time": ts.timestamp(),
            "lat": lat,
            "lon": lon,
            "altitude": alt,
            "accuracy": acc,
            "verticalAccuracy": accV
        })

    coordinates.sort(key=lambda x: x.time)

    with open(outputFile, "w") as writer:
        for coord in coordinates:
            writer.write(json.dumps(coord) + "\n")


if __name__ == "__main__":
    args = parser.parse_args()
    run(args)
    print("Done!")
