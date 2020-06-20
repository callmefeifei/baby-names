# -*- coding: utf-8 -*-
#  Written by   : 加菲猫 <callmefeifei@163.com>
#  Date         : 2020/06/10 11:06:11
#  Description  : 宝贝起名 - {偏旁查询模块}

import re
import sys
import csv
import urllib2
from bs4 import BeautifulSoup

reload(sys)
sys.setdefaultencoding("utf-8")

class Component(object):
    def __init__(self, dictionary_filepath="./xinhua.csv"):
        self.dictionary_filepath = dictionary_filepath
        self.read_dictionary()
        self.origin_len = len(self.dictionary)
        self.baiduhanyu_url = 'http://hanyu.baidu.com/zici/s?ptype=zici&wd=%s'

    def read_dictionary(self):
        self.dictionary = {}

        file = open(self.dictionary_filepath, 'rU')
        reader = csv.reader(file)

        for line in reader:
            self.dictionary[line[0].decode('utf-8')] = line[1].decode('utf-8')

        file.close()

    def post_baidu(self,url):
        #print url
        try:
            timeout = 5
            request = urllib2.Request(url)
            #伪装HTTP请求
            request.add_header('User-agent', 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36')
            request.add_header('connection','keep-alive')
            request.add_header('referer', url)
            # request.add_header('Accept-Encoding', 'gzip')  # gzip可提高传输速率，但占用计算资源
            response = urllib2.urlopen(request, timeout = timeout)
            html = response.read()
            #if(response.headers.get('content-encoding', None) == 'gzip'):
            #    html = gzip.GzipFile(fileobj=StringIO.StringIO(html)).read()
            response.close()
            return html
        except Exception as e:
            #print 'URL Request Error:', e
            return None

    def get_component(self, word):
        word = word.decode('utf-8')

        if word in self.dictionary:
            return self.dictionary[word]
        else:
            #return self.get_component_from_baiduhanyu(word)
            return None

    def get_component_from_baiduhanyu(self, word):
        url = self.baiduhanyu_url % word
        html = self.post_baidu(url)

        if html == None:
            return None

        component = self.anlysis_component_from_html(html)
        if component != None:
            self.dictionary[word] = component

        return component

    def anlysis_component_from_html(self,html_doc):
        soup = BeautifulSoup(html_doc, 'html.parser')
        li = soup.find(id="component")
        component = li.span.contents[0]

        return component

if __name__ == "__main__":
    dictionary_filepath = "/Users/callmefeifei/Desktop/scripts/baby-name/dicts/xinhua.csv"
    component = Component(dictionary_filepath=dictionary_filepath)
    print component.get_component("振")








