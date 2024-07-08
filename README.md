# Susun Jadwal

Susun Jadwal is an open source tool to plan class schedules for university students, 
developed by Ristek Fasilkom UI. https://susunjadwal.cs.ui.ac.id/

In the spirit of Open Source Software, *everyone* is welcome to contribute to Susun Jadwal! 
See the Contributing Guide below for more.

## Structure

```
app/                    // general views
models/                 // mongoDB models
scraper/                // courses (academic.ui.ac.id) scraper
sso/                    // SSO UI authentication logic
requirements.txt        // python dependency list
scripts/                // (utility scripts)
├── init-mongo.sh       // script to create non-root mongoDB user
├── launch.sh           // main script to start flask
├── mongo_dump.sh       // script to dump mongoDB data to .dump file
└── start.sh            // alternative script to start flask
.env.example            // template for .env file
dev.docker-compose.yml  // docker-compose for mongo and rmq
docker-compose.yml      // docker-compose for mongo, rmq, & server
```

## Contributing Guide

*Everyone* is welcome to contribute to Susun Jadwal!
Feel free to make a contribution by submitting a pull request.
You can also report bugs and request features / changes by creating a new 
[Issue](https://github.com/ristekoss/susunjadwal-backend/issues/new).

For in-depth discussion, please join RistekOSS's Discord.

## Development

### Requirements

1. `python` (3.12.1), and `pip`
2. `docker`

### Installing

The following steps will assume you have already set up a python virtual environment, 
and will use `dev.docker-compose.yml`. 

1. Boot up MongoDB and RabbitMQ: 
    ```docker-compose -f dev.docker-compose.yaml up```

2. Populate `.env`, using `.env.example` as reference.

3. Connect to MongoDB and create a non-root user.
    ```
    mongosh -u <root-username>
    // enter password when prompted
    
    use <db_name>;
    db.createUser({user: "<MONGODB_USERNAME>", pwd: "<MONGODB_PASSWORD>", roles: ["readWrite"]});
    // response should be '{ok: 1}', use these credentials in your .env secrets
    ```

4. Boot up the Flask server:
    ```export PORT=8000 && bash scripts/launch.sh```

5. Ping the API: `http://localhost:8000/susunjadwal/api/`

### Containerizing the Server

#### For Local

1. Populate `.env`.

2. Run `docker-compose.yml`.

#### For Deployment

While RISTEK uses a different standardized workflow, here is a general guide on deploying.

1. Populate `.env`.

2. Replace line 23-25 in `docker-compose.yml` to pull from [Docker Hub](https://hub.docker.com/r/ristekoss/):

```image: ristekoss/susunjadwal-backend:stable```

3. Modify the credentials in `MONGO_INITDB_XX` environment variables.

4. Build and push image from `Dockerfile`

5. `docker compose up`



## Dump and Restore Database

### Dump
1. Run the dump script: `bash mongo_dump.sh`
2. The result will be a `.dump` file in the directory `./mongodump`.

### Restore
1. Copy dump file to MongoDB Container: `docker cp <path_to_dump_file> susunjadwalbackend_mongo_1:/<path_to_dump_file>`
2. Load dump into DB: `docker exec -it <mongo_container_name> mongorestore -u <root_username> --archive=<file.dump>`
3. Enter `<root_username>`'s password when prompted.
4. You should see the success message: `XX documents successfully restored.`

## Deployment

We use a standardized pipeline for all our products which we invoke from `.github/workflows/deploy-<env>.yaml`

## Legacy Version

To see the version of `susunjadwal-backend` which was maintained and deployed up until 2023, see [5b8f710](https://github.com/ristekoss/susunjadwal-backend/tree/5b8f71068b62a0f1f684c616cb8e40c087861725).

## License

See LICENSE.md. This software actually goes a long way back, thank you so much to everyone involved.
