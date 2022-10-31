## Distributed Systems Capstone project

### Replicated log V1

The aim of this project is implementation of a simple distributed log system and practice approaches and patterns learned during the course.
A detailed description of the project is allowed to the course participants.

Features implemented in the current version:
+ HTTP Rest was chosen as an RPC framework for communication with and within the system 
+ message posted to the Master is replicating on every Secondary server asynchronously
+ logging is implemented for all essential stages
+ the total order for all messages across the system is guaranteed with some assumptions
+ deduplication is implemented with some assumptions
+ blocking the client if message delivery is delayed

#### Assumptions
1. To preserve consistency we consider that it is not possible to have gaps in the keys
2. It is not possible to override the already saved message
3. It is not required to block access to internal system endpoints from the outside 

#### Requirements
Docker should be installed on your system.
Local IP 0.0.0.0 and ports 8000, 8001, 8002 should be free to use.

#### Run and testing

Need to run the following command to start the replicated log system 

    docker-compose up --build

Log file will be created here: log/app.log

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
        "value": "testValue"
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

__

    curl -X POST http://0.0.0.0:8001/delay \
    -H "Content-Type: application/json" \
    -d '{
        "value": 30
    }' 