[![Build Status](https://travis-ci.org/Scott8586/bme280-python-mqtt.svg?branch=master)](https://travis-ci.org/Scott8586/bme280-python-mqtt)

## bme280-python-mqtt
Daemon for bme280 sensor reporting through MQTT on the raspberry pi under python3

This code uses the [Pimoroni bme280-python](https://github.com/pimoroni/bme280-python) code to scan the BME280 sensor attached to a raspberry pi and report the results over MQTT.

The daemon uses configparser() to read an .ini style file to get information on the MQTT server to contact.
It is also possible to set the i2c address for the sensor, and provide measurement offsets.
If elevation is provided (in meters), a sealevel pressure value is calculated and provided in the MQTT feed.

I am currently running this code on a raspberry pi zero W.

A systemd service file is also included and is part of the install process in the Makefile.

### Requirements

The following packages are required beyond stock python3.5 to get this running:

	argparse
	configparser
	python-daemon
	paho-mqtt
	smbus2
	pimoroni-bme280

You can install these using pip3 like so:

```
sudo pip3 install -r requirements.txt --break-system-packages
```

Install the requirements in the `root` enviroment, or whichever enviroment make sense for you. Currently I run the daemon as root for easy access to /dev/i2c

Or you can install these dependencies with `sudo make build`

### Install

Set the correct SMBus for your environment in the `bme280_mqtt_daemon.py`, as my setup has 22 but usually it has the 1.
Just run `sudo make install` from the cloned repo folder.

Now, `sudo cp mqtt-example.ini /etc/mqtt.ini` and modify its values with the editor you feel, like `nano /etc/mqtt.ini`.

### Home Assistant

The following configuration yaml could be used with Home Assistant:

```
sensor:
 - platform: mqtt
    state_topic: 'environment/den/BME280_temperature'
    unit_of_measurement: '°C'
    name: 'Den Temperature'
  - platform: mqtt
    state_topic: 'environment/den/BME280_humidity'
    unit_of_measurement: '% RH'
    name: 'Den Humidity'    
  - platform: mqtt
    state_topic: 'environment/den/BME280_pressure'
    unit_of_measurement: 'hPa'
    name: 'Den Pressure'
  - platform: mqtt
    state_topic: 'environment/den/BME280_sealevel_pressure'
    unit_of_measurement: 'hPa'
    name: 'Den Sealevel Pressure'
```

And for lovelace display:

```
cards:
  - entities:
      - entity: sensor.den_temperature
      - entity: sensor.den_humidity
      - entity: sensor.den_pressure
      - entity: sensor.den_sealevel_pressure
    title: Den BME280
    type: entities
```


