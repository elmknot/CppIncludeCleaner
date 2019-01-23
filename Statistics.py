#!/usr/bin/python
# -*- coding: UTF-8 -*-

'''
 Copyright (c) 2018-2019 翁轩锴 wengxuankai@foxmail.com
 
 Permission is hereby granted, free of charge, to any person obtaining a copy
 of this software and associated documentation files (the "Software"), to deal
 in the Software without restriction, including without limitation the rights
 to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 copies of the Software, and to permit persons to whom the Software is
 furnished to do so, subject to the following conditions:
 
 The above copyright notice and this permission notice shall be included in
 all copies or substantial portions of the Software.
 
 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 THE SOFTWARE.
'''

import codecs
import os
import sys
import webbrowser
from pyh import *
reload(sys)
sys.setdefaultencoding('utf-8')

class Statistics(object):
    def __init__(self):
        self.input_file_num = 0
        self.parse_file_num = 0
        self.clean_file_num = 0
        self.original_include_num = 0
        self.can_delete_include_num = 0
        self.can_replace_include_num = 0
        self.auto_delete_include_num = 0
        self.auto_replace_include_num = 0
        self.skip_parse_generate_tu_fail_num = 0
        self.skip_parse_reparse_fail_num = 0
        self.skip_parse_ignore_file_num = 0
        self.skip_parse_ignore_macro_file_num = 0
        self.skip_parse_cl_compile_num = 0
        self.skip_parse_excluded_from_build_num = 0
        self.skip_clean_cl_compile_num = 0
        self.skip_clean_excluded_from_build_num = 0
        self.skip_parse_generate_tu_fail_list = []
        self.skip_parse_reparse_fail_list = []
        self.skip_parse_ignore_file_list = []
        self.skip_parse_ignore_macro_file_list = []
        self.skip_parse_cl_compile_list = []
        self.skip_parse_excluded_from_build_list = []
        self.skip_clean_cl_compile_list = []
        self.skip_clean_excluded_from_build_list = []

    def write_html_and_open(self):        
        page = PyH("statistics")

        style = ""

        page << h1('Cpp Header Cleaner 处理结果报告', style = 'text-align:center')
        page << div('by xuankaiweng', style = 'font-size:10px;text-align:center')

        block1 = page << div(style = "margin:50px 190px 50px 190px;padding:30px 50px 30px 50px;\
            font-size:20px;text-align:center;background-color:gray")
        block1 << span("输入的.cpp文件总数:", style = "padding-left:140px")
        block1 << span(str(self.input_file_num), style = "padding-left:5px;background-color:green;color:white")
        block1 << span("实际处理的.cpp文件总数:", style = "padding-left:100px")
        block1 << span(str(self.parse_file_num), style = "padding-left:5px;background-color:green;color:white")
        block1 << span("自动清理#include语句的.cpp文件总数:", style = "padding-left:100px")
        block1 << span(str(self.clean_file_num), style = "padding-left:5px;padding-right:5px;background-color:green;color:white")

        block2 = page << div(style = "margin:50px 190px 50px 190px;padding:30px 100px 30px 100px;\
            font-size:20px;text-align:center;background-color:gray")
        div21 = block2 << div(style = "margin-bottom:20px")
        div21 << span("源文件中有效的#includ语句总数:")
        div21 << span(str(self.original_include_num), style = "padding-left:5px;padding-right:5px;background-color:green;color:white")
        div22 = block2 << div(style = "margin-bottom:20px")
        div22 << span("可以删除的#includ语句总数:")
        div22 << span(str(self.can_delete_include_num), style = "padding-left:5px;background-color:green;color:white")
        div22 << span("可以替换的#includ语句总数:", style = "padding-left:100px")
        div22 << span(str(self.can_replace_include_num), style = "padding-left:5px;padding-right:5px;background-color:green;color:white")
        div23 = block2 << div(style = "margin-top:20px")
        div23 << span("自动删除的#includ语句总数:")
        div23 << span(str(self.auto_delete_include_num), style = "padding-left:5px;background-color:green;color:white")
        div23 << span("自动替换的#includ语句总数:", style = "padding-left:100px")
        div23 << span(str(self.auto_replace_include_num), style = "padding-left:5px;padding-right:5px;background-color:green;color:white")

        block3 = page << div(style = "margin:50px 190px 50px 190px;padding:30px 100px 30px 100px;\
            font-size:15px;text-align:left;background-color:gray")

        div31 = block3 << div(style = "margin-bottom:20px;padding-left:200px")
        div31 << span("因翻译单元生成失败而未能处理的.cpp文件总数:", style = "padding-right:405px")
        if self.skip_parse_generate_tu_fail_num:
            style = "padding-left:5px;padding-right:5px;background-color:red;color:white"
        else:
            style = "padding-left:5px;padding-right:5px"
        div31 << span(str(self.skip_parse_generate_tu_fail_num), style = style)

        div32 = block3 << div(style = "margin-bottom:20px;padding-left:200px")
        div32 << span("因重新解析失败而未能处理的.cpp文件总数:", style = "padding-right:435px")
        if self.skip_parse_reparse_fail_num:
            style = "padding-left:5px;padding-right:5px;background-color:red;color:white"
        else:
            style = "padding-left:5px;padding-right:5px"
        div32 << span(str(self.skip_parse_reparse_fail_num), style = style)

        div33 = block3 << div(style = "margin-bottom:20px;padding-left:200px")      
        div33 << span("因含有其他平台的宏而未能处理的.cpp文件总数:", style = "padding-right:404px")
        if self.skip_parse_ignore_macro_file_num:
            style = "padding-left:5px;padding-right:5px;background-color:red;color:white"
        else:
            style = "padding-left:5px;padding-right:5px"
        div33 << span(str(self.skip_parse_ignore_macro_file_num), style = style)

        div34 = block3 << div(style = "margin-bottom:20px;padding-left:200px")
        div34 << span("因在IgnoreFile.txt文件中而未能处理的.cpp文件总数:", style = "padding-right:370px")
        if self.skip_parse_ignore_file_num:
            style = "padding-left:5px;padding-right:5px;background-color:#ffa500;color:white"
        else:
            style = "padding-left:5px;padding-right:5px"
        div34 << span(str(self.skip_parse_ignore_file_num), style = style)

        div35 = block3 << div(style = "margin-bottom:20px;padding-left:200px")
        div35 << span("因未在.vcxproj文件中设置ClCompile而未能处理的.cpp文件总数:", style = "padding-right:288px")
        if self.skip_parse_cl_compile_num:
            style = "padding-left:5px;padding-right:5px;background-color:#ffa500;color:white"
        else:
            style = "padding-left:5px;padding-right:5px"
        div35 << span(str(self.skip_parse_cl_compile_num), style = style)

        div36 = block3 << div(style = "margin-bottom:20px;padding-left:200px")
        div36 << span("因在.vcxproj文件中设置了ExcludedFromBuild而未能处理的.cpp文件总数:", style = "padding-right:223px")
        if self.skip_parse_excluded_from_build_num:
            style = "padding-left:5px;padding-right:5px;background-color:#ffa500;color:white"
        else:
            style = "padding-left:5px;padding-right:5px"
        div36 << span(str(self.skip_parse_excluded_from_build_num), style = style)

        div37 = block3 << div(style = "margin-bottom:20px;padding-left:200px")
        div37 << span("因未在.vcxproj文件中设置ClCompile而未能自动清理#include语句的.cpp文件总数:", style = "padding-right:165px")
        if self.skip_clean_cl_compile_num:
            style = "padding-left:5px;background-color:#ffa500;color:white"
        else:
            style = "padding-left:5px;padding-right:5px"
        div37 << span(str(self.skip_clean_cl_compile_num), style = style)

        div38 = block3 << div(style = "margin-bottom:20px;padding-left:200px") 
        div38 << span("因在.vcxproj文件中设置了ExcludedFromBuild而未能自动清理#include语句的.cpp文件总数:", style = "padding-right:100px")
        if self.skip_clean_excluded_from_build_num:
            style = "padding-left:5px;padding-right:5px;background-color:#ffa500;color:white"
        else:
            style = "padding-left:5px;padding-right:5px"
        div38 << span(str(self.skip_clean_excluded_from_build_num), style = style)

        if self.skip_parse_generate_tu_fail_list:
            block4 = page << div(style = "margin:20px 200px 20px 400px;font-size:20px")
            block4 << div("因翻译单元生成失败而未能处理的.cpp文件列表:", style = "color:red")
            for path in self.skip_parse_generate_tu_fail_list:
                block4 << div(path, style = "font-size:15px")

        if self.skip_parse_reparse_fail_list:
            block5 = page << div(style = "margin:20px 200px 20px 400px;font-size:20px")
            block5 << div("因重新解析失败而未能处理的.cpp文件列表:", style = "color:red")
            for path in self.skip_parse_reparse_fail_list:
                block5 << div(path, style = "font-size:15px")

        if self.skip_parse_ignore_file_list:
            block6 = page << div(style = "margin:20px 200px 20px 400px;font-size:20px")
            block6 << div("因在IgnoreFile.txt文件中而未能处理的.cpp文件列表: ", style = "color:#ffa500")
            for path in self.skip_parse_ignore_file_list:
                block6 << div(path, style = "font-size:15px")

        if self.skip_parse_ignore_macro_file_list:
            block7 = page << div(style = "margin:20px 200px 20px 400px;font-size:20px")
            block7 << div("因含有其他平台的宏而未能处理的.cpp文件列表: ", style = "color:#ffa500")
            for path in self.skip_parse_ignore_macro_file_list:
                block7 << div(path, style = "font-size:15px")

        if self.skip_parse_cl_compile_list:
            block8 = page << div(style = "margin:20px 200px 20px 400px;font-size:20px")
            block8 << div("因未在.vcxproj文件中设置ClCompile而未能处理的.cpp列表:", style = "color:#ffa500")
            for path in self.skip_parse_cl_compile_list:
                block8 << div(path, style = "font-size:15px")

        if self.skip_parse_excluded_from_build_list:
            block9 = page << div(style = "margin:20px 200px 20px 400px;font-size:20px")
            block9 << div("因在.vcxproj文件中设置了ExcludedFromBuild而未能处理的.cpp文件列表:", style = "color:#ffa500")
            for path in self.skip_parse_excluded_from_build_list:
                block9 << div(path, style = "font-size:15px")

        if self.skip_clean_cl_compile_list:
            block10 = page << div(style = "margin:20px 200px 20px 400px;font-size:20px")
            block10 << div("因未在.vcxproj文件中设置ClCompile而未能自动清理#include语句的.cpp文件列表:", style = "color:#ffa500")
            for path in self.skip_clean_cl_compile_list:
                block10 << div(path, style = "font-size:15px")

        if self.skip_clean_excluded_from_build_list:
            block11 = page << div(style = "margin:20px 200px 20px 400px;font-size:20px")
            block11 << div("因在.vcxproj文件中设置了ExcludedFromBuild而未能自动清理#include语句的.cpp文件列表:", style = "color:#ffa500")
            for path in self.skip_clean_excluded_from_build_list:
                block11 << div(path, style = "font-size:15px")

        # 写入html文件中
        html = page.render()
        f_html = codecs.open("statistics.html", 'w', encoding= 'utf-8')
        f_html.write(html)
        f_html.close()

        # 自动打开生成的html文件
        webbrowser.open_new_tab('statistics.html')