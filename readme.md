## Distributed Systems Capstone project

### Replicated log V3

The aim of this project is implementation of a simple distributed log system and practice approaches and patterns learned during the course.
A detailed description of the project is allowed to the course participants.

Features implemented in the current version:
+ added config file for being able to define some settings 
+ HTTP Rest was chosen as an RPC framework for communication with and within the system 
+ message posted to the Master is replicating on every Secondary server asynchronously with a retry mechanism:
  + retries implemented with an unlimited number of attempts, but the delay interval is growing after each attempt (intervals: 1, 2, 5, 10, 30, 60, 90, 180, 300 seconds)
  + if a secondary server is unhealthy (according to heartbeat status) - retry requests are paused until the server is up again
  + when secondary is up again all messages are replicating automatically
+ logging is implemented for all essential stages
+ the total order for all messages across the system is guaranteed with some assumptions
+ deduplication is implemented with some assumptions
+ implemented possibility to provide *write concern* parameter to specify how many ACKs the master should receive from secondaries before responding to the client 
+ blocking the client if message delivery is delayed
+ heartbeat mechanism is implemented:
  + master sends requests to all secondary nodes with provided in config file interval
  + after 2 failed requests in a row the node is considered suspected
  + after 5 failed requests in a row the node is considered unhealthy, all replication stop for this node
  + after the first successful heartbeat request the node considered as healthy
  + the heartbeat endpoint `/heartbeat` returns simple text message without any smart logic
+ quorum append is implemented:
  + parameter `quorum` in config defines the minimum number of nodes for quorum, including master
  + if number of healthy (or suspected) nodes is less - master switches to read-only mode
  + when needed number of nodes is active again - master switches back to normal mode

#### Assumptions
1. To preserve consistency we consider that it is not possible to have gaps in the keys
2. It is not possible to override the already saved message
3. It is not required to block access to internal system endpoints from the outside
4. If the *write_concern* parameter is not provided it is equal to ALL by default (ALL = 3 in default system state)
5. Config file is supposed to contain valid values, there is no validation logic for input parameters implemented

#### Requirements
Docker should be installed on your system.
Local IP 0.0.0.0 and ports 8000, 8001, 8002 should be free to use.

#### Run

Need to run the following command to start the replicated log system 

    docker-compose up --build

By default system contains 3 nodes:
+ 0.0.0.0:8000 - Master
+ 0.0.0.0:8001 - Secondary 1
+ 0.0.0.0:8002 - Secondary 2

#### Logging
+ log file will be created here: log/app.log
+ log file state is preserving by default, please clear it manually if necessary
+ records from different nodes in the log file may not be ordered by time 

#### Testing

The following commands can be used for testing the distributed log system
Note: all commands contain default IP address and port for each server 

Get list of all messages from the Master

    curl http://0.0.0.0:8000/messages

Get list of all messages from the Secondary 1

    curl http://0.0.0.0:8001/messages

Get list of all messages from the Secondary 2

    curl http://0.0.0.0:8002/messages

Add a new message on the Master node

    curl -X POST http://0.0.0.0:8000/message \
    -H "Content-Type: application/json" \
    -d '{
        "value": "testValue",
        "write_concern": 2
    }' 

Store a message with specific key on the Secondary node

_Note: it's internal system endpoint_

    curl -X PUT http://0.0.0.0:8001/message \
    -H "Content-Type: application/json" \
    -d '{
        "key": 2,
        "value": "testSetValue"
    }' 

Set a one-time delay in seconds on the Secondary node. 

_The next synchronization request from the Master to this Secondary node will be delayed for the followed number of seconds._
_Other requests including second replication request to the same server will be not affected_

    curl -X POST http://0.0.0.0:8001/delay \
    -H "Content-Type: application/json" \
    -d '{
        "value": 30
    }' 

Pause node 

_Pause docker container to imitate server is down_
_Please double-check containers names on your system_

    docker-compose pause secondary1 

#### Possible scenario for self-test

See file **self_test_delay.sh** - it contains self-test script for V2, without stopping nodes and contains logic to imitate a single request delay

See file **self_test_replication_and_quorum.sh** - it contains self-test script for V3 with testing replication and quorum. For getting the full picture you may need to review logs after the script execution.

Each script should be run on the fresh system, please restart docker-compose and clear logs before using it.

_Note: scripts should be run from the project directory and may need some adjustments according to your system configuration and docker setup_