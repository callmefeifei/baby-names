#!/usr/bin/env python
# -*- coding: utf-8 -*-
#  Written by        : 加菲猫 <callmefeifei@163.com>
#  Date              : 2020/06/06 20:01:29
#  Description       : 新生儿起名打分

#  Function support  : * 支持汉字拼音识别
#                    : * 支持汉字偏旁识别
#                    : * 支持笔划数识别
#                    : * 支持重名检测
#                    : * 支持根据生辰八字调用接口自动对五行进行分析

#  Tips: 
#  *                     --- 结果仅供参考，希望用到的都能够给自家宝宝起到好名字 ---
#  * 如该程序对您有所帮助, 请关注作者微信服务号以表支持(搜索: "欧赛安全"), 后续将提供更多有意思的开源代码或在线小工具.

# 配置信息
from config import settings

# 导入用到的库
import os
import re
import sys
import csv
import time
import json
import random
import requests
import codecs

import gevent
from gevent import monkey; monkey.patch_all()
from bs4 import BeautifulSoup

# 汉字拼音识别
from pypinyin import pinyin, lazy_pinyin, Style

# 笔划数识别
from cjklib.characterlookup import CharacterLookup
cjk = CharacterLookup('C')

# 汉字偏旁识别
from lib.component import *

reload(sys)
sys.setdefaultencoding("utf-8")

# 代理配置
proxies = {
    
}

class BabyName():
    def __init__(self, config={}, name_dict={}, is_score=True, use_proxy=False, is_check_component=False, component_preferences="", component_list=[], is_check_duplicate_name=False, max_thread=5, is_filter_out=False):
        # 根目录
        self.ROOTDIR = (os.path.dirname(os.path.realpath(__file__)))

        # 新华字典文件路径
        self.dictionary_filepath = self.ROOTDIR+"/dicts/xinhua.csv"
        self.component = Component(dictionary_filepath=self.dictionary_filepath)

        # 系统配置
        self.CONFIG = config

        # 姓名字典
        self.NAME_DICT = name_dict

        # Headers头
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.61 Safari/537.36"
        }

        # 计算姓名分数网站
        self.REQUEST_URL = settings.REQUEST_URL

        # 姓名结果输出
        self.result_output = self.CONFIG['output_fpath']

        # 是否打分
        self.is_score = is_score

        # 使用代理
        self.use_proxy = use_proxy

        # 是否检查偏旁
        self.is_check_component = is_check_component 
        self.component_preferences = component_preferences   # 偏旁偏好
        self.component_list = component_list                 # 金木水火土对应汉字列表

        # 是否检查重名
        self.is_check_duplicate_name = is_check_duplicate_name

        # 是否过滤重名数为零的
        self.is_filter_out = is_filter_out

        # 最大线程数
        self.max_thread = 10

    # 生成csv文件列名
    def generate_field(self, _filename="./egg.csv", _fieldnames=['first_name', 'last_name']):
        with open(_filename, 'wb') as csvfile:
            # 列名
            fieldnames = _fieldnames
            csvfile.write(codecs.BOM_UTF8)

            # 写csv文件
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, dialect='excel')
            writer.writeheader()

    # 将结果写到csv文件中
    def write_output(self, _filename="./egg.csv", _fieldnames=['first_name', 'last_name'], _values={'first_name': 'wang', 'last_name': 'wu'}):
        with open(_filename, 'a+') as csvfile:
            # 列名
            fieldnames = _fieldnames
            csvfile.write(codecs.BOM_UTF8)

            # 写csv文件
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, dialect='excel')
            writer.writerow(_values)

    def get_proxy(self):
        if self.use_proxy:
            # 代理服务器
            proxyHost = "forward.apeyun.com"
            proxyPort = "9082"

            # 代理隧道验证信息
            proxyUser = "2120061600001000956"
            proxyPass = "xxxxxxx"

            proxyMeta = "http://%(user)s:%(pass)s@%(host)s:%(port)s" % {
              "host" : proxyHost,
              "port" : proxyPort,
              "user" : proxyUser,
              "pass" : proxyPass,
            }

            proxies = {
                "http"  : proxyMeta,
                "https" : proxyMeta,
            }

        else:
            proxies = {}

        return proxies

    # 名字组合生成
    def custom_names_generate(self): 
        # 单名去重
        single_name_uniq = []

        # 单名字组合
        single_name_group = set()
        if self.CONFIG["sex"] == "男":
            fpath_input = self.NAME_DICT['boys_single']

        elif self.CONFIG["sex"] == "女":
            fpath_input = self.NAME_DICT['girls_single']

        for line in open(fpath_input):
            if str(line).strip() not in single_name_uniq:
                for name in open(fpath_input):
                    # 根据五行缺啥, 选择有益、互补的名字
                    if self.is_check_component:
                        if str(line).strip() in self.component_list or str(name).strip() in self.component_list:
                            p_name = str(line).strip()+str(name).strip()
                            single_name_group.add(p_name)
                    else:
                        p_name = str(line).strip()+str(name).strip()
                        single_name_group.add(p_name)

        return single_name_group

    """
        根据是否使用单字和用户配置的性别参数，获取所有的名字列表。
        :return: 名字列表
    """
    def get_all_names(self):
        print("[*] 姓名字典生成中, 请稍后...")

        t1 = float(time.time())
        target_name_postfixs = set()

        # 判断是否有单字限制, 如果设置了固定字, 生成的姓名列表中将都包含该字
        has_limit_word = False
        limit_word = self.CONFIG["limit_world"]
        if limit_word is not None and len(limit_word) > 0:
            has_limit_word = True

        # 根据生辰八字查看五行缺啥, 然后仅查看有该组合的姓名.
        if self.is_check_component:
            wuxing = self.compute_name_wuxing()
        else:
            wuxing = {}
            wuxing["wuxing_miss"] = "无"
            wuxing["wuxing_score"] = "无"

        # 整理名字
        if has_limit_word:
            if self.CONFIG["sex"] == "男":
                fpath_input = self.NAME_DICT['boys_single']

            elif self.CONFIG["sex"] == "女":
                fpath_input = self.NAME_DICT['girls_single']

            for line in open(self.NAME_DICT['boys_single']):
                iter_name = str(line).strip()

                # 根据五行欠缺, 仅过滤名字中包含对应属性的名字
                if self.is_check_component:
                    if iter_name in self.component_list or limit_word in self.component_list:
                        target_name_postfixs.add("%s%s" % (iter_name, limit_word))
                        target_name_postfixs.add("%s%s" % (limit_word, iter_name))
                else:
                    target_name_postfixs.add("%s%s" % (iter_name, limit_word))
                    target_name_postfixs.add("%s%s" % (limit_word, iter_name))
        else:
            if self.CONFIG["sex"] == "男":
                fpath_input_double = self.NAME_DICT['boys_double']
                fpath_input_single = self.NAME_DICT['boys_single']

            elif self.CONFIG["sex"] == "女":
                fpath_input_double = self.NAME_DICT['girls_double']
                fpath_input_single = self.NAME_DICT['girls_single']

            # 双字名
            for line in open(fpath_input_double):
                iter_name = str(line).strip()

                # 根据五行缺乏, 仅过滤名字中包含对应属性的名字
                if self.is_check_component:
                    if iter_name[-3:] in self.component_list or iter_name[:3] in self.component_list:
                        target_name_postfixs.add(iter_name)
                else:
                    target_name_postfixs.add(iter_name)

            # 单字名
            for line in open(fpath_input_single):
                iter_name = str(line).strip()

                # 根据五行缺乏, 仅过滤名字中包含对应属性的名字
                if self.is_check_component:
                    if iter_name[-3:] in self.component_list or iter_name[:3] in self.component_list:
                        target_name_postfixs.add(iter_name)
                else:
                    target_name_postfixs.add(iter_name)

        # 列表随机打乱
        target_name_postfixs = list(target_name_postfixs)
        custom_names = list(self.custom_names_generate())
        all_names = target_name_postfixs + custom_names

        random.shuffle(all_names)

        print("[*] 姓:%s, 性别:%s, 出生地(省):%s, 出生地(市):%s, 出生时辰:%s-%s-%s %s:%s:00, 命中缺:%s, 五行得分:%s" % (
                self.CONFIG["name_prefix"],
                self.CONFIG["sex"],
                self.CONFIG["area_province"],
                self.CONFIG["area_region"],
                self.CONFIG["year"],
                self.CONFIG["month"],
                self.CONFIG["day"],
                self.CONFIG["hour"],
                self.CONFIG["minute"],
                wuxing["wuxing_miss"],
                json.dumps(wuxing["wuxing_score"], ensure_ascii=False)
             )
        )

        print("[*] 导入名字 %s 个, 耗时 %s 秒 ." % (len(all_names), float(time.time()) - t1)  )

        return all_names

    # 查看偏旁
    def check_component(self, names):
        try:
            name_list = []
            if len(names) > 3:
                name_list.append(names[:3])
                name_list.append(names[-3:])
            else:
                name_list.append(names[-3:])

            for name in name_list:
                # 检查当前字是否在默认对应五行汉字列表
                if name in self.component_list:
                    return True

                # 检查当前字是否对应偏旁偏好
                elif self.component_preferences in self.component.get_component(name):
                    return True

            return False
        except Exception as e:
            return False

    # 查看重名(通过人人网)
    def check_duplicate_names(self, name):
        if self.is_check_duplicate_name:
            url = "http://name.renren.com/tongMing/search"
            params = {}
            params["q"] = name
            params["cx"] = "014540359382904656588:9tf8clwp-ki"
            params["ie"] = "UTF-8"

            try:
                resp = requests.post(url=url, data=params, headers=self.headers, timeout=10, allow_redirects=False)
                if resp.status_code == 301:
                    next_url = resp.__dict__['headers']['location']
                    body = requests.get(url=next_url, headers=self.headers, timeout=10).content

                    # 解析同名数量
                    soup = BeautifulSoup(body, 'html.parser')
                    duplicate_result = soup.find_all("p", class_="search_tip")

                    if duplicate_result:
                        for node in duplicate_result:
                            node_cont = node.get_text()
                            names_total = node.find_all("font")[1].get_text()
                            girls_total = node.find_all("font")[2].get_text()
                            boys_total = node.find_all("font")[3].get_text()
                    else:
                        names_total = "0人" 
                        girls_total = "女生0.00%"
                        boys_total = "男生0.00%"
                else:
                    names_total = "0人" 
                    girls_total = "女生0.00%"
                    boys_total = "男生0.00%"
            except Exception as err:
                names_total = "0人" 
                girls_total = "女生0.00%"
                boys_total = "男生0.00%"
                print 1111,err

            girls_num = re.findall("\d*\.\d*", girls_total)[0]
            boys_num = re.findall("\d*\.\d*", boys_total)[0]

            # 名字性别偏向
            name_sex = ""
            if int(float(girls_num)) > int(float(boys_num)):
                name_sex = "女"
            elif int(float(boys_num)) > int(float(girls_num)):
                name_sex = "男"
            else:
                name_sex = "中性"
        else:
            names_total = "0人" 
            girls_total = "女生0.00%"
            boys_total = "男生0.00%"
            name_sex = "未知"

        return names_total, girls_total, boys_total, name_sex

    def compute_name_wuxing(self, name_postfix="测试"):
        """
        调用接口，执行计算，返回结果
        :param name_postfix: 
        :return: 结果
        """
        result_data = {}

        # 生辰
        if int(self.CONFIG['hour']) in [0, 23]:
            cboHour = "%s-子时" % self.CONFIG['hour']
        elif int(self.CONFIG['hour']) in [1, 2]:
            cboHour = "%s-丑时" % self.CONFIG['hour']
        elif int(self.CONFIG['hour']) in [3, 4]:
            cboHour = "%s-寅时" % self.CONFIG['hour']
        elif int(self.CONFIG['hour']) in [5, 6]:
            cboHour = "%s-卯时" % self.CONFIG['hour']
        elif int(self.CONFIG['hour']) in [7, 8]:
            cboHour = "%s-辰时" % self.CONFIG['hour']
        elif int(self.CONFIG['hour']) in [9, 10]:
            cboHour = "%s-巳时" % self.CONFIG['hour']
        elif int(self.CONFIG['hour']) in [11, 12]:
            cboHour = "%s-午时" % self.CONFIG['hour']
        elif int(self.CONFIG['hour']) in [13, 14]:
            cboHour = "%s-未时" % self.CONFIG['hour']
        elif int(self.CONFIG['hour']) in [15, 16]:
            cboHour = "%s-申时" % self.CONFIG['hour']
        elif int(self.CONFIG['hour']) in [17, 18]:
            cboHour = "%s-酉时" % self.CONFIG['hour']
        elif int(self.CONFIG['hour']) in [19, 20]:
            cboHour = "%s-戌时" % self.CONFIG['hour']
        elif int(self.CONFIG['hour']) in [21, 22]:
            cboHour = "%s-亥时" % self.CONFIG['hour']

        _data = {}
        _data["data_type"] = 0
        _data["cboYear"] = self.CONFIG['year']
        _data["cboMonth"] = self.CONFIG['month']
        _data["cboDay"] = self.CONFIG['day']
        _data["cboHour"] = cboHour
        _data["cboMinute"] = self.CONFIG['minute']
        _data["pid"] = self.CONFIG['area_province']
        _data["cid"] = self.CONFIG['area_region']
        _data["isbz"] = 1
        _data["txtName"] = self.CONFIG['name_prefix']
        _data["name"] = name_postfix
        # 0表示女，1表示男
        if self.CONFIG["sex"] == "男":
            _data['rdoSex'] = "1"
        else:
            _data['rdoSex'] = "0"
        _data["zty"] = 0

        # 全名
        full_name = self.get_full_name(name_postfix)

        if self.is_score:
            # 获取姓名八字/五格
            # ============================================================
            proxies = self.get_proxy()
            content = requests.post(url=self.REQUEST_URL, data=_data, headers=self.headers, timeout=5, proxies=proxies).content
            soup = BeautifulSoup(content, 'html.parser')

            # 根据生辰八字, 获取命中缺什么, 五行得分
            result_data['wuxing_miss'] = ''
            result_data['wuxing_score'] = ''

            # 姓名五格&八字评分
            for node in soup.find_all("div", class_="sm_wuxing"):
                node_cont = node.get_text()
                if u'五行力量:' in node_cont:
                    try:
                        wuxing = node_cont.split(":")[1].replace(";", ',').replace(" ", "").replace(" ", "")
                        _wuxing_score = {}

                        for i in wuxing.split(","):
                            if len(i) != 0:
                                _wuxing_score[i[:1]] = int(re.findall("\d*", i)[1])
                            else:
                                continue
                    except Exception as err:
                        print "compute_name_wuxing", err

                    # 根据生辰八字, 了解命中缺什么, 挑名字时候有针对的选则
                    if _wuxing_score:
                        wuxing_miss = sorted(_wuxing_score.items(), key=lambda x:x[1])[0][0]

                        if wuxing_miss == '金':
                            self.component_preferences = "钅"             # 偏旁偏好
                            self.component_list = settings.JIN        # 金木水火土对应汉字列表
                        elif wuxing_miss == '木':
                            self.component_preferences = "木"             # 偏旁偏好
                            self.component_list = settings.MU        # 金木水火土对应汉字列表
                        elif wuxing_miss == '水':
                            self.component_preferences = "氵"             # 偏旁偏好
                            self.component_list = settings.SHUI        # 金木水火土对应汉字列表
                        elif wuxing_miss == '火':
                            self.component_preferences = "火"             # 偏旁偏好
                            self.component_list = settings.HUO        # 金木水火土对应汉字列表
                        elif wuxing_miss == '土':
                            self.component_preferences = "土"             # 偏旁偏好
                            self.component_list = settings.TU        # 金木水火土对应汉字列表

                        result_data['wuxing_miss'] = wuxing_miss
                        result_data['wuxing_score'] = _wuxing_score

        return result_data

    def compute_name_score(self, name_postfix):
        """
        调用接口，执行计算，返回结果
        :param name_postfix: 
        :return: 结果
        """
        result_data = {}

        # 生辰
        if int(self.CONFIG['hour']) in [0, 23]:
            cboHour = "%s-子时" % self.CONFIG['hour']
        elif int(self.CONFIG['hour']) in [1, 2]:
            cboHour = "%s-丑时" % self.CONFIG['hour']
        elif int(self.CONFIG['hour']) in [3, 4]:
            cboHour = "%s-寅时" % self.CONFIG['hour']
        elif int(self.CONFIG['hour']) in [5, 6]:
            cboHour = "%s-卯时" % self.CONFIG['hour']
        elif int(self.CONFIG['hour']) in [7, 8]:
            cboHour = "%s-辰时" % self.CONFIG['hour']
        elif int(self.CONFIG['hour']) in [9, 10]:
            cboHour = "%s-巳时" % self.CONFIG['hour']
        elif int(self.CONFIG['hour']) in [11, 12]:
            cboHour = "%s-午时" % self.CONFIG['hour']
        elif int(self.CONFIG['hour']) in [13, 14]:
            cboHour = "%s-未时" % self.CONFIG['hour']
        elif int(self.CONFIG['hour']) in [15, 16]:
            cboHour = "%s-申时" % self.CONFIG['hour']
        elif int(self.CONFIG['hour']) in [17, 18]:
            cboHour = "%s-酉时" % self.CONFIG['hour']
        elif int(self.CONFIG['hour']) in [19, 20]:
            cboHour = "%s-戌时" % self.CONFIG['hour']
        elif int(self.CONFIG['hour']) in [21, 22]:
            cboHour = "%s-亥时" % self.CONFIG['hour']

        _data = {}
        _data["data_type"] = 0
        _data["cboYear"] = self.CONFIG['year']
        _data["cboMonth"] = self.CONFIG['month']
        _data["cboDay"] = self.CONFIG['day']
        _data["cboHour"] = cboHour
        _data["cboMinute"] = self.CONFIG['minute']
        _data["pid"] = self.CONFIG['area_province']
        _data["cid"] = self.CONFIG['area_region']
        _data["isbz"] = 1
        _data["txtName"] = self.CONFIG['name_prefix']
        _data["name"] = name_postfix
        # 0表示女，1表示男
        if self.CONFIG["sex"] == "男":
            _data['rdoSex'] = "1"
        else:
            _data['rdoSex'] = "0"
        _data["zty"] = 0

        # 全名
        full_name = self.get_full_name(name_postfix)

        # 检查偏旁部首
        if is_check_component:
            if self.check_component(name_postfix):
                pass
            else:
                return False

        # 检查同名人数
        names_total, girls_total, boys_total, name_sex = self.check_duplicate_names(full_name)

        result_data['names_total'] = names_total
        result_data['girls_total'] = girls_total
        result_data['boys_total'] = boys_total
        result_data['name_sex'] = name_sex

        # 检查八字+姓名得分
        result_data['full_name'] = full_name
        result_data["wuge_score"] = 100
        result_data["bazi_score"] = 100
        result_data["minggong"] = "X"
        result_data["mingzhuxingxiu"] = "X"
        result_data['total_score'] = 100

        # 过滤掉重名为0的.
        if self.is_filter_out:
            if names_total == '0人':
                return False

        # 根绝性别设置筛选对应性别的姓名
        if self.CONFIG["sex"] != name_sex:
            return False

        if self.is_score:
            # 获取姓名八字/五格
            # ============================================================
            proxies = self.get_proxy()
            content = requests.post(url=self.REQUEST_URL, data=_data, headers=self.headers, timeout=5, proxies=proxies).content
            soup = BeautifulSoup(content, 'html.parser')

            # 姓名五格&八字评分
            for node in soup.find_all("div", class_="sm_wuxing"):
                node_cont = node.get_text()
                if u'姓名五格评分' in node_cont:
                    result_data["wuge_score"] = re.findall(r"\n(.*?) ", node_cont, re.S)[0].split("：")[1].split("\n")[0].strip("分")

                if u'姓名八字评分' in node_cont:
                    result_data["bazi_score"] = re.findall(r"\n(.*?) ", node_cont, re.S)[0].split("：")[2].split("分")[0]

            # 命宫 & 命主
            if result_data:
                for node in soup.find_all("ul", class_="bazi_box1"):
                    node_cont = node.get_text()
                    result_data["minggong"] = node_cont.split(":")[-1]
                    result_data["mingzhuxingxiu"] = node_cont.split(":")[-2].split("命宫分析")[0]

            result_data['total_score'] = float(result_data['wuge_score']) + float(result_data['bazi_score'])

        return result_data

    def get_full_name(self, name_postfix):
        return "%s%s" % ((self.CONFIG["name_prefix"]), name_postfix)

    def online_compute_score(self, _fieldnames, name_postfix, cur_idx, shengyushu):
        # 识别笔划数
        if len(name_postfix) > 3:
            _pinyin = pinyin(u'%s' % name_postfix)[0][0] + pinyin(u'%s' % name_postfix)[1][0]
            try:
                bihua = cjk.getStrokeCount(u"%s" % name_postfix[:3]) + cjk.getStrokeCount(u"%s" % name_postfix[-3:])
            except:
                bihua = 0

        else:
            _pinyin = pinyin(u'%s' % name_postfix)[0][0]
            try:
                bihua = cjk.getStrokeCount(u"%s" % name_postfix[-3:])
            except:
                bihua = 0

        # 开始评估
        try:
            # 以名字的后缀作为参数进行计算
            name_data_dict = False
            count = 0
            while True:
                # 如果请求计算失败, 则等待一段时间或通过代理
                try:
                    name_data_dict = self.compute_name_score(name_postfix)
                    break
                except Exception as e:
                    # 等待1分钟, 继续请求
                    count += 1
                    print("[-][%s][%s] 查询异常, 请等待..." % (count, cur_idx))
                    time.sleep(1)
                    continue
        except Exception as e:
            print "error:", name_postfix, e
            return False

        if not name_data_dict:
            return False

        # 打印评估结果
        print "\t".join((str(cur_idx) + "/" + str(shengyushu), 
                         u"姓名=" + name_data_dict['full_name'],
                         u"拼音=" + _pinyin,
                         u"八字评分=" + str(name_data_dict['bazi_score']),
                         u"五格评分=" + str(name_data_dict['wuge_score']),
                         u"笔划数=" + str(bihua),
                         u"重名数=" + str(name_data_dict['names_total']),
                         u"女生占比=" + str(name_data_dict['girls_total']),
                         u"男生占比=" + str(name_data_dict['boys_total']),
                         u"性别偏向=" + name_data_dict['name_sex'],
                         u"总分=" + str(name_data_dict['total_score'])
                         ))

        # 保存评估结果
        self.write_output(
                # 文件名
                _filename = self.result_output,
                # 列名
                _fieldnames=_fieldnames, 
                # 内容
                _values={
                        'ID': cur_idx,
                        '姓名': name_data_dict['full_name'], 
                        '拼音': _pinyin,
                        '八字评分': str(name_data_dict['bazi_score']),
                        '五格评分': str(name_data_dict['wuge_score']),
                        '命主星宿': str(name_data_dict['mingzhuxingxiu']),
                        '命宫': str(name_data_dict['minggong']),
                        '笔划数': str(bihua),
                        '重名数': str(name_data_dict['names_total']),
                        '女生占比': str(name_data_dict['girls_total']),
                        '男生占比': str(name_data_dict['boys_total']),
                        '性别偏向': name_data_dict['name_sex'],
                        '总分': str(name_data_dict['total_score'])
                }
        )

    def run(self):
        # 根据字典获取所有名字列表
        self.all_names = self.get_all_names()

        cur_idx = 0
        all_count = len(self.all_names)
        name_data_list = []

        # 输出文件列名
        _fieldnames = ["ID", "姓名", "拼音", "八字评分", "五格评分", "命主星宿", "命宫", "笔划数", "重名数", "女生占比", "男生占比", "性别偏向", "总分"]

        # 生成表头
        if os.path.exists(self.result_output):
            pass
        else:
            self.generate_field(                    # 文件名
                _filename = self.result_output,
                # 列名
                _fieldnames=_fieldnames, 
            )

        # 遍历所有名字评分
        gevent_list = []

        while True:
            if len(gevent_list) >= self.max_thread:
                gevent.joinall(gevent_list)
                gevent_list = []
            else:
                if self.all_names:
                    cur_idx += 1
                    shengyushu = len(self.all_names)
                    name_postfix = self.all_names.pop()
                    gevent_list.append(gevent.spawn(self.online_compute_score, _fieldnames, name_postfix, cur_idx, shengyushu))
                else:
                    break
if __name__ == "__main__":
    """
    Tips:
                ---- 程序仅供参考，祝大家能够给自己宝宝起到好名字 ----
        1. 运行前, 先配置config/settings.py中相关配置, 如出生日期、姓氏等.
        2. 打分接口可能会有变化或随着时间长久失效, 调试替换其他接口即可.
        3. 部分接口请求次数过多可能会被封IP, 推荐购买使用 "猿人云" 提供的动态转发代理, 并替换本文件get_proxy方法中的授权信息即可. (可使用我的推广链接申请: https://ape.vip/T-ovAUDi)
    最后, 如该程序对您有所帮助, 请关注作者微信服务号以表支持(搜索: "欧赛安全"), 后续将提供更多有意思的开源代码或在线小工具.
    """

    # 是否进行打分
    is_score = True

    # 是否使用代理
    use_proxy = False

    # 是否检查命格缺失?
    is_check_component = True
    component_preferences = "木" # is_check_component设置为True时会自动判断.
    component_list = settings.MU # 木命对应的名字

    # 是否检查重名
    is_check_duplicate_name = True

    # 是否过滤掉重名数为零的(设置为True, renren网查不到的将不显示) 
    is_filter_out = True

    # 最大线程数
    max_thread = 10

    babyname = BabyName(config=settings.CONFIG, name_dict=settings.NAME_DICTS, is_score=is_score, use_proxy=use_proxy, is_check_component=is_check_component, component_preferences=component_preferences, component_list=component_list, is_check_duplicate_name=is_check_duplicate_name, max_thread=max_thread, is_filter_out=is_filter_out)
    babyname.run()



