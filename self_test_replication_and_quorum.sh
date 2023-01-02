#!/bin/bash

echo "Check that no messages are stored at the moment:"
echo "Master records: "
 curl http://0.0.0.0:8000/messages
echo "\nSecondary 1 records: "
 curl http://0.0.0.0:8001/messages
echo "\nSecondary 2 records: "
curl http://0.0.0.0:8002/messages

echo "\n\nAdd new message Msg1 with WC=3"
curl -X POST http://0.0.0.0:8000/message \
-H "Content-Type: application/json" \
-d '{
    "value": "Msg1",
    "write_concern": 3
}'

echo "\n\nCheck that the message Msg1 is stored on all modes:\n"
echo "Master records: "
 curl http://0.0.0.0:8000/messages
echo "\nSecondary 1 records: "
 curl http://0.0.0.0:8001/messages
echo "\nSecondary 2 records: "
curl http://0.0.0.0:8002/messages

echo "\n\Stop the first node"
docker-compose pause secondary1

echo "\n\nAdd new message Msg2 with WC=2"
curl -X POST http://0.0.0.0:8000/message \
-H "Content-Type: application/json" \
-d '{
    "value": "Msg2",
    "write_concern": 2
}'

echo "\nCheck that the message Msg2 is returned from Secondary 2 only:"
echo "Master records: "
 curl http://0.0.0.0:8000/messages
echo "\nSecondary 1 records: "
 curl http://0.0.0.0:8001/messages --max-time 1
echo "\nSecondary 2 records: "
curl http://0.0.0.0:8002/messages

echo "\n\nSleep 10 seconds to be able see in logs paused replication and check the latest 10 records from logs:"
sleep 10s

tail -n 10 ./log/app.log

echo "\n\nStop the second node"
docker-compose pause secondary2

echo "\n\nSleep 10 seconds to make sure that both nodes are considered as unhealthy now"
sleep 10s
echo "\nMaster records: "
 curl http://0.0.0.0:8000/messages
echo "\nSecondary 1 records: "
 curl http://0.0.0.0:8001/messages --max-time 1
echo "\nSecondary 2 records: "
curl http://0.0.0.0:8002/messages --max-time 1

echo "\n\nAdd new message Msg3 with WC=1 and see that Master is read-only now"
curl -X POST http://0.0.0.0:8000/message \
-H "Content-Type: application/json" \
-d '{
    "value": "Msg3",
    "write_concern": 1
}'

echo "\n\nRun both secondaries"
docker-compose unpause secondary1
docker-compose unpause secondary2

echo "\n\nSleep 5 seconds - all messages should be already synchronized on all nodes, except Msg3, because it was posted to read-only Master and was ignored :"
sleep 5s
echo "\nMaster records: "
 curl http://0.0.0.0:8000/messages
echo "\nSecondary 1 records: "
 curl http://0.0.0.0:8001/messages
echo "\nSecondary 2 records: "
curl http://0.0.0.0:8002/messages

echo "\n\nCheck the latest 10 records from logs:\n"
sleep 1s
tail -n 10 ./log/app.log

echo "\n\nTo validate all details about delays and heartbeats logic you have to review all logs\n"

echo "\n\nSelf-test finished\n"
