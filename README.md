# noip

Keep No-IP hostnames pointing at the current public IP of each machine, and keep an AWS security group's SSH allow-list in sync with those hostnames.

```
each host --cron--> noip.py --> No-IP (hostname -> that host's public IP)
                                      | DNS
EC2 -- sg.py (every 5 min) <----------+
   '- resolved IP changed -> update the security group's port 22 rules
```

Two independent programs, standard library only:

| File | Runs on | Does |
|---|---|---|
| `noip.py DOMAIN [--cred FILE] [--ip IP]` | every host you want to track | set DOMAIN to this host's public IP (official dynupdate API) |
| `sg.py [--once] [--dry]` | a machine with the `aws` CLI | resolve the names in `sg.json` and sync the security group |

## noip.py

`--cred` points to a shell-style file (default `~/.noip.cred`) with two lines, `username=...` and `password=...`. It is only read, never executed, so the password never appears on the command line. Without `--ip`, No-IP uses the request's source IP. Exit code 0 means `good`/`nochg`; anything else (`nohost`, `badauth`, ...) is a failure.

```
*/10 * * * *  python3 /path/to/noip.py myhost.ddns.net --cred /path/to/cred
```

## sg.py

Copy `sg.example.json` to `sg.json` and fill in the security group id and `watch` (rule description -> hostname). Rules whose description matches a name are reused and kept in step with the DNS answer: new IPs are added first, then stale ones revoked, so the allow-list never has a gap. Hostnames that do not resolve are left alone. `--once --dry` prints what would change without touching AWS. Create a file named `break` next to the script to stop the loop.

## Tests

```
python3 -m unittest discover -s tests
```
