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

import os
import sys
import clang.cindex
import xml.etree.cElementTree as ET
import Utility
from Task import Task
from Statistics import Statistics
reload(sys)
sys.setdefaultencoding('utf-8')

class VcxprojConfiguration(object):
    def __init__(self):
        # .vcxproj文件中设置的编译使用的宏字典，key为宏的名称，value为宏的值
        self.vcxproj_macro_dict = {}
        # .vcxproj文件中设置的搜索路径列表
        self.vcxproj_search_path_list = []
        # .vcxproj文件中通过ClCompile设置的需要编译的文件列表
        self.vcxproj_cl_compile_path_list = []
        # .vcxproj文件中通过ExcludedFromBuild设置的不需要编译的文件列表
        self.vcxproj_excluded_from_build_path_list = []
        # 使用clang生成AST时需要传入的参数列表
        self.clang_arg_list = []

class CppIncludeCleaner(object):
    def __init__(self, input_arg):
        # 数据统计模块
        self.statistics = Statistics()
        # 输入参数
        self.input_arg = input_arg
        # 待处理的的文件路径列表
        self.input_file_path_list = []
        # IgnoreFile.txt文件中的不处理的文件列表
        self.ignore_file_list = []
        # .vcxproj文件中设置的各项配置字典
        self.vcxproj_configuration_dict = {}

    def begin(self):
        # 生成需要处理的文件路径列表
        self.generate_input_file_path_list()

        # 读取项目配置：vcxproj文件路径、vcxproj文件名称等
        self.parse_config()

        # 读取IgnoreFile.txt文件
        self.parse_ignore_file()

        # 解析vcxproj文件
        self.parse_vcxproj()

        # 生成clang编译参数
        self.generate_clang_args()

        # 设置libclang的路径
        self.set_clang_config()

        # 创建具体的单个文件的解析任务
        self.create_tasks()

        # 输出处理结果统计
        self.display_statistics()

    def generate_input_file_path_list(self):
        for input_file_path in self.input_arg:
            if os.path.isfile(input_file_path):
                if input_file_path.endswith(".cpp"):
                    self.input_file_path_list.append(input_file_path)
            elif os.path.isdir(input_file_path):
                for root, dirs, files in os.walk(input_file_path):
                    for f_name in files:
                        if f_name.endswith(".cpp"):
                            self.input_file_path_list.append(os.path.join(root, f_name))
            else:
                print "Error! Invalid input_file_path: %s" % (input_file_path,)
        self.statistics.input_file_num = len(self.input_file_path_list)

    def parse_config(self):
        with open("Config.ini", 'r') as f_config:
            for line in f_config.readlines():
                arg_list = line.split("=")
                setattr(self, arg_list[0], arg_list[1].replace("\n", ""))

        self.project_configuration = {configuration_str for configuration_str in self.project_configuration.split(";")}

        if hasattr(self, "macros_ignore"):
            self.macros_ignore = {macros_str for macros_str in self.macros_ignore.split(";")}

    def parse_ignore_file(self):
        with open("IgnoreFile.txt", 'r') as f_ignore_file:
            for line in f_ignore_file.readlines():
                self.ignore_file_list.append(Utility.get_abs_join_path(self.vcxproj_path, line.replace("\n", "")))

        # print "self.ignore_file_list", len(self.ignore_file_list)
        # for path in self.ignore_file_list:
        #     print path

    def parse_vcxproj(self):
        for configuration in self.project_configuration:
            self.vcxproj_configuration_dict[configuration] = VcxprojConfiguration()
            vcxproj_file_path = os.path.join(self.vcxproj_path, self.vcxproj_filename)
            # macro_dict中存储的是.vcxproj文件本身使用的宏，而不是编译过程中使用的宏
            macro_dict = {"$(MSBuildThisFileDirectory)": "..\\"}
            self.parse_xml(vcxproj_file_path, macro_dict, configuration)

            # vcxproj_cl_compile_path_list = \
            # self.vcxproj_configuration_dict[configuration].vcxproj_cl_compile_path_list
            # print "vcxproj_cl_compile_path_list", len(vcxproj_cl_compile_path_list)
            # for path in vcxproj_cl_compile_path_list:
            #     print path

            # vcxproj_excluded_from_build_path_list = \
            # self.vcxproj_configuration_dict[configuration].vcxproj_excluded_from_build_path_list
            # print "vcxproj_excluded_from_build_path_list", len(vcxproj_excluded_from_build_path_list)
            # for path in vcxproj_excluded_from_build_path_list:
            #     print path

    def parse_xml(self, file_path, macro_dict, configuration):
        file = ET.ElementTree(file = file_path)
        root = file.getroot()
        self.DFS(root, file_path, macro_dict, configuration)

    def DFS(self, element, file_path, macro_dict, configuration):
        if not self.parse_Condition(element, macro_dict):
            return

        if element.tag.endswith("ProjectConfiguration"):
            self.parse_ProjectConfiguration(element, macro_dict, configuration)
        if element.tag.endswith("AdditionalIncludeDirectories"):
            self.parse_AdditionalIncludeDirectories(element, macro_dict, configuration)
        elif element.tag.endswith("Import"):
            self.parse_Import(element, macro_dict, configuration)
        elif element.tag.endswith("ClCompile"):
            self.parse_ClComplie(element, macro_dict, configuration)
        elif element.tag.endswith("PropertyGroup") and "Label" in element.attrib and element.attrib["Label"] == "UserMacros":
            self.parse_UserMacros(element, file_path, macro_dict)
        elif element.tag.endswith("PreprocessorDefinitions"):
            self.parse_PreprocessorDefinitions(element, configuration)
        elif element.tag.endswith("CharacterSet"):
            self.parse_CharacterSet(element, configuration)

        for child in element:
            self.DFS(child, file_path, macro_dict, configuration)

    def parse_macro(self, path, macro_dict):
        while(True):
            can_replace_macro = False
            for key, value in macro_dict.items():
                if key in path:
                    path = path.replace(key, value)
                    can_replace_macro = True
            if not can_replace_macro:
                break
        return path

    def parse_Condition(self, element, macro_dict):
        if not "Condition" in element.attrib:
            return True

        condition = self.parse_macro(element.attrib["Condition"], macro_dict)
        condition = condition.replace("And", "and").replace("Or", "or")

        if "exists" in condition or "Exists" in condition:
            return True
        
        return eval(condition)

    def parse_ProjectConfiguration(self, element, macro_dict, configuration):
        if element.attrib["Include"] == configuration:
            for child in element:
                if child.tag.endswith("Configuration"):
                    macro_dict["$(Configuration)"] = child.text
                if child.tag.endswith("Platform"):
                    macro_dict["$(Platform)"] = child.text

    def parse_AdditionalIncludeDirectories(self, element, macro_dict, configuration):
        per_path_list = element.text.split(";")
        for per_path in per_path_list:
            per_path = self.parse_macro(per_path, macro_dict)
            per_path = Utility.get_abs_join_path(self.vcxproj_path, per_path)
            vcxproj_search_path_list = self.vcxproj_configuration_dict[configuration].vcxproj_search_path_list
            if per_path not in vcxproj_search_path_list and os.path.isdir(per_path):
                vcxproj_search_path_list.append(per_path)

    def parse_Import(self, element, macro_dict, configuration):
        path = element.attrib["Project"]
        path = self.parse_macro(path, macro_dict)
        path = Utility.get_abs_join_path(self.vcxproj_path, path)
        if os.path.isfile(path):
            self.parse_xml(path, macro_dict, configuration)

    def parse_ClComplie(self, element, macro_dict, configuration):
        if "Include" in element.attrib:
            path = Utility.get_abs_join_path(self.vcxproj_path, element.attrib["Include"])
            vcxproj_cl_compile_path_list = self.vcxproj_configuration_dict[configuration].vcxproj_cl_compile_path_list
            if path.endswith(".cpp") and os.path.isfile(path) and path not in vcxproj_cl_compile_path_list:
                vcxproj_cl_compile_path_list.append(path)
                for child in element:
                    if child.tag.endswith("ExcludedFromBuild") and self.parse_Condition(child, macro_dict):
                        vcxproj_excluded_from_build_path_list = \
                        self.vcxproj_configuration_dict[configuration].vcxproj_excluded_from_build_path_list
                        if path not in vcxproj_excluded_from_build_path_list:
                            vcxproj_excluded_from_build_path_list.append(path)

    def parse_UserMacros(self, element, file_path, macro_dict):
        for child in element:
            path = self.parse_macro(child.text, macro_dict)
            path = Utility.get_abs_join_path(file_path, path) + "\\"
            key = child.tag
            pos = key.rfind("}")
            key = "$(%s)" %(key[pos + 1:],)
            macro_dict[key] = path

    def parse_PreprocessorDefinitions(self, element, configuration):
        vcxproj_macro_dict = self.vcxproj_configuration_dict[configuration].vcxproj_macro_dict
        for macro in element.text.split(";"):
            if macro != "%(PreprocessorDefinitions)":
                if "=" in macro:
                    vcxproj_macro_dict[macro.split("=")[0]] = macro.split("=")[1]
                else:
                    vcxproj_macro_dict[macro] = None

    def parse_CharacterSet(self, element, configuration):
        vcxproj_macro_dict = self.vcxproj_configuration_dict[configuration].vcxproj_macro_dict
        vcxproj_macro_dict[element.text] = None

    def generate_clang_args(self):
        for configuration in self.project_configuration:
            clang_arg_list = self.vcxproj_configuration_dict[configuration].clang_arg_list
            # 虽然不加也没啥关系，但是为了安全还是明确一下处理的是C++代码
            clang_arg_list.append("-x")
            clang_arg_list.append("c++")
            # 这里一定要用C++14，否则会有一大堆匪夷所思的error
            clang_arg_list.append("--std=c++14")
            # 引入宏定义文件，注意这个文件不是预先配置的，而是读取.vcxproj文件的自动生成的
            clang_arg_list.append("-imacrosmacro.txt")
            # warning茫茫多影响debug，既然我们这个工具不是用来查warning的，就不要显示warning了
            clang_arg_list.append("-w")
            # 默认10条error就会使clang终止，我们改成不做限制，有多少error都显示出来
            clang_arg_list.append("-ferror-limit=0")

            vcxproj_search_path_list = self.vcxproj_configuration_dict[configuration].vcxproj_search_path_list
            for path in vcxproj_search_path_list:
                clang_arg_list.append(b"-I" + path)

    def set_clang_config(self):
        clang.cindex.Config.set_library_file("./clang/libclang.dll")

    def create_tasks(self):
        for path in self.input_file_path_list:
            if path in self.ignore_file_list:
                self.statistics.skip_parse_ignore_file_num += 1
                self.statistics.skip_parse_ignore_file_list.append(path)
            else:
                self.create_task(path)

    def create_task(self, path):
        task = Task(path, self)
        task.begin()  

    def display_statistics(self):
        self.statistics.write_html_and_open()


if __name__ == "__main__":
    cpp_include_cleaner = CppIncludeCleaner(sys.argv[1:])
    cpp_include_cleaner.begin()