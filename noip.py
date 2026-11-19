#!/usr/bin/python3
# -*- coding: utf-8 -*-
'''
把某個 No-IP 主機名稱更新成「這台機器目前的對外 IP」（官方 dynupdate API，只用標準庫）。

  noip.py DOMAIN [--cred FILE] [--ip IP]

  --cred  含 username=... / password=... 兩行的 shell 檔（只讀取、不執行），預設 ~/.noip.cred
          帳密不上命令列，ps 看不到
  --ip    指定 IP；不給就由 No-IP 以請求來源 IP 判定
  結束碼  0 = good / nochg，其他 = 失敗（nohost 帳號下沒這主機、badauth 帳密錯、911 對方故障…）

排程與各主機的對應見 README.md。
'''
import re, sys, ssl, base64, argparse
import urllib.request, urllib.parse
from time import sleep
from datetime import datetime, timezone

API = 'https://dynupdate.no-ip.com/nic/update'

def tls_context():
    '''仍驗證憑證與主機名稱，只放寬 Python 3.13 的 X509 嚴格檢查：
    有 SSL 檢查的網路（公司代理、自簽中繼 CA）常見 "Basic Constraints of CA cert not marked critical"'''
    ctx = ssl.create_default_context()
    ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return ctx

def read_cred(path):
    d = {}
    for line in open(path):
        m = re.match(r'\s*(?:export\s+)?(username|password)=(["\']?)(.*)\2\s*$', line)
        if m:
            d[m.group(1)] = m.group(3)
    return d['username'], d['password']

def update(domain, user, password, ip='', tries=3):
    q = {'hostname': domain, **({'myip': ip} if ip else {})}
    req = urllib.request.Request(f'{API}?{urllib.parse.urlencode(q)}', headers={
        'Authorization': 'Basic ' + base64.b64encode(f'{user}:{password}'.encode()).decode(),
        'User-Agent': 'noip.py/2',
    })
    for i in range(tries):
        try:
            return urllib.request.urlopen(req, timeout=15, context=tls_context()).read().decode().strip()
        except OSError as e:     # URLError / HTTPError / timeout
            res = f'error {e!r}'
            if i < tries - 1:
                sleep(2 << i)
    return res

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('domain')
    p.add_argument('--cred', default='~/.noip.cred')
    p.add_argument('--ip', default='')
    a = p.parse_args(argv)
    import os
    res = update(a.domain, *read_cred(os.path.expanduser(a.cred)), ip=a.ip)
    print(datetime.now(timezone.utc).isoformat(), a.domain, res, flush=True)
    return 0 if res.startswith(('good', 'nochg')) else 1

if __name__ == '__main__':
    sys.exit(main())
