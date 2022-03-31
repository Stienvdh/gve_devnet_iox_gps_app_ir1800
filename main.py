#!/usr/bin/python

""" Copyright (c) 2020 Cisco and/or its affiliates.
This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at
           https://developer.cisco.com/docs/licenses
All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied. 
"""

import serial
import time
import json
import signal
import threading
import logging
import requests
import os
import datetime

from wsgiref.simple_server import make_server

def _sleep_handler(signum, frame):
    print("SIGINT Received. Stopping CAF")
    raise KeyboardInterrupt

def _stop_handler(signum, frame):
    print("SIGTERM Received. Stopping CAF")
    raise KeyboardInterrupt

signal.signal(signal.SIGTERM, _stop_handler)
signal.signal(signal.SIGINT, _sleep_handler)

PORT = 8000
HOST = "0.0.0.0"

class SerialThread(threading.Thread):
    def __init__(self):
        super(SerialThread, self).__init__()
        self.name = "SerialThread"
        self.setDaemon(True)
        self.stop_event = threading.Event()


    def stop(self):
        self.stop_event.set()

    def run(self):
        INTERVAL = 5 # Interval between publishing in seconds
        URL = "XXX" # URL to send JSON HTTP payload to

        serial_dev = os.getenv("gps1")
        if serial_dev is None:
            serial_dev="/dev/ttyNMEA1"

        sdev = serial.Serial(port=serial_dev)
        sdev.timeout = 5
        print("Serial:  %s\n", sdev)

        # Initialise logging
        try:
            directory = os.environ['CAF_APP_LOG_DIR'] + "/"
        except KeyError:
            directory = "./"
        logger = logging.getLogger('webapp')
        logger.setLevel(logging.INFO)
        file_handler = logging.FileHandler(directory + 'gps_data.log')
        formatter = logging.Formatter('%(msg)s')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        while True:
            if self.stop_event.is_set():
                break
            while sdev.inWaiting() > 0:
                sensVal = sdev.readline()
                sensVal = sensVal.decode().split(",")
                format = sensVal[0][1:]
                # NMEA data formats: https://anavs.com/knowledgebase/nmea-format/
                if format == "GPRMC" and sensVal[2] == "A":
                    entry = {
                        "timestamp" : datetime.datetime.now().strftime("%d/%m/%y %H:%M:%SUTC"),
                        "latitude" : sensVal[3] + sensVal[4],
                        "longitude" : sensVal[5] + sensVal[6],
                        "speed" : sensVal[7]
                    }

                    # Send to REST endpoint
                    requests.post(URL, headers={"Content-Type" : "application/json"}, json=entry)

                    # Log to file
                    logger.info(json.dumps(entry))

                    time.sleep(INTERVAL)

        sdev.close()

def simple_app(environ, start_response):
    status = '200 OK'
    headers = [('Content-type', 'application/json')]
    start_response(status, headers)
    ret = json.dumps({"response" : "OK"})
    return ret

httpd = make_server(HOST, PORT, simple_app)
try:
    p = SerialThread()
    p.start()
    httpd.serve_forever()
except KeyboardInterrupt:
    p.stop()
    httpd.shutdown()