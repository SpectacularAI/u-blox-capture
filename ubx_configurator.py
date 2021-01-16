import argparse
import json
from serial import Serial
from ubxtranslator.core import Parser
from ubxtranslator.predefined import ACK_CLS
from pandas import Timestamp, Timedelta # Use pandas time objects for nanosecond precision
import os


parser = argparse.ArgumentParser(description="Configure u-blox device")
parser.add_argument("-p", help="Serial device")
parser.add_argument("-b", help="Baudrate", type=int, default=460800)


CFG_DICT = {
    "CFG-RATE-MEAS": { "key": 0x30210001, "type": "U2"},
    "CFG-RATE-NAV": { "key": 0x30210002, "type": "U2"}
}


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
    payload.extend(cfg)
    return createMessage(messageClass, messageId, payload)


def cfgKeyValue(key, value):
    pair = []
    definition = CFG_DICT[key]
    if not definition:
        raise Exception("Unsupported config: (}".format(key))
    pair.extend(toU4(definition["key"]))
    if definition["type"] == 'U2':
        pair.extend(toU2(value))
    elif definition["type"] == 'U4':
        pair.extend(toU4(value))
    else:
        raise Exception("Unsupported type: (}".format(value))
    return pair


def setRate(interval):
    return ubxCfgValset(cfgKeyValue("CFG-RATE-MEAS", interval))


def ackListener(device, queue, shouldQuit):
    parser = Parser([ACK_CLS])
    try:
        while not shouldQuit:
            try:
                msg, msg_name, payload = parser.receive_from(device)
                queue.append({
                    "type": msg_name, # ACK or NAK
                    "clsID": payload["clsID"],
                    "msgID": payload["msgID"]
                })
            except (ValueError, IOError) as err:
                print(err)
    finally:
        device.close()


def executeConfig(device, queue, configs):
    for conf in configs:
        cmd = bytearray(ubxCfgValset(cfgKeyValue(conf["key"], conf["value"])))
        classId = cmd[3]
        msgId = cmd[4]
        res = device.write(cmd)
        if res != len(cmd):
            raise Exception("Expected to send {} bytes, but sent {}".format(len(cmd), res))
        response = queue.waitAndPop()
        if response["type"] != "ACK" or response["clsID"] != classId or msgId response["msgID"]:
            raise Exception("Didn't receive correct ACK msg from device: {}".format(response))


def run(args):
    # cmd = bytearray(setRate(100))
    # string = ""
    # for b in cmd:
    #     string += "{} ".format(hex(b))
    # print(string)
    configs = [
        {"key": "CFG-RATE-MEAS", "value": 100}
    ]

    device = Serial(args.p, args.b, timeout=10)
    ackQueue = BlockingQueue()
    shouldQuit = []
    threading.Thread(target = ackListener, args=(device,ackQueue,shouldQuit)).start()
    executeConfig(device, ackQueue, configs)
    shouldQuit.append(True)


    # with open(outputFile, "w") as writer:
    #     try:
    #         while not aList:
    #             try:
    #                 msg, msg_name, payload = parser.receive_from(device)
    #                 raw = parseUBX(payload)
    #                 entry = {
    #                     "type": msg_name,
    #                     "payload": raw
    #                 }
    #                 writer.write(json.dumps(entry) + "\n")
    #             except (ValueError, IOError) as err:
    #                 if args.v:
    #                     print(err)
    #     finally:
    #         device.close()


if __name__ == "__main__":
    args = parser.parse_args()
    run(args)
    print("Done!")
