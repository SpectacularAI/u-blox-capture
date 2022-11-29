import argparse
import json
from serial import Serial
from ubxtranslator.ubxtranslator.core import Parser
from ubxtranslator.ubxtranslator.predefined import ACK_CLS
from pandas import Timestamp, Timedelta # Use pandas time objects for nanosecond precision
import os
import threading
import time


parser = argparse.ArgumentParser(description="Configure u-blox device")
parser.add_argument("device", help="Serial device")
parser.add_argument("config", help="Config file")
parser.add_argument("-b", help="Baudrate", type=int, default=460800)
parser.add_argument("-flash", help="Store to flash memory in addition to ram", action="store_true")
parser.add_argument("-skip_nak", help="Skip NAKs", action="store_true")

class BlockingQueue(list):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cond = threading.Condition()


    def append(self, item):
        with self._cond:
            super().append(item)
            self._cond.notify_all()


    def waitAndPop(self):
        with self._cond:
            while not len(self):
                self._cond.wait()
            return self.pop()


def toU1(value):
    return value.to_bytes(1, byteorder='little')


def toU2(value):
    return value.to_bytes(2, byteorder='little')


def toU4(value):
    return value.to_bytes(4, byteorder='little')


def getLayerBitfield(ram, flash):
    res = 0
    if ram:
        res = res | 1 << 0
    if flash:
        res = res | 1 << 2
    return res


def msgToString(cmd):
    string = ""
    for b in cmd:
        string += "{} ".format(hex(b))
    return string


def createMessage(messageClass, messageId, payload):
    frame = [
        0xb5,
        0x62,
        messageClass,
        messageId,
    ]
    frame.extend(toU2(len(payload)))
    frame.extend(payload)
    # 8-bit unsigned integers
    CK_A = 0
    CK_B = 0
    for b in frame[2:]: # Skip magic bytes
        CK_A = (CK_A + b) & 0xff
        CK_B = (CK_B + CK_A) & 0xff
    frame.append(CK_A)
    frame.append(CK_B)
    return frame


# UBX-CFG-VALSET
def ubxCfgValset(cfg, ram=True, flash=False):
    messageClass = 0x06
    messageId = 0x8a
    payload = [
        0x00, # Version
        getLayerBitfield(ram, flash), # Layer
        0, # Reserved
        0, # Reserved
    ]
    payload.extend(cfg) # Payload, cfg key value pairs without padding
    return createMessage(messageClass, messageId, payload)


def cfgKeyValue(key, value, definitions):
    pair = []
    definition = definitions[key]
    keyId = definition[0]
    valueType = definition[1]
    if not definition:
        raise Exception("Unsupported config: {}".format(key))
    pair.extend(toU4(keyId))
    # TODO: Support other types
    if valueType == "U1":
        pair.extend(toU1(value))
    elif valueType == "U2":
        pair.extend(toU2(value))
    elif valueType == "U4":
        pair.extend(toU4(value))
    else:
        raise Exception("Unsupported type: '{}'".format(valueType))
    return pair


def ackListener(device, queue, shouldQuit):
    parser = Parser([ACK_CLS])
    try:
        while not shouldQuit:
            try:
                msg, msg_name, payload = parser.receive_from(device)
                queue.append({
                    "type": msg_name, # ACK or NAK
                    "clsID": payload.clsID,
                    "msgID": payload.msgID
                })
                # print(("Received: {}".format(payload)))
            except (ValueError, IOError) as err:
                # TODO: Filter out unnecesary errors and display interesting onces
                continue
                # print(err)
    finally:
        device.close()


def executeConfig(device, queue, configs, definitions, flash, skipNak):
    for conf in configs:
        confKey = conf["key"]
        confValue = conf["value"]
        cmd = bytearray(ubxCfgValset(cfgKeyValue(confKey, confValue, definitions), flash=flash))
        classId = cmd[2]
        msgId = cmd[3]
        # print(msgToString(cmd))
        res = device.write(cmd)
        if res != len(cmd):
            raise Exception("Expected to send {} bytes, but sent {}".format(len(cmd), res))
        response = queue.waitAndPop()
        if response["type"] != "ACK" or response["clsID"] != classId or response["msgID"] != msgId:
            if response["type"] == "NAK" and skipNak:
                print("Received NAK i.e. failed to set {}, {}: {}, was expecting: clsID={}, msgID={}".format(confKey, confValue, response, classId, msgId))
            else:
                raise Exception("Didn't receive correct ACK msg from device: {}, was expecting: clsID={}, msgID={}".format(response, classId, msgId))
        else:
            print("{} set to {}".format(confKey, confValue))
        time.sleep(0.1)


def run(args):
    definitions = {}
    with open("./definitions/zed-fp9-interface-description.txt") as f:
        lines = f.readlines()
        for line in lines:
            parts = [x.strip() for x in line.split(" ")]
            if len(parts) != 3:
                raise Exception("Corrupted definition: {}".format(line))
            definitions[parts[0]] = [int(parts[1], 16), parts[2]]

    configs = []
    with open(args.config) as f:
        lines = f.readlines()
        for line in lines:
            parts = [x.strip() for x in line.split(" ")]
            if len(parts) != 2:
                raise Exception("Corrupted config: {}".format(line))
            configs.append({"key": parts[0], "value": int(parts[1])})

    device = Serial(args.device, args.b, timeout=10)
    ackQueue = BlockingQueue()
    shouldQuit = []
    threading.Thread(target = ackListener, args=(device,ackQueue,shouldQuit)).start()
    try:
        executeConfig(device, ackQueue, configs, definitions, args.flash, args.skip_nak)
    except Exception as e:
        print("CONFIGURATION FAILED!!!")
        print(str(e))

    shouldQuit.append(True)


if __name__ == "__main__":
    args = parser.parse_args()
    run(args)
    print("Done!")
