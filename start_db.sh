#!/bin/bash

MONGO_ADMIN_USER="nasyaoris"
MONGO_ADMIN_PASS="nasyanada"

docker run -d \
	--name ristek-mongo \
	--restart always \
	-p 37017:27017 \
	-e MONGO_INITDB_ROOT_USERNAME=$MONGO_ADMIN_USER \
	-e MONGO_INITDB_ROOT_PASSWORD=$MONGO_ADMIN_PASS \
       	mongo
