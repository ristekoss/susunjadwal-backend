# Susun Jadwal Backend

## Requirements

1. Ensure `python` and `pip` are installed
2. Create virtual environment using `python3 -m venv env`
3. Activate virtualenv `source ./env/bin/activate`
4. `pip install -r requirements.txt`
5. Run `FLASK_ENV="development" flask run`

## Configuration

### Development

MongoDB using docker:
`docker run --rm -d -p 27017:27017 --name=test-mongo mongo`

Stop database:
`docker stop test-name`

By default, Flask access MongoDB on `localhost:27017` with database named `test`.

### Production

1. Set database admin username and password at `start_db.sh`
2. Run `./start_db.sh` to create docker container named `ristek-mongo`
3. Run `docker exec -it ristek-mongo mongo -u <admin_username>` to execute `mongo`
4. Create database: `use <db_name>`
5. Create user for database:

```
db.createUser(
    {
        user: "<db_user>",
        pwd: "<db_pwd>",
        roles:[
            {
                role: "readWrite",
                db: "<db_name>"
            }
        ]
    }
);
```

6. Run `./start.sh`
7. Don't forget to provide `credentials.json` in scraper folder

## License

See LICENSE.md. This software actually goes a long way back, thank you so much to everyone involved.
