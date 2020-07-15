#!/usr/bin/env python3
"""
Python script for reading a BME280 sensor on a raspberry pi and reporting back via MQTT
"""

# pylint: disable=no-member
# pylint: disable=unused-argument

import time
import datetime
import platform
#import math # needed only for detailed sealavel pressure calculation
import json
import os
import signal
import sys

import argparse
import configparser
import daemon
from daemon import pidfile
import paho.mqtt.client as mqtt
from builtins import object

try:
    from smbus2 import SMBus
except ImportError:
    from smbus import SMBus

# Python library for the BME280 temperature, pressure and humidity sensor
# pylint: disable=import-error
import bme280

MQTT_INI = "/etc/mqtt.ini"
MQTT_SEC = "bme280"

SEALEVEL_MIN = -999

class Options(object):
    """Object for holding option variables
    """
    def __init__(self):
        self.toffset = 0
        self.hoffset = 0
        self.poffset = 0
        self.root_topic = ""
        self.elevation = SEALEVEL_MIN
        self.format = "flat"

class Topics(object):
    """Object for handing topic strings
    """
    
    def __init__(self, root_topic, section):
        self.temperature  = root_topic + '/' + section + '_temperature'
        self.humidity   = root_topic + '/' + section + '_humidity'
        self.pressure = root_topic + '/' + section + '_pressure'
        self.sealevel_pressure = root_topic + '/' + section + '_sealevel_pressure'

class SensorData(object):
    """Sensor Data Object
    """
    
    def __init__(self):
        self.temperature = 0
        self.humidity = 0
        self.pressure = 0

        
def receive_signal(signal_number, frame):
    """function to attach to a signal handler, and simply exit
    """

    print('Received signal: ', signal_number)
    sys.exit(0)


def on_connect(client, userdata, flags, return_code):
    """function to mark the connection to a MQTT server
    """

    if return_code != 0:
        print("Connected with result code: ", str(return_code))


def publish_mqtt(client, sensor_data, options, topics, file_handle, verbose=False):
    """Publish the sensor data to mqtt, in either flat, or JSON format
    """


    hum = sensor_data.humidity + options.hoffset

    temp_C = sensor_data.temperature
    temp_F = 9.0/5.0 * temp_C + 32 + options.toffset
    temp_K = temp_C + 273.15

    press_A = sensor_data.pressure + options.poffset

    # https://www.sandhurstweather.org.uk/barometric.pdf
    if options.elevation > SEALEVEL_MIN:
        # option one: Sea Level Pressure = Station Pressure / e ** -elevation / (temperature x 29.263)
        #press_S = press_A / math.exp( - elevation / (temp_K * 29.263))
        # option two: Sea Level Pressure = Station Pressure + (elevation/9.2)
        press_S = press_A + (options.elevation/9.2)
    else:
        press_S = press_A

    curr_datetime = datetime.datetime.now()

    if verbose:
        str_datetime = curr_datetime.strftime("%Y-%m-%d %H:%M:%S")
        print("{0}: temperature: {1:.1f} F, humidity: {2:.1f} %RH, pressure: {3:.2f} hPa, sealevel: {4:.2f} hPa".
              format(str_datetime, temp_F, hum, press_A, press_S), file=file_handle)
        file_handle.flush()

    if options.format == "flat":
        temperature = str(round(temp_F, 1))
        humidity = str(round(hum, 1))
        pressure = str(round(press_A, 2))
        pressure_sealevel = str(round(press_S, 2))

        client.publish(topics.temperature, temperature)
        client.publish(topics.humidity, humidity)
        client.publish(topics.pressure, pressure)

        if options.elevation > SEALEVEL_MIN:
            client.publish(topics.sealevel_pressure, pressure_sealevel)

    else:
        data = {}
        data['humidity'] = round(hum, 1)
        data['temperature'] = round(temp_F, 1)
        data['pressure'] = round(press_A, 2)
        if options.elevation > SEALEVEL_MIN:
            data['sealevel'] = round(press_S, 2)
        data['timestamp'] = curr_datetime.replace(microsecond=0).isoformat()

        #json_data = json.dumps(data)
        client.publish(options.root_topic, json.dumps(data))

def start_daemon(args):
    """function to start daemon in context, if requested
    """

    context = daemon.DaemonContext(
        working_directory='/var/tmp',
        umask=0o002,
        pidfile=pidfile.TimeoutPIDLockFile(args.pid_file),
        )

    context.signal_map = {
        signal.SIGHUP: receive_signal,
        signal.SIGINT: receive_signal,
        signal.SIGQUIT: receive_signal,
        signal.SIGTERM: receive_signal,
    }

    with context:
        start_bme280_sensor(args)


def start_bme280_sensor(args):
    """Main program function, parse arguments, read configuration,
    setup client, listen for messages"""

    i2c_address = bme280.I2C_ADDRESS_GND # 0x76, alt is 0x77

    options = Options()

    if args.daemon:
        file_handle = open(args.log_file, "w")
    else:
        file_handle = sys.stdout

    client = mqtt.Client(args.clientid)

    mqtt_conf = configparser.ConfigParser()
    mqtt_conf.read(args.config)

    options.root_topic = mqtt_conf.get(args.section, 'topic')

    topics = Topics(options.root_topic, args.section)
    
    if mqtt_conf.has_option(args.section, 'address'):
        i2c_address = int(mqtt_conf.get(args.section, 'address'), 0)

    if mqtt_conf.has_option(args.section, 'toffset'):
        options.toffset = float(mqtt_conf.get(args.section, 'toffset'))

    if mqtt_conf.has_option(args.section, 'hoffset'):
        options.hoffset = float(mqtt_conf.get(args.section, 'hoffset'))

    if mqtt_conf.has_option(args.section, 'poffset'):
        options.poffset = float(mqtt_conf.get(args.section, 'poffset'))

    if mqtt_conf.has_option(args.section, 'elevation'):
        options.elevation = float(mqtt_conf.get(args.section, 'elevation'))

    if mqtt_conf.has_option(args.section, 'format'):
        options.format = mqtt_conf.get(args.section, 'format')

    if (mqtt_conf.has_option(args.section, 'username') and
            mqtt_conf.has_option(args.section, 'password')):
        username = mqtt_conf.get(args.section, 'username')
        password = mqtt_conf.get(args.section, 'password')
        client.username_pw_set(username=username, password=password)

    host = mqtt_conf.get(args.section, 'host')
    port = int(mqtt_conf.get(args.section, 'port'))

    client.on_connect = on_connect
    client.connect(host, port, 60)
    client.loop_start()

    # Initialise the BME280
    bus = SMBus(1)

    sensor = bme280.BME280(i2c_addr=i2c_address, i2c_dev=bus)
    sensor_data = SensorData()
    
    if args.verbose:
        curr_datetime = datetime.datetime.now()
        str_datetime = curr_datetime.strftime("%Y-%m-%d %H:%M:%S")
        print("{0}: pid: {1:d} bme280 sensor started on 0x{2:x}, toffset: {3:0.1f} F, hoffset: {4:0.1f} %, poffset: {5:0.2f} hPa".
              format(str_datetime, os.getpid(), i2c_address, options.toffset, options.hoffset, options.poffset), file=file_handle)
        file_handle.flush()

    while True:
        curr_time = time.time()
        my_time = int(round(curr_time))
        sensor_data.temperature = sensor.get_temperature()
        sensor_data.humidity = sensor.get_humidity()
        sensor_data.pressure = sensor.get_pressure()
        
        if my_time % 60 == 0:
            publish_mqtt(client, sensor_data, options, topics, file_handle, args.verbose)

        time.sleep(1)


def main():
    """Main function call
    """

    #myhost = socket.gethostname().split('.', 1)[0]
    my_host = platform.node()
    my_pid = os.getpid()
    client_id = my_host + '-' + str(my_pid)

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-c', '--config', default=MQTT_INI, help="configuration file")
    parser.add_argument('-d', '--daemon', action='store_true', help="run as daemon")
    parser.add_argument('-p', '--pid-file', default='/var/run/bme280_mqtt.pid')
    parser.add_argument('-l', '--log-file', default='/var/log/bme280_mqtt.log')
    parser.add_argument('-i', '--clientid', default=client_id, help="clientId for MQTT connection")
    parser.add_argument('-s', '--section', default=MQTT_SEC, help="configuration file section")
    parser.add_argument('-v', '--verbose', action='store_true', help="verbose messages")

    cmdline_args = parser.parse_args()

    if cmdline_args.daemon:
        start_daemon(cmdline_args)
    else:
        start_bme280_sensor(cmdline_args)

if __name__ == '__main__':
    main()
