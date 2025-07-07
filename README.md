# Freak

> \~(´ω\`)\~
> (Josip Broz Tito, possibly)

**Freak** (as in extremely interested into something, NOT as in predator) is a in-development FOSS and sovereign alternative to Reddit (and an attempt to revive Ruqqus from scratch). The socio-moral reasons are beyond the scope of this README.

## Installation

* First make sure you have these requirements:
    * Unix-like OS (Docker container, Linux or MacOS are all good).
    * **Python** >=3.10. Recommended to use a virtualenv (unless in Docker lol).
    * **PostgreSQL** at least 16.
    * **Redis**/Valkey (as of 0.4.0 unused in codebase).
    * A server machine with a public IP address and shell access (mandatory for production, optional for development/staging).
    * A reverse proxy listening on ports 80 and 443. Reminder to set `APP_IS_BEHIND_PROXY=1` in `.env` !!!
    * Electricity.
    * Will to not give up.
* Clone this repository.
* Fill in `.env` with the necessary information.
    * `DOMAIN_NAME` (you must own it. Don't have? `.xyz` are like $2 or $3 on Namecheap[^1])
    * `APP_NAME`
    * `DATABASE_URL` (hint: `postgresql://username:password@localhost/dbname`)
    * `SECRET_KEY` (you can generate one with the command `cat /dev/random | tr -dc A-Za-z0-9_. | head -c 56`)
    * `PRIVATE_ASSETS` (you must provide the icon stylesheets here. Useful for custom CSS / scripts as well)
    * `APP_IS_BEHIND_PROXY` (mandatory if behind reverse proxy or NAT)
* ...

[^1]: Namecheap is an American company. Don't trust American companies.

## FAQ

...

## License

Licensed under the [Apache License, Version 2.0](LICENSE), a non-copyleft free and open source license.

This is a hobby project, made available “AS IS”, with __no warranty__ express or implied.

I (sakuragasaki46) may NOT be held accountable for Your use of my code.

> It's pointless to file a lawsuit because you feel damaged, and it's only going to turn against you. What a waste of money you could have spent on a vacation or charity, or invested in stocks.

