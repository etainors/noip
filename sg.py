#!/usr/bin/python3
# -*- coding: utf-8 -*-
'''
跑在 EC2：監看一組 No-IP 主機名稱解析出的 IP，變了就同步 AWS security group 的 SSH 規則。
規則的 Description = sg.json 的名稱；一律先加新的再撤舊的（不會中途把自己鎖在外面）；
以 SG 現有規則為準，不存本地狀態。需要 aws CLI 與 ec2 權限。

  sg.py [--config sg.json]             持續跑，每 interval 秒一次（建立 break 檔可停止）
  sg.py --once [--dry]                 只跑一次；--dry 只列出會做什麼
'''
import os, sys, json, socket, argparse, subprocess
from time import sleep
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))

def resolve(domain):
    try:
        return sorted({i[4][0] for i in socket.getaddrinfo(domain, None, socket.AF_INET)})
    except socket.gaierror:
        return []

def aws(*args):
    return json.loads(subprocess.check_output(['aws', 'ec2', *args]) or '{}')

def current(gid, port):
    '''SG 上這個 port 的規則 -> {Description: {cidr, ...}}'''
    out = {}
    for p in aws('describe-security-groups', '--group-ids', gid)['SecurityGroups'][0]['IpPermissions']:
        if p.get('IpProtocol') == 'tcp' and p.get('FromPort') == port and p.get('ToPort') == port:
            for r in p['IpRanges']:
                out.setdefault(r.get('Description', ''), set()).add(r['CidrIp'])
    return out

def plan(want, have):
    '''want / have: {name: {cidr}} -> (要加, 要撤) 兩個 [(name, cidr)]；解析不到（want 為空）的名稱不動'''
    add = [(n, c) for n, cs in want.items() if cs for c in sorted(cs - have.get(n, set()))]
    rev = [(n, c) for n, cs in want.items() if cs for c in sorted(have.get(n, set()) - cs)]
    return add, rev

def perm(cidr, port, desc=None):
    r = f'CidrIp={cidr}' + (f',Description={desc}' if desc else '')
    return f'IpProtocol=tcp,FromPort={port},ToPort={port},IpRanges=[{{{r}}}]'

def run_once(conf, dry=False):
    gid, port = conf['group_id'], conf.get('port', 22)
    want = {n: {f'{ip}/32' for ip in resolve(d)} for n, d in conf['watch'].items()}
    for n, d in conf['watch'].items():
        print(n, d, *sorted(want[n]) or ['(沒解析，略過)'])
    add, rev = plan(want, current(gid, port))
    for n, c in add:
        print('auth', n, c)
        if not dry:
            aws('authorize-security-group-ingress', '--group-id', gid, '--ip-permissions', perm(c, port, n))
    for n, c in rev:
        print('revoke', n, c)
        if not dry:
            aws('revoke-security-group-ingress', '--group-id', gid, '--ip-permissions', perm(c, port))

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--config', default=os.path.join(HERE, 'sg.json'))
    p.add_argument('--once', action='store_true')
    p.add_argument('--dry', action='store_true')
    a = p.parse_args(argv)
    conf = json.load(open(a.config))
    while True:
        print(datetime.now(timezone.utc).isoformat(), flush=True)
        try:
            run_once(conf, a.dry)
        except Exception as e:     # aws 暫時失敗不要讓常駐程式死掉
            print('fail', repr(e), flush=True)
        if a.once or os.path.isfile(os.path.join(HERE, 'break')):
            return
        sleep(conf.get('interval', 300))

if __name__ == '__main__':
    main()
