# u-blox-capture

Tools to capture RTK GPS output using u-blox C099-F9P application board.

## Building

str2str is used to send RTK ground station information to u-blox device.

``` bash
cd RTKLIB/app/str2str/gcc/
make
```

## Usage

### Configuration

`ubx_configurator.py` can be used to configure the u-blox device. `example/` folder contains some example configurations that can be used. `definitions/zed-fp9-interface-description.txt` contains supported configuration values. It's not comprehensive, you can add missing values from [ZED-F9P Interface Description](https://www.u-blox.com/en/docs/UBX-18010854). Use `-flash` flag store changes to on-board flash memory, making them persistent.

``` bash
python ubx_configurator /dev/cu.usbmodem14123301 example/high_precision_gps_only.cfg
```

### Setting up RTK

Connect u-blox device and find what device it is. On Mac for example:
``` bash
ls /dev | grep cu.usbmodem
```

Next start str2str that connects to RTK ground station and delivers information to u-blox device.

You need to replace following with correct variables:
* RTK information from your provider: USER, PASS, IP, PORT, MOUNTPOINT
* LAT/LON: Rought estimate of current position
* DEVICE: device name, for example: cu.usbmodem14123301

``` bash
./RTKLIB/app/str2str/gcc/str2str -in ntrip://USER:PASS@IP:PORT/MOUNTPOINT -p LAT LON 0.0 -n 250 -out serial://DEVICE:460800:8:n:1
```

Leave this running on the backround.

u-blox device should now show a *blinking blue light* (connected to GPS) and *solid yellow light* next to it (connected to RTK).

### Logging

Replace `/dev/cu.usbmodem14123301` with your device.

``` bash
python ubx_logger.py -v /dev/cu.usbmodem14123301
```

### Converting to simple GPS coordinates

`gps_converter.py` is used to convert different UBX messages (PVT, TIMEUTC, HPPOSLLH) to accurate easy to use GPS coordinates.

``` bash
python gps_converter.py output/ubx-2021-01-16-17-22-16.jsonl
```

An example entry:

``` bash
{
    "time": 1610810565.79965,    # UTC time in seconds
    "lat": 60.173692026,         # Latitude
    "lon": 24.803227458,         # Longtiude
    "altitude": 15.3108,         # Altitude in metters
    "accuracy": 10.364,          # Accuracy in meters
    "verticalAccuracy": 14.836   # Vertical accuracy in meters
}
```

## Resources

* C099-F9P Quick Start https://www.u-blox.com/en/docs/UBX-18052242
* C099-F9P User Guide (with ODIN-W2 Connectivity SW) https://www.u-blox.com/en/docs/UBX-18055649
* ZED-F9P Interface Description https://www.u-blox.com/en/docs/UBX-18010854