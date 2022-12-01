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

echo "\n\nInit a 10 second delay on Secondary 1 for the next request"
curl -X POST http://0.0.0.0:8001/delay \
-H "Content-Type: application/json" \
-d '{
    "value": 10
}'

echo "\n\nAdd new message Msg2 with WC=3"
curl -X POST http://0.0.0.0:8000/message \
-H "Content-Type: application/json" \
-d '{
    "value": "Msg2",
    "write_concern": 3
}' &

echo "\nCheck that the message Msg2 is returned from Secondary 2 only:"
echo "Master records: "
 curl http://0.0.0.0:8000/messages
echo "\nSecondary 1 records: "
 curl http://0.0.0.0:8001/messages
echo "\nSecondary 2 records: "
curl http://0.0.0.0:8002/messages

echo "\n\nAdd new message Msg3 with WC=3 (this request will not be delayed)"
curl -X POST http://0.0.0.0:8000/message \
-H "Content-Type: application/json" \
-d '{
    "value": "Msg3",
    "write_concern": 3
}'

echo "\n\nCheck that the message Msg3 is returned from Secondary 2 only:"
echo "Master records: "
 curl http://0.0.0.0:8000/messages
echo "\nSecondary 1 records: "
 curl http://0.0.0.0:8001/messages
echo "\nSecondary 2 records: "
curl http://0.0.0.0:8002/messages

echo "\n\nSleep 10 seconds - all messages should be already synchronized on all nodes:"
sleep 10s
echo "\nMaster records: "
 curl http://0.0.0.0:8000/messages
echo "\nSecondary 1 records: "
 curl http://0.0.0.0:8001/messages
echo "\nSecondary 2 records: "
curl http://0.0.0.0:8002/messages

echo "\n\nInit a 10 second delay on Secondary 1 for the next request"
curl -X POST http://0.0.0.0:8001/delay \
-H "Content-Type: application/json" \
-d '{
    "value": 10
}'

echo "\n\nAdd new message Msg4 with WC=2"
curl -X POST http://0.0.0.0:8000/message \
-H "Content-Type: application/json" \
-d '{
    "value": "Msg4",
    "write_concern": 2
}'

echo "\n\nCheck that the message Msg4 is returned from Master and Secondary 2- we are not waiting for Secondary 1:"
echo "Master records: "
 curl http://0.0.0.0:8000/messages
echo "\nSecondary 1 records: "
 curl http://0.0.0.0:8001/messages
echo "\nSecondary 2 records: "
curl http://0.0.0.0:8002/messages

echo "\n\nSleep 10 seconds - all messages should be already synchronized on all nodes:"
sleep 10s
echo "\nMaster records: "
 curl http://0.0.0.0:8000/messages
echo "\nSecondary 1 records: "
 curl http://0.0.0.0:8001/messages
echo "\nSecondary 2 records: "
curl http://0.0.0.0:8002/messages

echo "\n\nInit a 10 second delay on Secondary 1 and Secondary 2 for the next request"
curl -X POST http://0.0.0.0:8001/delay \
-H "Content-Type: application/json" \
-d '{
    "value": 10
}'
curl -X POST http://0.0.0.0:8002/delay \
-H "Content-Type: application/json" \
-d '{
    "value": 10
}'

echo "\n\nAdd new message Msg5 with WC=1"
curl -X POST http://0.0.0.0:8000/message \
-H "Content-Type: application/json" \
-d '{
    "value": "Msg5",
    "write_concern": 1
}'

echo "\n\nCheck that the message Msg5 is returned from Master only:"
echo "Master records: "
 curl http://0.0.0.0:8000/messages
echo "\nSecondary 1 records: "
 curl http://0.0.0.0:8001/messages
echo "\nSecondary 2 records: "
curl http://0.0.0.0:8002/messages


echo "\n\nSleep 10 seconds - all messages should be already synchronized on all nodes:"
sleep 10s
echo "\nMaster records: "
 curl http://0.0.0.0:8000/messages
echo "\nSecondary 1 records: "
 curl http://0.0.0.0:8001/messages
echo "\nSecondary 2 records: "
curl http://0.0.0.0:8002/messages

echo "\n\nSelf-test finished\n"