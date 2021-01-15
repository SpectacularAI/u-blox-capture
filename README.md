# u-blox-capture


## Building

``` bash
cd RTKLIB/app/str2str/gcc/
make
```

## Usage

### Setting up the device

Connect u-blox device and find what device it is. On Mac for example:
``` bash
ls /dev | grep cu.usbmodem
```

Next tart str2str that connects to RTK ground station and delivers information to u-blox device.

You need to replace following with correct variables:
* RTK information from your provider: USER, PASS, IP, PORT, MOUNTPOINT
* LAT/LON: Rought estimate of current position
* DEVICE: device name, for example: cu.usbmodem14123301

``` bash
./RTKLIB/app/str2str/gcc/str2str -in ntrip://USER:PASS@IP:PORT/MOUNTPOINT -p LAT LON 0.0 -n 250 -out serial://DEVICE:460800:8:n:1
```

Leave this running on the backround.

u-blox device should now show a blinking blue light (connected to GPS) and solid yellow light next to it (connected to RTK).

### Logging

Replace DEVICE with full device path, for example: /dev/cu.usbmodem14322301.

``` bash
python ubx_logger.py -v -a -p DEVICE
```
