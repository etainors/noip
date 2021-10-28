#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# 定時執行
# add: /etc/crontab
# 0,10,20,30,40,50	*	*	*	*	admin	/var/services/homes/admin/noip.sh
# restart Synology NAS
#
# 開機執行
# edit: /etc/init.d/noip.sh
# add 8 lines:
#! /bin/sh
### BEGIN INIT INFO
# Provides:       noip
# Required-Start: $all
# Required-Stop:
# Default-Start:  2 3 4 5
# Default-Stop:   0 1 6
### END INIT INFO
#
# add line: /usr/bin/python3 /home/ubuntu/noip.py
# $ sudo chmod 755 /etc/init.d/noip.sh
# $ sudo update-rc.d noip.sh defaults
# remove:
# $ sudo update-rc.d noip.sh remove
import sys, requests
from bs4 import BeautifulSoup
from time import sleep
from datetime import datetime
bs = lambda i:BeautifulSoup(i, 'html.parser')

G = {'web':{}, 'soup':{}, 'data':{}}
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.114 Safari/537.36'

def log(s):
    t = datetime.utcnow().isoformat()
    print(t, s)
    open(PATH_NOIP_LOG, 'a').write(t+'\t'+s+'\n')

# 使用noip的API
def dynupdate(username, password, hostname, ip=''):
    url = 'https://dynupdate.no-ip.com/nic/update?hostname='+hostname+('&myip='+ip if ip else '')
    log(requests.get(url, auth=(username, password)).content.decode('utf8').strip())

def login(username, password):
    t = 1
    while t < 1000:
        s = requests.Session()

        # 讀登入頁取token
        log('read login')
        G['web'][0] = s.get('https://www.noip.com/login', headers={'User-Agent':UA})
        G['soup'][0] = bs(G['web'][0].content)

        # 登入
        log('login')
        G['web'][1] = s.post('https://www.noip.com/login', data={
            'username':username,
            'password':password,
            'submit_login_page':'1',
            '_token':G['soup'][0].find('input', {'name':'_token'})['value'],
            'Login':''
        })

        # 檢查
        G['soup'][1] = bs(G['web'][1].content)
        if G['soup'][1].find('title').text.strip() == 'My No-IP':
            log('login success')
            return s
        else:
            log('login fail')
            open('tmp.html', 'wb').write(G['web'][0].content)
            sleep(t)
            t <<= 1


# 讀管理頁
def manage(s, log_id=2):
    log('read manage')
    G['web'][log_id] = s.get('https://www.noip.com/members/dns/')
    G['soup'][log_id] = bs(G['web'][log_id].content)
    r = []
    for i in G['soup'][log_id].select('tr.table-non-striped-row'):
        r.append([i.find('td', {'class':'ml-20'}).text.strip(), i.find('td', {'class':'withright'}).text.strip(), 'https://www.noip.com/members/dns/'+i.find('a', {'class':'btn-labeled'})['href']])
    return r

# 更新IP
def modify(s, url, ip, log_id=3):
    log('read modity')
    G['web'][log_id] = s.get(url)
    G['soup'][log_id] = bs(G['web'][log_id].content)
    G['data'][log_id] = dict((i, G['soup'][log_id].find('input', {'name':i})['value']) for i in ['host[domain]', 'host[host]', 'host[port][ip]', 'host[port][port]', 'host[ttl]', 'nlocations', 'token'])
    G['data'][log_id].update({
        'do':'update',
        'host[group_id]':'0',
        'host[ip]':ip,
        'host[mx][0][priority]':'5',
        'host[redirect][protocol]':'http',
        'host[type]':'a',
    })
    log('modity ip to '+ip)
    s.post(url, data=G['data'][log_id])

# 使用網頁，改host_to的ip為host_from的ip
def main_v1(username, password, host_from, host_to):
    s = login(username, password)
    data = manage(s)

    # 不需更新
    if len(set([i[1] for i in data])) == 1:
        log('no need modify, logout')
        s.get('https://www.noip.com/logout')
        exit()

    new_ip = ''
    mod_url = []
    for i in data:
        if i[0] == host_from:
            new_ip = i[1]
        if i[0] in host_to:
            mod_url.append(i[2])

    # 偵錯
    if not new_ip or len(mod_url) != len(host_to):
        log('host_from/host_to setting error')
        s.get('https://www.noip.com/logout')
        exit()

    # 更新IP
    for url in mod_url:
        modify(s, url, new_ip)

    # 檢查結果
    log('read manage')
    r = manage(s, 4)
    if set([i[1] for i in r]) != set([new_ip]):
        log('update '+new_ip+' error')
        s.get('https://www.noip.com/logout')
        exit()

    # 登出
    log('logout')
    s.get('https://www.noip.com/logout')
    log('update to '+new_ip)

# 使用網頁，改host的ip
def main(username, password, host, ip):
    s = login(username, password)
    data = manage(s)

    # 不需更新
    for i in data:
        if i[0] == host and i[1] == ip:
            log('no need modify, logout')
            s.get('https://www.noip.com/logout')
            exit()

    # 偵錯
    if host not in [i[0] for i in data]:
        open('tmp.html', 'wb').write(G['web'][2].content)
        log(host+' not in account: '+username)
        s.get('https://www.noip.com/logout')
        exit()

    # 更新IP
    for i in data:
        if i[0] == host:
            modify(s, i[2], ip)

    # 檢查結果
    r = manage(s, 4)
    for i in r:
        if i[0] == host:
            if i[1] != ip:
                log('update '+host+' to '+ip+' error')
                s.get('https://www.noip.com/logout')
                exit()

    # 登出
    log('logout')
    s.get('https://www.noip.com/logout')
    log(host+' update to '+ip)

PATH_NOIP_LOG = 'noip.log'

if __name__ == '__main__':
    import argparse
    if len(sys.argv) > 1 and sys.argv[1] == 'dyn':
        parser = argparse.ArgumentParser()
        parser.add_argument('mod', help='dyn: use noip api')
        parser.add_argument('-u', '--username', default='', help='noip login username')
        parser.add_argument('-p', '--password', default='', help='noip login password')
        parser.add_argument('-d', '--domain', default='', help='noip domain to update')
        parser.add_argument('-i', '--ip', default='', help='noip ip to update to')
        args = parser.parse_args()
        dynupdate(args.username, args.password, args.domain, args.ip)
    elif len(sys.argv) > 1 and sys.argv[1] == 'h2h':
        parser = argparse.ArgumentParser()
        parser.add_argument('mod', help='h2h: use web, ip from host to hosts in same account')
        parser.add_argument('-u', '--username', default='', help='noip login username')
        parser.add_argument('-p', '--password', default='', help='noip login password')
        parser.add_argument('-f', '--host_from', default='', help='ip from the host')
        parser.add_argument('-t', '--host_to', default='', help='ip to the hosts, separate by comma')
        args = parser.parse_args()
        main_v1(args.username, args.password, args.host_from, args.host_to.split(','))
    elif len(sys.argv) > 1 and sys.argv[1] == 'i2h':
        parser = argparse.ArgumentParser()
        parser.add_argument('mod', help='i2h: use noip web interface')
        parser.add_argument('-u', '--username', default='', help='noip login username')
        parser.add_argument('-p', '--password', default='', help='noip login password')
        parser.add_argument('-d', '--domain', default='', help='noip domain to update')
        parser.add_argument('-i', '--ip', default='', help='noip ip to update to')
        args = parser.parse_args()
        main(args.username, args.password, args.domain, args.ip)
    else:
        parser = argparse.ArgumentParser()
        parser.add_argument('mod', help='you can use [dyn|h2h|i2h], dyn -h, h2h -h, i2h -h for more detail. And mod must be first argument.')
        args = parser.parse_args()

'''
exit()
python3
from noip import *
'''
