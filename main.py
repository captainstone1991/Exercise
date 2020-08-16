import os
import sys
import re
import time
import getopt
import hashlib
import traceback
from datetime import datetime
from functools import reduce
from io import BytesIO

import requests
from PIL import Image
from urllib import request


def main():
    """
    主入口
    """
    try:
        # 获取命令行参数
        args = get_args()
        if not args:
            print('param error')
            return None

        # 校验命令行输入的间隔时间
        time_period = args[0][1]
        try:
            time_period = int(time_period)
        except Exception as e:
            print('time period error')
            return None

        # 校验命令行输入的url路径
        url = args[1][1]
        if not url.startswith('http'):
            print('url error')
            return None

        # 校验命令行输入的存储路径
        dir_path = args[2][1]
        try:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
        except Exception as e:
            print('path error')
            return None
        # 去掉输入的存储路径中最后的/
        if dir_path.endswith('/'):
            dir_path = dir_path[:-1]

        print('work start')
        while True:
            get_url_content(url, dir_path)
            time.sleep(time_period)
    except Exception as e:
        print(traceback.format_exc())


def save_log(log_path, content):
    """
    写入日志
    :param log_path: 日志文件路径
    :param content: 日志内容
    :return: ok/None
    """
    try:
        with open(log_path, 'a') as f:
            f.write('{}\n'.format(content))
        return 'ok'
    except Exception as e:
        print(traceback.format_exc())
        return None


def get_args():
    """
    获取命令行传入的参数
    :return: 命令行传入的参数元组
    """
    try:
        opts, args = getopt.getopt(sys.argv[1:], "d:u:o:", [])
        # 校验命令行参数
        if len(opts) != 3:
            return None
        for elem in opts:
            if not isinstance(elem, tuple):
                return None
        return opts
    except Exception as e:
        print(traceback.format_exc())


def get_url_content(url, dir_path):
    """
    获取url中的内容
    :param url: 远程路径
    :param dir_path: 文件保存总目录
    :return:
    """
    time_now = get_time_now()  # 获取当前时间
    log_path = dir_path + '/logs.txt'  # 日志路径
    try:
        # 创建目录
        save_dir = dir_path + '/' + time_now + '/'  # 本次爬取文件保存的总目录
        try:
            if not os.path.exists(save_dir):
                os.makedirs(save_dir + 'css')  # css目录
                os.makedirs(save_dir + 'js')  # js目录
                os.makedirs(save_dir + 'images')  # 图片目录
        except Exception as e:
            save_log(log_path, '{}目录创建内容目录失败'.format(time_now))
            return None

        # 请求url中的内容
        headers = {
            'content-type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3626.119 Safari/537.36'
        }
        try:
            res = requests.get(url=url, headers=headers, timeout=5)
        except Exception as e:
            save_log(log_path, '{}目录获取url内容失败'.format(time_now))
            return None
        res.encoding = 'utf-8'

        # 获取html文本
        html_text = res.text
        html_text = get_css(html_text, save_dir)  # 下载css文件，并对html文本中相关路径进行替换
        html_text = get_js(html_text, save_dir)  # 下载js文件，并对html文本中相关路径进行替换
        html_text = get_images(html_text, save_dir)  # 下载图片文件，并对html文本中相关路径进行替换
        # 判断html内容是否异常
        if not html_text:
            return None
        # 保存html文件
        html_path = save_dir + 'index.html'
        with open(html_path, 'w') as f:
            f.write(html_text)
        save_log(log_path, '{}目录内容保存成功'.format(time_now))
        return 'ok'
    except Exception as e:
        save_log(log_path, '{}目录内容保存失败'.format(time_now))
        return None


def get_css(html_text, save_dir):
    """
    保存css样式
    :param html_text:html文本
    :param save_dir:保存路径
    :return:替换后的html文本
    """
    try:
        # css文件存储目录
        css_dir = save_dir + 'css/'
        # 正则提取html文本中的css路径
        pattern_1 = '<link href="(.*?)"'
        pattern_2 = '<link rel="stylesheet" href="(.*?)"'
        pattern_3 = '<link type="text/css" rel="stylesheet" href="(.*?)"'
        css_list = re.compile(pattern_1, re.S).findall(html_text) + re.compile(pattern_2, re.S).findall(
            html_text) + re.compile(pattern_3, re.S).findall(html_text)
        # 对css路径进行筛选
        final_css_list = [i for i in css_list if i.endswith('.css')]
        final_css_list = list_remove_duplicate(final_css_list)  # 列表去重
        # 遍历css路径
        for css in final_css_list:
            md5_name = md5(css + str(time.time()))  # 生成md5名称，防止重复
            if not md5_name:
                return None
            md5_name += '.css'
            replace_name = './css/' + md5_name  # 生成css文件的本地相对路径
            html_text = html_text.replace(css, replace_name)  # 替换html文本中的css路径为本地相对路径
            # 保存css文件
            save_path = css_dir + md5_name  # 生成保存路径
            # 获取css内容并判断内容是否异常
            content = get_content(css)
            if not content:
                return None
            # 保存并判断保存状态
            save_status = save(save_path, content)
            if not save_status:
                return None
        return html_text
    except Exception as e:
        return None


def get_js(html_text, save_dir):
    """
    保存js文件
    :param html_text:html文本
    :param save_dir:保存路径
    :return:替换后的html文本
    """
    try:
        # js文件存储目录
        js_dir = save_dir + 'js/'
        # 正则提取html文本中的js路径
        pattern_1 = '<script src="(.*?)"'
        pattern_2 = '<script type="text/javascript" src="(.*?)"'
        js_list = re.compile(pattern_1, re.S).findall(html_text) + re.compile(pattern_2, re.S).findall(html_text)
        # 对js路径进行筛选
        final_js_list = [i for i in js_list if i.endswith('.js')]
        final_js_list = list_remove_duplicate(final_js_list)  # 列表去重
        # 遍历js路径
        for js in final_js_list:
            md5_name = md5(js + str(time.time()))  # 生成md5名称，防止重复
            if not md5_name:
                return None
            md5_name += '.js'
            replace_name = './js/' + md5_name  # 生成js文件的本地相对路径
            html_text = html_text.replace(js, replace_name)  # 替换html文本中的js路径为本地相对路径
            # 保存js文件
            save_path = js_dir + md5_name  # 生成保存路径
            # 获取js内容并判断内容是否异常
            content = get_content(js)
            if not content:
                return None
            # 替换js文件中的图片url为本地图片路径
            content = replace_js_image_url(content, save_dir)
            # 保存并判断保存状态
            save_status = save(save_path, content)
            if not save_status:
                return None
        return html_text
    except Exception as e:
        return None


def get_images(html_text, save_dir):
    """
    保存图片
    :param html_text:html文本
    :param save_dir:保存路径
    :return:替换后的html文本
    """
    try:
        # 图片文件存储目录
        image_dir = save_dir + 'images/'
        # 正则提取html文本中的图片路径
        pattern_1 = '<img src="(.*?)"'
        pattern_2 = '<img.*?src="(.*?)"'
        pattern_3 = "background: url\('(.*?)'\)"
        image_list_1 = re.compile(pattern_1, re.S).findall(html_text) + re.compile(pattern_2, re.S).findall(html_text)
        image_list_2 = re.compile(pattern_3, re.S).findall(html_text)
        # 对图片路径进行筛选
        final_image_list_1 = [i for i in image_list_1 if check_is_image(i)]
        final_image_list_2 = [i for i in image_list_2 if check_is_image(i)]
        final_image_list = final_image_list_1 + final_image_list_2
        final_image_list = list_remove_duplicate(final_image_list)  # 列表去重
        # 遍历图片路径
        for image_url in final_image_list:
            suffix = get_image_suffix(image_url)  # 获取图片后缀名
            if not suffix:
                suffix = image_url.split('.')[-1]
            md5_name = md5(image_url + str(time.time()))  # 生成md5名称，防止重复
            if not md5_name:
                return None
            md5_name = md5_name + '.' + suffix
            replace_name = './images/' + md5_name  # 生成图片文件的本地相对路径
            html_text = html_text.replace(image_url, replace_name)  # 替换html文本中的图片路径为本地相对路径
            # 保存图片文件
            save_path = image_dir + md5_name  # 生成保存路径
            # 获取图片内容并判断内容是否异常
            content = get_content(image_url)
            if not content:
                return None
            # 保存并判断保存状态
            save_status = save(save_path, content)
            if not save_status:
                return None
        return html_text
    except Exception as e:
        return None


def replace_js_image_url(content, save_dir):
    """
    替换js内容中的url路径
    :param content: 原始js内容
    :param save_dir: 保存路径
    :return: 替换后的js内容
    """
    try:
        # 图片本地保存路径
        image_dir = save_dir + 'images/'
        # 将二进制内容转为字符串
        content = content.decode('utf-8')
        # 正则匹配js内容中的图片
        pattern_1 = 'photo:"(.*?)"'
        pattern_2 = 'photoDefault:"(.*?)"'
        pattern_3 = 'photoDisable:"(.*?)"'
        pattern_4 = 'logoUrl:"(.*?)"'
        pattern_5 = 'icon:"(.*?)"'
        image_list = re.compile(pattern_1, re.S).findall(content) + re.compile(pattern_2, re.S).findall(
            content) + re.compile(pattern_3, re.S).findall(content) + re.compile(pattern_4, re.S).findall(
            content) + re.compile(pattern_5, re.S).findall(content)
        final_image_list = [i for i in image_list if check_is_image(i)]  # 筛选出图片
        final_image_list = list_remove_duplicate(final_image_list)  # 列表去重
        # 遍历图片路径
        for image_url in final_image_list:
            suffix = get_image_suffix(image_url)  # 获取图片后缀名
            if not suffix:
                suffix = image_url.split('.')[-1]
            md5_name = md5(image_url + str(time.time()))  # 生成md5名称，防止重复
            if not md5_name:
                return None
            md5_name = md5_name + '.' + suffix
            replace_name = './images/' + md5_name  # 生成图片文件的本地相对路径
            content = content.replace(image_url, replace_name)  # 替换js文本中的图片路径为本地相对路径
            # 保存图片文件
            save_path = image_dir + md5_name  # 生成保存路径
            # 获取图片内容并判断内容是否异常
            image_content = get_content(image_url)
            if not image_content:
                return None
            # 保存并判断保存状态
            save_status = save(save_path, image_content)
            if not save_status:
                return None
        content = content.encode('utf-8')
        return content
    except Exception as e:
        return None


def save(save_path, content):
    """
    保存文件
    :param save_path: 保存路径
    :param content: 文件内容
    :return: ok/None
    """
    try:
        with open(save_path, 'wb') as f:
            f.write(content)
        return 'ok'
    except Exception as e:
        return None


def get_content(url):
    """
    获取链接文件内容
    :param url: 链接
    :return: url获取的内容
    """
    try:
        # 判断url是否为http开头，如果不是自动补齐
        if not url.startswith('http'):
            url = 'http:' + url
        headers = {
            'content-type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3626.119 Safari/537.36'
        }
        res = requests.get(url, timeout=10, headers=headers)
        content = res.content
        return content
    except Exception as e:
        return None


def get_image_suffix(image_url):
    """
    根据图片属性获取图片后缀
    :param image_url: 图片链接
    :return: suffix: 图片后缀
    """
    try:
        # 判断url是否为http开头，如果不是自动补齐
        if not image_url.startswith('http'):
            image_url = 'http:' + image_url
        # 获取图片内容
        req = request.urlopen(image_url)
        bytes_content = req.read()
        content = BytesIO(bytes_content)
        img = Image.open(content, 'r')
        # 获取图片格式
        image_format = img.format
        # 将图片格式转为小写字母即为图片后缀
        suffix = image_format.lower()
        return suffix
    except Exception as e:
        return None


def check_is_image(image_url):
    """
    判断路径是否为图片
    :param image_url:图片路径
    :return: True/False
    """
    if image_url.endswith('.jpg') or image_url.endswith('.jpeg') or image_url.endswith('.png') or image_url.endswith(
            '.gif') or image_url.endswith('.bmp') or image_url.endswith('.JPG') or image_url.endswith(
        '.JPEG') or image_url.endswith('.PNG') or image_url.endswith('.BMP') or image_url.endswith('.GIF'):
        return True
    return False


def get_time_now():
    """
    获取当前时间
    :return: 当前时间
    """
    try:
        time_now = datetime.now().strftime('%Y%m%d%H%M')
        return time_now
    except Exception as e:
        return None


def md5(source_data):
    """
    md5加密
    :param source_data:需要加密的内容
    :return: md5加密后的内容
    """
    try:
        md5 = hashlib.md5()
        md5.update(source_data.encode())
        return md5.hexdigest()
    except Exception as e:
        return None


def list_remove_duplicate(source_list):
    """
    列表去重
    :param source_list:源列表
    :return:去重后的列表
    """
    try:
        if not source_list:
            source_list = []
        else:
            remove_duplicate = lambda x, y: x if y in x else x + [y]
            source_list = reduce(remove_duplicate, [[], ] + source_list)
        return source_list
    except Exception as e:
        return source_list


main()
