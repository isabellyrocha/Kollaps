#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import time
import socket
import json
from os import environ, getenv
from threading import Lock

from kollaps.Kollapslib.CommunicationsManager import CommunicationsManager
from kollaps.Kollapslib.NetGraph import NetGraph
from kollaps.Kollapslib.XMLGraphParser import XMLGraphParser
from kollaps.Kollapslib.utils import print_named

import sys
if sys.version_info >= (3, 0):
    from typing import Dict, List, Tuple

LOG_FILE = "/var/log/Kollaps_LOG.json"
DEFAULT_INTERVAL = 1.0

class LoggerState:
    graph = None  # type: NetGraph
    lock = Lock()
    flows = {} # type: Dict[str, List[int, int]]
    comms = None  # type: CommunicationsManager


def collect_flow(bandwidth, links):
    key = str(links[0]) + ":" + str(links[-1])
    with LoggerState.lock:
        if key in LoggerState.flows:
            LoggerState.flows[key][0] += int(bandwidth/1000)
            LoggerState.flows[key][1] += 1
            
        else:
            LoggerState.flows[key] = [int(bandwidth/1000), 1]
            
    return True


def main():
    if len(sys.argv) != 2:
        topology_file = "/topology.xml"
    else:
        topology_file = sys.argv[1]

    AVERAGE_INTERVAL = float(environ.get("AVERAGE_INTERVAL", str(DEFAULT_INTERVAL)))

    graph = NetGraph()
    XMLGraphParser(topology_file, graph).fill_graph()
    
    own_ip = socket.gethostbyname(socket.gethostname())
    LoggerState.comms = CommunicationsManager(collect_flow, graph, None, own_ip)

    LoggerState.graph = graph
    
    print_named("logger", "Logger ready!")  # PG

    log_file = open(LOG_FILE, 'w')

    starttime=time.time()
    output = {}
    while True:
        with LoggerState.lock:
            output["ts"] = time.time()
            for key in LoggerState.flows:
                output[key] = (LoggerState.flows[key][0]/LoggerState.flows[key][1], LoggerState.flows[key][1])
            LoggerState.flows.clear()
            
        if(len(output) > 1):
            json.dump(output, log_file)
            log_file.write("\n")
            log_file.flush()
            
        output.clear()
        sleep_time = AVERAGE_INTERVAL - ((time.time() - starttime) % AVERAGE_INTERVAL)
        time.sleep(sleep_time)

if __name__ == "__main__":
    if getenv('RUNTIME_EMULATION', 'true') != 'false':
        main()
