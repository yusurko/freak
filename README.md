# Freak

> \~(´ω\`)\~
> (Josip Broz Tito, possibly)

**Freak** (as in extremely interested into something, NOT as in predator) is a in-development FOSS and sovereign alternative to Reddit (and an attempt to revive Ruqqus from scratch). The socio-moral reasons are beyond the scope of this README.

## Installation

* First make sure you have these requirements:
    * Unix-like OS (Docker container, Linux or MacOS are all good).
    * **Python** >=3.10. Recommended to use a virtualenv (unless in Docker lol).
    * **PostgreSQL** at least 16.
    * **Redis**/Valkey (as of 0.4.0 unused in codebase -_-).
    * **Docker** and **Docker Compose**.
    * A server machine with a public IP address and shell access (mandatory for production, optional for development/staging).
        * First time? I recommend a VPS. The cheapest one starts at €5/month, half a Spotify subscription.
        * You must have **shell access**. FTP only is not enough.
    * A domain (mandatory for production).
        * You must have bought it beforehand. Don't have? `.xyz` are like $2 or $3 on Namecheap[^1]
        * For development, tweaking `/etc/hosts` or plain running on `localhost:5000` is usually enough.
    * A reverse proxy (i.e. Caddy or nginx) listening on ports 80 and 443. Reminder to set `APP_IS_BEHIND_PROXY=1` in `.env` !!!
    * Electricity.
    * Will to not give up.
* Clone this repository.
* Fill in `.env` with the necessary information.
    * `SERVER_NAME` (see above)
    * `APP_NAME`
    * `DATABASE_URL` (hint: `postgresql://username:password@localhost/dbname`)
    * `SECRET_KEY` (you can generate one with the command `cat /dev/random | tr -dc A-Za-z0-9_. | head -c 56`)
    * `PRIVATE_ASSETS` (you must provide the icon stylesheets here. Useful for custom CSS / scripts as well)
    * `APP_IS_BEHIND_PROXY` (mandatory if behind reverse proxy or NAT)
    * `IMPRESSUM` (if you host or serve your site in Germany[^2]. Lines are separated by double colons `::`)
* Adjust `docker-compose.yml` to your liking.
* Run `docker compose build`.
* Create a systemd unit file looking like this:
```systemd
[Unit]
Description=Freak
## using Caddy? replace nginx.service with Caddy.service. Yes, twice
Wants=nginx.service docker.service
After=nginx.service docker.service

[Service]
Type=simple
## REPLACE it with your path
WorkingDirectory=/path/to/repository/freak
ExecStart=/usr/bin/docker compose up
ExecReload=/usr/bin/docker compose run freak bash ./docker-run.sh r
ExecStop=/usr/bin/docker compose down

[Install]
WantedBy=multi-user.target
```
* Copy the file to `/usr/lib/systemd/system` (with root access)
* Run `sudo systemctl enable --now freak.service`
* Expect no red text or weird error gibberish. If there is, you did not follow the tutorial: read it from the start again.
* Congratulations! Your Freak instance is up and running


[^1]: Namecheap is an American company. Don't trust American companies.
[^2]: Not legal advice.

## FAQ

### Why another Reddit clone? 

I felt like it.

### Will Freak be federated?

It's on the roadmap. However, it probably won't be fully functional if not after at least twenty feature releases. Therefore, wait patiently.

Freak is currently implementing the [SIS](https://yusur.moe/protocols/sis.html).

### What is your legal contact / Impressum?

You have to configure it yourself by setting `IMPRESSUM` in `.env`.

I only write the code. I am not accountable for Your use (see [License](#license)).

## License

Licensed under the [Apache License, Version 2.0](LICENSE), a non-copyleft free and open source license.

This is a hobby project, made available “AS IS”, with __no warranty__ express or implied.

I (sakuragasaki46) may NOT be held accountable for Your use of my code.

> It's pointless to file a lawsuit because you feel damaged, and it's only going to turn against you. What a waste of money you could have spent on a vacation or charity, or invested in stocks.

