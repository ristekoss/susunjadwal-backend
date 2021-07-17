# Susun Jadwal Backend

## Requirements

1. `python` and `pip`
2. `docker`

## Configuration

### Development

1. Create virtual environment using `python3 -m venv env`
2. Activate virtualenv `source ./env/bin/activate`
3. Install requirements `pip install -r requirements.txt`
4. Add your credential to scrap schedule from SIAK in `scraper/credentials.json` with the following structure:

```
{
    "<kd_org>": {
        "username": "<username>",
        "password": "<password>"
    }
}
```

You can also see `scraper/credentials.template.json` for example and `sso/additional-info.json` for list of `kd_org`.

5. Start database using `bash start_db.sh`
6. Go to mongo console by running `docker exec -it ristek-mongo mongo -u <admin_username>`
7. Create database by running `use <db_name>`. By default, Flask use database named `test` so it becomes `use test`
8. Create user for database:

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
You can quit mongo console now by using Ctrl + D.

9. Create config file, `instance/config.cfg`. You can see `instance/config.template.cfg` for example and edit db name, username, and password to match the one you created before
10. Run `docker-compose up -d` to start the rabbit mq
11. Create `.env` file from `.env.example` file
12. Finally, run Flask by using `FLASK_ENV="development" flask run`

### Production

#### Old
> We actually have a slightly different setup in the real Ristek server. For future maintainers, you may want to contact past contributors.

1. Do everything in development step **except** step no 10, running Flask. Don't forget to modify `instance/config.cfg`, `start_db.sh`, and `scraper/credentials.json` if you want to
3. Run gunicorn using `bash start.sh`
4. Set your Nginx (or other reverse proxy of your choice) to reverse proxy to `sunjad.sock`. For example, to reverse proxy `/susunjadwal/api` you can set

```
location ^~ /susunjadwal/api {
    proxy_set_header Host $http_host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_pass http://unix:/path/to/susunjadwal/backend/sunjad.sock;
}
```
4. Run the schedule scrapper cron job using `crontab -e` and add the line to run `cron.sh`. For example, to run it every 10 minutes add `*/10 * * * * bash /path/to/susunjadwal/backend/cron.sh`

#### New
1. Do everything in development step **except** step no 10, running Flask.
2. Create `config.cfg` and fill the DB credentials according the given specification in `docker-compose-deploy.yaml` (host must be `mongo`)
3. Run `docker-compose -f docker-compose-deploy.yaml up -d` to execute all

## License

See LICENSE.md. This software actually goes a long way back, thank you so much to everyone involved.
