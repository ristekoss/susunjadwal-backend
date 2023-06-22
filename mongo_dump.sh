MONGO_CONTAINER_ID=$(sudo docker ps -aqf "name=susunjadwalbackend_mongo")
DATE=$(date '+%Y-%m-%d')
if [ ! -d "mongodump" ]; then
    mkdir -p "mongodump"
fi
docker exec $MONGO_CONTAINER_ID sh -c 'mongodump --authenticationDatabase admin -u root-user -p root-user --db backend --archive' > mongodump/mongo_$DATE.dump