#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import json
import os
import time
import subprocess
from datetime import datetime
from threading import Thread
from threading import Event
import logging
from decimal import Decimal
import gc
import signal

try:
    import Queue
except ImportError:
    import queue as Queue
try:
    from urllib2 import (
        urlopen,
        Request,
        URLError,
    )
except ImportError:
    from urllib.request import (
        urlopen,
        Request,
        URLError,
    )

from utils import SingleInstance
from utils import ping_log as log
import copy

IPM_CACHE_DIR = '/opt/cbc/ipm/cache'
IPM_EVENT_CACHE_FILE = os.path.join(IPM_CACHE_DIR, 'event_used_data_cache.json')


def ensure_cache_dir(cache_dir):
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)


def load_event_cache():
    try:
        with open(IPM_EVENT_CACHE_FILE, 'r') as f:
            return json.loads(f.read())
    except Exception:
        return None


def save_event_cache(now_time, seq, new_info, last_update_info):
    ensure_cache_dir(IPM_CACHE_DIR)
    date_time_str = datetime.fromtimestamp(now_time).strftime('%Y-%m-%d %H:%M:%S')
    need_saved_info = {}
    for item in last_update_info + new_info:
        need_saved_info[item['metric'] + item['tags']] = item
    info = {
        'last_update_time': now_time,
        'last_date_time': date_time_str,
        'last_update_seq': seq,
        'last_update_info': list(need_saved_info.values()),
    }
    with open(IPM_EVENT_CACHE_FILE, 'w') as f:
        f.write(json.dumps(info, indent=4))


def build_connection_down_status(target, target_result):
    if 'is_check_connection_down' not in target or not target.get('is_check_connection_down'):
        return None
    outbound_interface = target.get('outbound_interface')
    if not outbound_interface:
        return None
    # connection name 从 ipm_name 解析：去掉前缀 IPM4（第5个字符起），按 _ 分割取第一段，缺省回退 outbound_interface
    ipm_name = target.get('ipm_name') or ''
    if ipm_name:
        connect_name = ipm_name[4:].split('_', 1)[0]
    else:
        connect_name = outbound_interface
    threshold = target.get('check_connection_down_threshold', 10)
    try:
        threshold = float(threshold)
    except Exception:
        threshold = 10
    lost_rate = target_result.get('rttLostRate')
    if lost_rate is None:
        return None
    packet_loss_rate = round(float(lost_rate) * 100, 4)
    value = 'PROBLEM' if packet_loss_rate > threshold else 'OK'
    return {
        'metric': 'connection.down',
        'tags': 'connect_name={0}'.format(connect_name),
        'value': value,
        'packet_loss_rate': packet_loss_rate,
        'outbound_interface': outbound_interface,
        'connect_name': connect_name,
    }


def push_connection_down_event(event_info, now_time_str):
    if event_info['value'] == 'PROBLEM':
        message = 'Connection {0} quality has degraded. Packet loss rate: {1:g}%.'.format(
            event_info['connect_name'],
            event_info['packet_loss_rate']
        )
    else:
        message = 'Connection {0} quality has recovered. Packet loss rate: {1:g}%.'.format(
            event_info['connect_name'],
            event_info['packet_loss_rate']
        )
    status = event_info['value']
    value = int(event_info['packet_loss_rate']) if float(event_info['packet_loss_rate']).is_integer() else event_info['packet_loss_rate']
    push_event_py = '/root/cbc/agent/push_event.py'
    cmd = (
        'python {0} --event-type connection.down '
        '--status {1} --severity 0 --message "{2}" --object="{3}" '
        '--value={4} --unit=% --trigger-time "{5}"'
    ).format(push_event_py, status, message, event_info['tags'], value, now_time_str)
    try:
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
        p.communicate()
    except Exception as e:
        log.error('push_connection_down_event() {0}'.format(cmd))
        log.error(e)


def cmd_process(cmd):
    log.debug("cmd_process() start exec cmd:{0}\n".format(cmd))
    args = cmd.split()
    try:
        p = subprocess.Popen(
            args,
            stdin=None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True
        )
        return p
    except Exception as e:
        log.error('cmd_process() {0}'.format(cmd))
        log.error(e)
        return None


class ArgusClient(object):

    def __init__(self, argus_port, endpoint):
        """argus 客户端

        :param argus_port: argus port
        :param endpoint: endpoint
        """
        self.argus_port = str(argus_port)
        self.argus_ip = "127.0.0.1"
        self.request_path = "/v1/push"
        self.endpoint = endpoint

    def get_data_to_argus(self, need_clean_data):
        '''
        need_clean_data demo:
        [
        {u'rttMin': -1.0, u'rttLostRate': 1.0, u'rttNum': 0,
        u'rttLoss': 300, u'timestamp': 1610949161,
        u'ipm_id': u'6036ce05-5fd2-40d8-93d0-a0eb9bdf4b20', u'rttJitter': -1.0,
        u'rttMax': -1.0, u'ip_address': u'10.110.0.14', u'step': 300,
        u'rttAvailRate': 0.0, u'rttAvg': -1.0, u'rttTTL': -1.0}
        ]
        :return: argus agent metric list
        '''
        keys = [
            'rttMin',
            'rttMax',
            'rttAvg',
            'rttNum',
            'rttLoss',
            'rttJitter',
            'rttLostRate',
            'rttTTL',
            'rttAvailRate',
        ]
        metric = "ipm.{0}"
        agent_data_list = []
        for data_dict in need_clean_data:
            ipm_id = data_dict.get("ipm_id")
            timestamp = data_dict.get("timestamp")
            step = data_dict.get("step")
            for k, v in data_dict.items():
                if k in keys:
                    agent_data_list.append(
                        {"endpoint": self.endpoint, "metric": metric.format(k), "timestamp": timestamp,
                         "step": step,
                         "value": v, "counterType": "GAUGE", "tags": "ipm_id={0}".format(ipm_id)})
        return agent_data_list

    def post_data_to_argus(self, worker_id, data_list):
        '''
        发送数据到 argus
        :param data_list: 数据 list
        :return: bool
        '''
        status = 500
        response = None
        try:
            mid = json.dumps(data_list)
            _url = "http://" + self.argus_ip + ":" + self.argus_port + self.request_path
            request = Request(url=_url, data=mid.encode("utf-8"))
            response = urlopen(request, timeout=30)
            status = response.getcode()
            response.read()
            log.info('Worker {0} posted {1} metrics to argus and got status {2}.'.format(worker_id, len(data_list), status))
            log.debug("data is [ " + mid + " ] ")
        except Exception as e:
            log.error('Worker {0} posted {1} metrics to argus got error {2} and code {3}'.format(worker_id, len(data_list), str(e), status))
            return False
        finally:
            if response:
                try:
                    response.close()
                except Exception:
                    pass
        return True

    def insert(self, worker_id, target_results):
        """
        将监控结果写入发送到 argus agent
        :param target_results: 收集到，并且清洗过的数据
        :return: bool
        """
        if not target_results:
            return True

        # 拿到 argus 的数据格式
        argus_list = self.get_data_to_argus(target_results)
        # 将数据推到argus
        res = self.post_data_to_argus(worker_id, argus_list)
        return res


class PingWorkerBase(Thread):
    def __init__(
            self,
            targets,
            f_ping_path='/usr/bin/fping',
            argus_client=None,
            queue=None,
            ip_version=4,
            source_address='',
            count=300,
            report_interval=300,
            request_interval=1000, ## Reserve 10ms for task scheduling and data collection
            connection_down_queue=None,
    ):
        """生产者线程, 对目标进行 ipm 监控

        :param targets: 监控目标
        :param f_ping_path: fping 路径
        :param argus_client: argus_client 实例, 如果不是长期监控, 则监控结果不进队列, 直接传到 argus
        :param queue: Queue.Queue 实例, 用来存监控的结果
        :param durable: 是否长期监控
        :param ip_version: targets 是 v4 还是 v6 地址
        :param source_address: 发起监控的本地地址
        :param count: 每个监控周期的发包数
        :param report_interval: 监控周期的间隔, 单位是秒, 必须不小于 count * request_interval / 1000
        :param request_interval: 发包间隔, 单位是毫秒
        :param connection_down_queue: Queue.Queue 实例, 用来推送 connection down 事件
        """
        super(PingWorkerBase, self).__init__()
        self.setDaemon(True)

        self.count = count
        self.path = f_ping_path
        self.argus = argus_client
        self.ip_version = ip_version
        self.t_address = 'ip_address'
        self.report_interval = report_interval
        self.request_interval = request_interval
        self.source_address = source_address
        self.queue = queue
        self.connection_down_queue = connection_down_queue
        self.result = {}
        self.process_of_f_ping = {}
        self.processes_of_ping = {}
        self.timestamp = None
        self.shutdown_flag = Event()

    def f_ping(self):
        raise Exception("FPing must be rewritten")

    def ttl__ping(self):
        '''
        为了拿到 target ip 的 TTL的value
        :return:
        '''
        ps = {}
        path = 'ping'
        if self.ip_version == 6:
            path = 'ping6'
        if self.source_address:
            t = '{0} -I ' + self.source_address + ' -i 0.2 -n -c 4 {1}'
        else:
            t = '{0} -i 0.2 -n -c 4 {1}'
        for target_address, target_dict in self.targets.items():
            cmd = t.format(path, target_address)
            log.debug("target_address is :{0}\n".format(target_address))
            p = cmd_process(cmd)
            ps[target_address] = p
        self.processes_of_ping = ps

    def __rtt_jitter(self, rtt_list, avg):
        num = len(rtt_list)
        if num > 1:
            sd_sq = sum([float((self.convert(rtt) - self.convert(avg))) ** 2 for rtt in rtt_list])
            st_dev = float(self.convert(sd_sq) / (self.convert(num) - 1)) ** 0.5
        else:
            st_dev = -1.0
        return st_dev

    @staticmethod
    def convert(number):
        return Decimal(str(number))

    @staticmethod
    def round_float(rtt_str_dict):
        for key, rtt_value in rtt_str_dict.items():
            if isinstance(rtt_value, float):
                rtt_str_dict[key] = round(rtt_value, 4)
        return rtt_str_dict

    def __calculations(self, rtt_str_list):
        total = len(rtt_str_list)
        rtt_list = [float(i) for i in rtt_str_list if i != '-']
        packet_num = len(rtt_list)
        loss = float(self.convert(total) - self.convert(packet_num))

        if total != 0:
            loss_rate = float(self.convert(loss) / self.convert(total))
            avail_rate = float(self.convert(1) - self.convert(loss_rate))
        else:
            return {
                'rttMin': None,
                'rttMax': None,
                'rttAvg': None,
                'rttNum': None,
                'rttLoss': None,
                'rttJitter': None,
                'rttLostRate': 1.0,
                'rttAvailRate': 0,
            }

        if packet_num > 0:
            avg = float(self.convert(sum(rtt_list)) / self.convert(len(rtt_list)))
            jitter = self.__rtt_jitter(rtt_list, avg)
            rtt_min = min(rtt_list)
            rtt_max = max(rtt_list)
        else:
            failed_num = None
            avg, jitter, rtt_min, rtt_max = [failed_num] * 4

        rtt_dict = {
            'rttMin': rtt_min,
            'rttMax': rtt_max,
            'rttAvg': avg,
            'rttNum': packet_num,
            'rttLoss': loss,
            'rttJitter': jitter,
            'rttLostRate': loss_rate,
            'rttAvailRate': avail_rate,
        }
        return self.round_float(rtt_dict)

    def __calculate_avg_ttl(self, ttls_str_list):
        """
          ttls_str_list in form of ["44" "-" "45" "44"]
          return dictionary of {"rttTTL": <ttl>}
        """
        ttl_val_list = [int(i) for i in ttls_str_list if i != '-']
        ttl_val_len = len(ttl_val_list)
        
        if ttl_val_len < 1:
            return {'rttTTL': -1}
        else:
            return {'rttTTL': int(sum(ttl_val_list)/ttl_val_len) }

    @staticmethod
    def reverse_data(meta_str):
        """
         Input: "43.254.240.53 : 11.1 11.1 349 11.7 15.1 12.4 11.8 11.4"
         Output: ['43.254.240.53', '11.1 11.1 349 11.7 15.1 12.4 11.8 11.4']
        """
        s_list = meta_str[::-1].split(":", 1)
        new_list = []
        for s in s_list[::-1]:
            new_list.append(s[::-1].strip())
        return new_list

    def __wash_output_of_ping(self, target_address, stdout):
        try:
            s = stdout.split('ttl=', 1)[1]
            ttl_end = s.index(' ')
            ttl = float(s[:ttl_end])
        except Exception as e:
            log.error(
                '[ping]: {0}, [Exception]: {1}'.format(
                    target_address, e
                )
            )
            ttl = -1.0

        self.result[target_address] = {
            'timestamp': self.timestamp + self.count,
            'rttTTL': ttl,
            "target_address": target_address
        }

    def __wash_output_of_f_ping(self, output, ipm_ip_tuple_list):
        """
          Calculate metrics based on fping output like:
            2.3.4.5       : 31.1 - 39 44.7 45.1         ## to build rttxxx 
            2.3.4.5 cbc_ttl : 44 - 45 44   43           ## to build rttl
            43.254.240.53 : 11.1 11.1 349 11.7 15.1 
            43.254.240.53 cbc_ttl : 44 - 45 44   43
          ipm_ip_tuple_list is array of IP string for this worker.
        """
        log.debug("FPing output is: {0}\n".format(output.strip()))
        for r in output.strip().split('\n'):
            ## handle TTL measurement
            func_id = 0 ## default is to calculate RTTxxx
            if r.find("cbc_ttl") > 0:
                r = r.replace("cbc_ttl", "")  ## remove "cbc_ttl" keyword
                func_id = 1 ## mark as calculation of TTL
            
            ## handle RTT measurements
            s = self.reverse_data(r)
            if not len(s) == 2:
                log.warning(r)
                log.warning(str(ipm_ip_tuple_list))
                continue
            try:
                ip, res = s
                ip = ip.strip()
                
                # Loop to check if the resulted IP@ is expected                
                for target_address in ipm_ip_tuple_list:
                    if target_address == ip:
                        if func_id == 0:
                            ## Get RTT measurements in form of dict
                            cal_res = self.__calculations(res.split())
                        elif func_id == 1:
                            ## Get TTL measurement in form of dict
                            cal_res = self.__calculate_avg_ttl(res.split())
                        else:
                            continue
                                                                 
                        ## Is it the first time to add target to measurements mapping pair
                        if target_address not in self.result:
                            self.result[target_address] = {
                                "timestamp": self.timestamp + self.count,                            
                                "target_address": target_address,
                                "step": self.report_interval
                            }
                        
                        ## Add RTT or TTL metrics
                        self.result[target_address].update(cal_res)
                        log.debug("Update result per target: {0}".format(json.dumps(self.result[target_address], indent=3)))
                        break
            except Exception as e:
                log.warning(r)
                log.warning(e)

    def wash_output(self):
        '''
        ## No more needed.
        ps = self.processes_of_ping
        for target_address, p in ps.items():  # ip_tuple (ipm_id, target_ip)
            if not p:
                continue
            s, _ = p.communicate()
            self.__wash_output_of_ping(target_address, s)
        '''
        p = list(self.process_of_f_ping.values())[0]
        ipm_ip_tuple_list = eval(list(self.process_of_f_ping.keys())[0])
        # [('02aeca92-1067-4e73-9bfd-ea6d50d4a272', '10.10.1.14')]
        log.debug("Worker fping {0} of slot {1} started to poll for ipm IPs {2}...".format(self.worker_id, self.timestamp, ipm_ip_tuple_list))

        stdout_chunks = []
        stderr_chunks = []

        def drain_stream(stream, chunks):
            try:
                while True:
                    data = stream.read(4096)
                    if not data:
                        break
                    chunks.append(data)
            except Exception:
                return

        timed_out = False
        deadline = time.time() + self.report_interval

        stdout_reader = Thread(target=drain_stream, args=(p.stdout, stdout_chunks))
        stdout_reader.setDaemon(True)
        stdout_reader.start()

        stderr_reader = Thread(target=drain_stream, args=(p.stderr, stderr_chunks))
        stderr_reader.setDaemon(True)
        stderr_reader.start()

        try:
            ## Loop to poll the subprocess status
            while p.poll() is None:
                if self.shutdown_flag.is_set():
                    log.info("Worker fping {0} of slot {1} received TERM signal, stop.".format(self.worker_id, self.timestamp))
                    p.kill()
                    break
                if time.time() >= deadline:
                    timed_out = True
                    try:
                        p.terminate()
                    except Exception:
                        pass
                    grace_deadline = time.time() + 2
                    while p.poll() is None and time.time() < grace_deadline:
                        time.sleep(0.05)
                    if p.poll() is None:
                        p.kill()
                    break
                time.sleep(0.1)

            p.wait()
            stdout_reader.join()
            stderr_reader.join()
        finally:
            try:
                if p.stdout:
                    p.stdout.close()
            except Exception:
                pass
            try:
                if p.stderr:
                    p.stderr.close()
            except Exception:
                pass

        stdout = b''.join(stdout_chunks)
        stderr = b''.join(stderr_chunks)
        if stdout:
            stdout = stdout.decode()
        if stderr:
            stderr = stderr.decode()
        log.debug("Worker fping {0} of slot {1} got stdout:{2}".format(self.worker_id, self.timestamp, stdout))
        log.debug("Worker fping {0} of slot {1} got stderr:{2}".format(self.worker_id, self.timestamp, stderr))
        status = 124 if timed_out else p.returncode
        log.debug("Worker fping {0} of slot {1} got status:{2}".format(self.worker_id, self.timestamp, status))
        if status not in [0, 1, 124]:
            log.warning(
                '[{0}] status: {1}, stdout: {2}, stderr: {3}, source address: {4}'.format(
                    self.path, status, stdout, stderr, self.source_address
                )
            )
        else:
            ## Try best to parse output: note that it is observed that meaningful output is present even with status 1.
            self.__wash_output_of_f_ping(stderr, ipm_ip_tuple_list)

    def ping(self):
        """调用 FPing 和 Ping 工具探测目标地址"""

        self.result = {}
        self.f_ping()
        log.debug("Worker fping {0} of slot {1} started.".format(self.worker_id, self.timestamp))
        if not self.process_of_f_ping:
            return

        ## self.ttl__ping()
        self.wash_output()

    def put(self):
        """将监控结果存入队列"""
        insert_data = []
        for k, v in self.result.items():
            ipm_ids = self.ipm_ids_dict_by_target_address.get(k)
            for ipm_id in ipm_ids:
                ping_value = copy.deepcopy(v)
                ping_value.update({"ipm_id": ipm_id})
                insert_data.append(ping_value)
        self.argus.insert(self.worker_id, insert_data)

    def get_connection_down_status_list(self):
        connection_down_status_list = []
        for target_address, target in self.targets.items():
            target_result = self.result.get(target_address)
            if not target_result:
                continue
            event_info = build_connection_down_status(target, target_result)
            if event_info:
                connection_down_status_list.append(event_info)
        return connection_down_status_list

    def run(self):
        log.debug("Ping worker starts to ping these target: {0}".format(self.targets))
        if not self.targets:
            return
        self.ping()
        self.put()
        ## 生产者侧推送 connection down 状态, 由独立线程按自己的节奏消费
        if self.connection_down_queue is not None:
            connection_down_status_list = self.get_connection_down_status_list()
            if connection_down_status_list:
                self.connection_down_queue.put(connection_down_status_list)
        log.debug('Ping worker stopped.')


class PingWorkerV2(PingWorkerBase):
    def __init__(
            self,
            part_cmd,
            targets,
            f_ping_path='/usr/bin/fping',
            argus_client=None,
            start_time=None,
            worker_id=0,
            connection_down_queue=None,
    ):
        """生产者线程, 对目标进行 ipm 监控

        :param targets: 监控目标
        :param f_ping_path: fping 路径
        :param argus_client: argus_client 实例, 如果不是长期监控, 则监控结果不进队列, 直接传到 argus
        """
        super(PingWorkerV2, self).__init__(targets, connection_down_queue=connection_down_queue)
        self.setDaemon(True)
        self.worker_id = worker_id
        self.part_cmd = part_cmd
        self.tag = part_cmd
        self.path = f_ping_path
        self.argus = argus_client
        self.count = 300
        self.ip_version = 4
        self.t_address = "target_address"
        self.report_interval = 300
        self.request_interval = 1000
        self.source_address = ""
        self.result = {}
        self.process_of_f_ping = {}
        self.processes_of_ping = {}
        self.ipm_ids_dict_by_target_address = {}
        self.targets = self.washed_targets(targets)
        self.timestamp = start_time

    def washed_targets(self, targets):
        """ Multiple targets per fping thread (this worker):
            The target could be duplicated in terms of target IP@, eg when two IPMs are created with exactly same IP target, interval and outgoing interface.
            This function will build two maps:
              #1 self.targets: {"<target_ip_address>" : IPM_object } 
                 which will remove duplicated targets (keep the last one).
              #2 self.ipm_ids_dict_by_target_address: {"<target_ip_address>" : [<IPM_id>] }
                 which records the mapping btw target_ip_address to list of IPM objects for reporting purpose, for example:
                 {
                    "2.2.2.2": ["79d384e5-46da-f192-1c24-f1aec65831ee"], 
                    "8.8.8.8": ["7971b6e8-64cc-4625-66d7-9ccabe339745"], 
                    "43.254.240.53": [ "23f426a3-2255-fb74-6556-ef9411076a28", "9292bba7-d4c9-9050-d141-9211246efedb"]
                 }                 
        """
        self.count = targets[0].get("count")
        # inf = float('inf')
        self.ip_version = targets[0].get("ip_version")
        self.report_interval = targets[0].get("report_interval")
        self.source_address = targets[0].get("source_address")
        new_targets = {}
        for t in targets:
            target_address = t.get("target_address")
            ipm_id = t['ipm_id']
            ipm_ids = self.ipm_ids_dict_by_target_address.get(target_address, [])
            self.ipm_ids_dict_by_target_address[target_address] = ipm_ids
            ipm_ids.append(ipm_id)
            new_targets[target_address] = t
        return new_targets

    def f_ping(self):
        path = self.path
        ## need to change it explicitly to list, otherwise it will keep type of dict_keys.
        ipm_keys = list(self.targets.keys())
        # 如果part_cmd中有-v参数，则从part_cmd中删除-v参数和值，并把值赋值给vrf_name
        if '-v' in self.part_cmd:
            part_cmds = self.part_cmd.split()
            v_index = part_cmds.index('-v')
            vrf_name = part_cmds.pop(v_index + 1)
            part_cmds.pop(v_index)
            self.part_cmd = ' '.join(part_cmds)
            vrf_part_cmd = 'sudo ip vrf exec {0} '.format(vrf_name)
            cmd = vrf_part_cmd + path + " " + self.part_cmd + ' ' + ' '.join(ipm_keys)
        else:
            cmd = path + " " + self.part_cmd + ' ' + ' '.join(ipm_keys)
        self.process_of_f_ping = {str(ipm_keys): cmd_process(cmd)}

    def run(self):
        if not self.timestamp % self.report_interval == 0:
            # 不在整点，不需要运行
            log.debug("Ping worker v2: current ts is {0}, no need to run".format(self.timestamp))
            return
        super(PingWorkerV2, self).run()


class MainThread(object):
    def __init__(self):
        """主线程, 用于管理生产者和消费者线程"""
        self.config_path = os.path.join(
            "/opt/cbc/ipm/etc/",
            'ping_conf.json',
        )
        self.endpoint = ''
        self.conf = {}
        self.targets_size = 80
        self.f_ping_path = '/usr/bin/fping'
        self.targets = []
        self.grouped_targets_v2 = {}
        self.producers_v1 = []
        self.producers_v2 = []
        self.argus = ArgusClient(1988, self.endpoint)
        self.workers = {}
        self.connection_down_queue = Queue.Queue()
        self.shutdown_set = 0

    @staticmethod
    def _chunks(array, size):
        """分割列表"""
        return [
            array[i: i + size]
            for i in range(0, len(array), size)
        ]

    def signal_handler(self, signum, frame):
        """
          Define signal handler for fping main thread.
        """
        log.info("MainThread caught signal {0}, start to notify workers.".format(signum))
         
        for _, subm in self.workers.items():
            for _, p in subm.items():
                p.shutdown_flag.set()
        # Set flag for main thread to exit
        time.sleep(2)
        self.shutdown_set = 1

            
    def set_signal_handler(self):
        signal.signal(signal.SIGTERM, self.signal_handler)
        # Do not arm SIGKILL handler as it is not allowed.
        #signal.signal(signal.SIGKILL, self.signal_handler)

    def __group_targets_new(self, ):
        """给监控目标分组"""
        __new_grouped_targets = {}
        inf = float('inf')
        for t in self.targets:
            t['durable'] = (t.get('end_time', inf) == inf)
            ipm_version = t.get("ipm_version")
            if not ipm_version:
                # old_targets_index.append(self.targets.index(t))
                continue
            p_cmd = self.part_of_cmd(t)
            __new_grouped_targets.setdefault(p_cmd, []).append(t)
        for k, v in __new_grouped_targets.items():
            __new_grouped_targets[k] = self._chunks(v, self.targets_size)
        self.grouped_targets_v2 = __new_grouped_targets

    @staticmethod
    def part_of_cmd(target):
        _p_cmd_list = ["-i 10 ", "-t 2000 "]
        source_address = target.get("source_address")
        cmd_sour_address = "-S {0} ".format(source_address) if source_address else ""
        _p_cmd_list.append(cmd_sour_address)
        outbound_interface = target.get("outbound_interface")
        outbound_interface = "-I {0} ".format(outbound_interface) if outbound_interface else ""
        _p_cmd_list.append(outbound_interface)
        count = target.get("count")
        cmd_count = "-C {0} ".format(count - 3) if count else ""
        _p_cmd_list.append(cmd_count)
        request_interval = target.get("request_interval")
        ## Reserve 10ms for task scheduling and result collecting
        cmd_request_interval = "-p {0} ".format(request_interval - 5) if request_interval else ""
        _p_cmd_list.append(cmd_request_interval)
        packet_size = target.get("packet_size")
        cmd_packet_size = "-b {0} ".format(packet_size) if packet_size else ""
        _p_cmd_list.append(cmd_packet_size)
        tos = target.get("tos")
        cmd_tos = "-O {0} ".format(tos) if tos else ""
        _p_cmd_list.append(cmd_tos)
        is_dfset = target.get("is_dfset")
        cmd_is_dfset = "-M" if is_dfset else ""
        _p_cmd_list.append(cmd_is_dfset)
        # 如果vrf_name不为空，则添加-v参数，表示使用指定VRF，此参数只是用来说明使用了vrf和根据vrf参数聚合，并不是fping的参数
        vrf_name = target.get("vrf_name")
        cmd_vrf_name = "-v {0} ".format(vrf_name) if vrf_name else ""
        _p_cmd_list.append(cmd_vrf_name)
        ## -A to show targets by address
        ## -T to show TTL per reply
        ## -q to not show intermediate results
        return ''.join(_p_cmd_list) + " -A -q -T"

    def __try_load_config(self):
        """载入配置文件"""
        count = 0
        while count < 3:
            try:
                with open(self.config_path) as f:
                    self.conf = json.loads(f.read())
                    return
            except Exception as e:
                log.error("Load configuration error: {0}, count: {1}".format(str(e), count + 1))
                count += 1
        if count == 3:
            exit(1)

    def handle_target_v1_to_v2(self, target):
        new_target = {}
        if target.get("ipm_version", "1") == "2":
            return target
        new_target = {
            "ipm_version": "2",
            "ipm_id": target.get("ipm_id"),
            "ipm_name": target.get("name"),
            "target_address": target.get("ip_address"),
            "ip_version": target.get("ip_version"),
            "end_time": target.get("end_time"),
            "count": target.get("count"),
            "consumer_interval": self.conf.get("consumer_interval"),
            "report_interval": target.get("report_interval"),
            "request_interval": target.get("request_interval"),
            "source_address": target.get("source_address"),
            "outbound_interface": "",
            "packet_size": None,
            "is_dfset": False,
            "tos": None
        }
        return new_target

    def load_config(self):
        self.__try_load_config()
        targets = self.conf.get('targets', [])
        self.targets = [self.handle_target_v1_to_v2(target) for target in targets]
        self.f_ping_path = self.conf.get('path', '/usr/bin/fping')
        self.targets_size = self.conf.get('targets_size_of_worker', 80)
        self.endpoint = self.conf.get('device_id', '')
        self.argus.endpoint = self.endpoint
        self.__group_targets_new()
        is_debug = self.conf.get('debug', False)
        _level = logging.DEBUG if is_debug else logging.INFO
        log.setLevel(_level)
        #log.debug("Log level is debug.") if is_debug else log.info("Log level is info.")

    def _create_threads(self, start_time):
        """创建FPing 的线程"""
        worker_id = 1
        task_interval = 0
        
        ## clear workers of last run, if any.
        for interval, submap in self.workers.items():
            if start_time % interval == 0:
                submap.clear()

        for k, ts in self.grouped_targets_v2.items():
            if not ts:
                # 前面更新 _update_threads ，会清空target， 清空了一个线程的target， 就不会继续新建线程对象了， 如果是新的，那就会新建线程对象
                continue
            for t in ts:
                if len(t) < 1:
                    log.warn("No valid targets: Skipped.")
                    continue
                ## Check if this minute matches the start for the target
                task_interval = t[0]["report_interval"]
                if start_time % task_interval != 0:
                    log.debug("It is not the time to start {0} at {1}".format(t[0]["ipm_name"], start_time))
                    continue
                p = PingWorkerV2(k, t, self.f_ping_path, self.argus, start_time, worker_id,
                                 connection_down_queue=self.connection_down_queue)
                p.start()
                
                ## Store worker info for later use
                if task_interval not in self.workers.keys():
                    ## instantiate new sub-map for this interval to build map like {300: {<id_1>: <worker_1>, <id_2>:<worker_2>}, 60: {}}
                    self.workers[task_interval] = {}
                self.workers[task_interval][worker_id] = p                
                worker_id += 1                
        if worker_id > 1:
            log.info('Number of fping v2 workers created: {0}'.format(worker_id - 1))

    def compare_connection_down_events(self, current_event_info_list, last_update_info):
        need_push_events = []
        for current_event_info in current_event_info_list:
            matched = False
            for cached_value in last_update_info:
                if current_event_info['metric'] == cached_value['metric'] and current_event_info['tags'] == cached_value['tags']:
                    matched = True
                    if current_event_info['value'] != cached_value['value']:
                        need_push_events.append(current_event_info)
                    break
            if not matched and current_event_info['value'] == 'PROBLEM':
                need_push_events.append(current_event_info)
        return need_push_events

    def handle_connection_down_events(self, current_event_info_list, start_time):
        if not current_event_info_list:
            return
        cache_info = load_event_cache()
        last_update_info = cache_info.get('last_update_info', []) if cache_info else []
        need_push_events = self.compare_connection_down_events(current_event_info_list, last_update_info)
        now_time = int(start_time)
        seq = cache_info.get('last_update_seq', 0) + 1 if cache_info else 1
        save_event_cache(now_time, seq, current_event_info_list, last_update_info)
        now_time_str = datetime.fromtimestamp(now_time).strftime('%Y-%m-%d %H:%M:%S')
        for need_push_event in need_push_events:
            push_connection_down_event(need_push_event, now_time_str)

    def connection_down_handler(self):
        """独立线程消费 connection down 事件, worker 完成一轮入队即触发, 不阻塞主调度循环"""
        while True:
            if self.shutdown_set == 1:
                log.info("connection_down_handler thread exits as TERM signal is received.")
                break
            try:
                ## 阻塞等待: 有 worker 完成一轮并入队后才处理, 无需轮询
                ## get() 原子取走单个 worker 入队的一项, 逐项处理, 队列天然串行化, 无并发竞态
                current_event_info_list = self.connection_down_queue.get()
                if current_event_info_list:
                    self.handle_connection_down_events(current_event_info_list, int(time.time()))
            except Exception as e:
                log.error('connection_down_handler() error: {0}'.format(e))

    def setup_threads(self):
        """根据当前配置调整生产者线程"""
        while True:
            if self.shutdown_set == 1:
                log.info("Main thread exits as TERM signal is received.")
                break

            start_time = time.time()
            self.load_config()
            # # 创建新线程
            self._create_threads(int(start_time))
            end_time = time.time()
            async_time = end_time - start_time
            time.sleep(60 - (start_time % 60) - async_time)

    @staticmethod
    def get_file_list(file_path):
        dir_list = os.listdir(file_path)
        if not dir_list:
            return
        else:
            dir_list = sorted(dir_list, key=lambda x: os.path.getmtime(os.path.join(file_path, x)))
            return dir_list

    def detect_file(self, file_path):
        fileList = self.get_file_list(file_path)
        max_size_of_log = self.conf.get('max_size_of_log', 120)
        if fileList and len(fileList) > max_size_of_log:
            rmLen = len(fileList) - max_size_of_log
            for i in range(rmLen):
                rm_path = file_path + '/' + fileList[i]
                log.info('Remove gc log file: {0}'.format(rm_path))
                os.remove(rm_path)

    def gc_inspection(self):
        gc_log_dir_path = '/tmp/fping_gc_log'
        gc_log_dir_exist = os.path.exists(gc_log_dir_path)
        if not gc_log_dir_exist:
            os.mkdir(gc_log_dir_path)
        while True:
            if self.shutdown_set == 1:
                log.info("gc_inspection thread exits as TERM signal is received.")
                break

            is_debug = self.conf.get('debug', False)
            gc_minute_interval = int(self.conf.get('gc_minute_interval', 30))
            if gc_minute_interval < 1:
                gc_minute_interval = 1
            if is_debug:
                self.detect_file(gc_log_dir_path)
                gc_list = gc.get_objects()
                gc_map_by_type = {}
                for obj in gc_list:
                    obj_type = type(obj)
                    obj_type_sum = gc_map_by_type.get(obj_type, 0)
                    gc_map_by_type[obj_type] = obj_type_sum + 1

                log_path = "{0}/{1}-fping-gc.log".format(gc_log_dir_path,
                                                       time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime()))
                with open(log_path, "w") as f:
                    f.write('{0}: {1}\n\n'.format('object_total', len(gc_list)))
                    for key in gc_map_by_type:
                        gc_num = gc_map_by_type[key]
                        f.write('{0}: {1}\n'.format(key, gc_num))

                log.info('Gc has written log to file: {0}'.format(log_path))
                del gc_list
                del gc_map_by_type

            time.sleep(60 * gc_minute_interval)

    def start(self):
        self.load_config()
        gc_thread = Thread(target=self.gc_inspection)
        gc_thread.setDaemon(True)
        gc_thread.start()
        ## 独立线程按自己的节奏处理 connection down 事件, 不阻塞主调度循环
        connection_down_thread = Thread(target=self.connection_down_handler)
        connection_down_thread.setDaemon(True)
        connection_down_thread.start()
        # 初始化生产者
        now_time = time.time()
        redundant_ts = 60 - (now_time % 60)
        log.info("FPing main thread started and will work in {0} seconds.".format(redundant_ts))
        time.sleep(redundant_ts)
        ## Adjust to start of minute
        self.setup_threads()


if __name__ == '__main__':
    # 确保脚本同一时间只有一个实例在执行
    me = SingleInstance()
    main = MainThread()
    main.set_signal_handler() ## arm signal handler
    main.start()
