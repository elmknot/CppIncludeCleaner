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
import shutil
import time
import clang.cindex
import Utility
from DAG import DAG, DAGNode
reload(sys)
sys.setdefaultencoding('utf-8')

class Task(object):
    def __init__(self, file_path, cleaner):
        # 待处理文件的路径
        self.file_path = file_path
        # 所属的CppIncludeCleaner类
        self.cleaner = cleaner
        # 被设置为不编译时的警告文字
        self.warning_text = ""
        # 是否含有条件性的#include
        self.include_conditional = False
        # 搜索路径列表
        self.search_path_list = []
        # 待处理文件中原有的#include语句字典，key为行号，value为相对路径
        self.line_include_dict = {}
        # 待处理文件中原有的#include语句字典，key为相对路径，value为绝对路径
        self.original_include_dict = {}
        # 待处理文件中可以删除的#include语句字典，key为相对路径，value为绝对路径
        self.to_delete_include_dict = {}
        # 待处理文件中可以替换的#include语句字典，key为替换前的相对路径，value为替换后的绝对路径
        self.to_replace_include_dict = {}
        # 待处理文件中不变的#include语句字典，key为相对路径，value为绝对路径
        self.unchanged_include_dict = {}
        # 待处理文件中被引用的文件路径集合
        self.referenced_include_set = set()
        # 待处理文件中被宏定义引用的文件路径集合
        self.macro_referenced_include_set = set()
        # 完整的原有的#include语句集合字典，key为文件名，value为该文件中原有的#include语句集合
        self.complete_original_include_set_dict = {}
        # 完整的被引用文件路径集合字典，key为文件名，value为该文件中被引用的文件路径集合
        self.complete_referenced_include_set_dict = {}

    def begin(self):
        self.cl_compile = True
        self.excluded_from_file = False
        for configuration in self.cleaner.vcxproj_configuration_dict.values():
            if self.file_path not in configuration.vcxproj_cl_compile_path_list:
                self.cl_compile = False
            if self.file_path in configuration.vcxproj_excluded_from_build_path_list:
                self.excluded_from_file = True

            for search_path in configuration.vcxproj_search_path_list:
                if search_path not in self.search_path_list:
                    self.search_path_list.append(search_path)

        if not self.cl_compile:
            if self.cleaner.enable_not_cl_compile == "1":
                self.warning_text += u"\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!注意!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n\n"
                self.warning_text += u"              此文件在.vcxproj工程文件配置中未被ClCompile定义过\n"
                self.warning_text += u"             因此可能与其他.cpp文件有相互依赖从而使分析结果不准确\n"
                self.warning_text += u"\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
            else:
                self.cleaner.statistics.skip_parse_cl_compile_num += 1
                self.cleaner.statistics.skip_parse_cl_compile_list.append(self.file_path)
                return
        if self.excluded_from_file:
            if self.cleaner.enable_excluded_from_build == "1":
                self.warning_text += u"\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!注意!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n\n"
                self.warning_text += u"            此文件在.vcxproj工程文件配置中被设置为ExcluedFromBuild\n"
                self.warning_text += u"             因此可能与其他.cpp文件有相互依赖从而使分析结果不准确\n"
                self.warning_text += u"\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
            else:
                self.cleaner.statistics.skip_parse_excluded_from_build_num += 1
                self.cleaner.statistics.skip_parse_excluded_from_build_list.append(self.file_path)
                return
        print self.warning_text
        print "Process File:", self.file_path

        time_list = []
        time_list.append(time.time())

        if self.handle_translation_unit(time_list): 
            # 解析DAG
            self.parse_dag()

            time_list.append(time.time())
            Utility.print_or_write_normal("Parse dag Cost time", time_list[-1] - time_list[-2], self.f_debug, False, True)

            self.cleaner.statistics.parse_file_num += 1

            # 自动clean
            self.auto_clean()

        self.f_diagnostics.close()
        self.f_debug.close()

    def handle_translation_unit(self, time_list):
        count = 0 
        for key, value in self.cleaner.vcxproj_configuration_dict.items():
            count += 1

            # 生成翻译单元
            tu = self.generate_translation_unit(value, count == 1)
            Utility.print_or_write_normal("Process For Configuration", key, self.f_debug, False, True)
            if not tu:
                return False
            time_list.append(time.time())
            Utility.print_or_write_normal("Generate Translation Unit Cost time", \
                time_list[-1] - time_list[-2], self.f_debug, False, True)

            # 解析翻译单元
            if not self.parse_translation_unit(tu, value, count == 1):
                return False
            time_list.append(time.time())
            Utility.print_or_write_normal("Parse Translation Unit Cost time", \
                time_list[-1] - time_list[-2], self.f_debug, False, True)

        return True

    def generate_translation_unit(self, configuration, is_first):
        if is_first:
            self.index = clang.cindex.Index.create()
            self.f_diagnostics = Utility.make_output_file("diagnostics/", self.file_path, self.cleaner.vcxproj_path)
            self.f_debug = Utility.make_output_file("debug/", self.file_path, self.cleaner.vcxproj_path)

        # 生成宏定义文件
        with open("macro.txt", 'w') as f_macro:
            count = 0
            for key, value in configuration.vcxproj_macro_dict.items():
                count += 1
                if count > 1:
                    f_macro.write("\n")
                if value != None:
                    f_macro.write("#define " + key + " " + value)
                else:
                    f_macro.write("#define " + key)

        # 生成翻译单元，这里的解析选项不能选默认的0，否则会丢失#include语句相关的信息
        tu_parse_options = clang.cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD
        tu = self.index.parse(self.file_path, configuration.clang_arg_list, None, tu_parse_options)

        # 把clang生成AST过程中产生的诊断信息输出一下
        has_error = False
        for diag in tu.diagnostics:
            self.f_diagnostics.write(diag.__repr__() + "\n")
            # 如果有severity >= 3，即error和fatal的diagnostics，则不要继续解析了，反正也是错的
            if diag.severity >= 3:
                has_error = True
        if has_error:
            self.cleaner.statistics.skip_parse_generate_tu_fail_num += 1
            self.cleaner.statistics.skip_parse_generate_tu_fail_list.append(self.file_path)
            return None
        else:
            return tu

    def parse_translation_unit(self, tu, configuration, is_first):
        self.f_debug.write(self.warning_text)
        self.current_include_conditional = False

        cursor = tu.cursor
        cursor_path = Utility.get_abs_path(cursor.displayname, cursor.displayname, configuration)
        if is_first:
            self.dag = DAG(DAGNode(cursor_path, None, self.current_include_conditional), self.f_debug)
        self.f_debug.write("Reference records of %s\n" %(cursor_path,))
        for child in cursor.walk_preorder():
            if not child.location.file:
                continue

            # 通过处理__cplusplus宏间接处理extern "C"语句
            if child.displayname == "__cplusplus" and child.kind == clang.cindex.CursorKind.MACRO_INSTANTIATION:
                Utility.print_or_write_normal("__cplusplus Reference", "%s %s %s %s %s" %(child.displayname, \
                    str(child.kind), child.location.line, child.location.column, \
                    child.location.file.name), self.f_debug, False, True)
                self.referenced_include_set.add(os.path.abspath(child.location.file.name))

            # 处理#include语句
            self.parse_include(cursor, child, configuration)

            if child.location.file.name == cursor.displayname:
                # 如果遇到其他平台的宏，则不要继续parse了，因为很有可能是错的
                if child.kind == clang.cindex.CursorKind.MACRO_INSTANTIATION \
                and child.displayname in self.cleaner.macros_ignore:
                    self.cleaner.statistics.skip_parse_ignore_macro_file_num += 1
                    self.cleaner.statistics.skip_parse_ignore_macro_file_list.append(self.file_path)
                    return False
                # 处理auto语义定义的自动变量
                self.parse_auto(tu, cursor, child)

            if not child.referenced:
                continue
            if not child.referenced.location.file:
                continue
            # 引用本文件的cursor不用处理
            if child.referenced.location.file.name == child.location.file.name:
                continue        
            # 本文件内的cursor
            if child.location.file.name == cursor.displayname:
                Utility.print_or_write_normal("Reference", "%s %s %s %s %s" %(child.displayname, \
                    str(child.kind), child.location.line, child.location.column, \
                    child.referenced.location.file.name), self.f_debug, False, True)
                self.referenced_include_set.add(os.path.abspath(child.referenced.location.file.name))
                if child.kind == clang.cindex.CursorKind.MACRO_INSTANTIATION:
                    self.macro_referenced_include_set.add(os.path.abspath(child.referenced.location.file.name))
                    # 出现宏定义之后的#include语句为条件性的#include语句
                    self.current_include_conditional = True
            # 其他文件内的cursor
            elif self.cleaner.enable_complete_parse == "1":
                Utility.print_or_write_normal("Complete Reference", "%s %s %s %s %s %s" %(child.displayname, \
                    str(child.kind), child.location.file.name, child.location.line, child.location.column, \
                    child.referenced.location.file.name), self.f_debug, False, True)
                if child.location.file.name not in self.complete_referenced_include_set_dict:
                    self.complete_referenced_include_set_dict[child.location.file.name] = set()
                child_referenced_include_set = self.complete_referenced_include_set_dict[child.location.file.name]
                child_referenced_include_set.add(os.path.abspath(child.referenced.location.file.name))

        return True

    def parse_include(self, cursor, child, configuration):
        if child.kind == clang.cindex.CursorKind.INCLUSION_DIRECTIVE:
            abs_path = Utility.get_abs_path(child.displayname, child.location.file.name, configuration)
            if abs_path:
                source_name = os.path.abspath(child.location.file.name)
                if source_name in self.dag.name_node_dict:
                    self.dag.add_node(abs_path, self.dag.name_node_dict[source_name], self.current_include_conditional)
                    # 本文件内的#include语句
                    if child.location.file.name == cursor.displayname:
                        self.line_include_dict[child.location.line] = child.displayname
                        self.original_include_dict[child.displayname] = abs_path
                        self.include_conditional = self.current_include_conditional
                    # 其他文件内的#include语句
                    elif self.cleaner.enable_complete_parse == "1":
                        if child.location.file.name not in self.complete_original_include_set_dict:
                            self.complete_original_include_set_dict[child.location.file.name] = set()
                        child_original_include_set = self.complete_original_include_set_dict[child.location.file.name]
                        child_original_include_set.add(abs_path)

    def parse_auto(self, tu, cursor, child):
        """
        auto语义定义的自动变量是一个很大的坑
        直接遍历clang生成的AST找不到deduced类型
        理论上最简单直接的方法是获取声明的变量或是调用函数返回值的类型对应的Cursor，然而折腾了一天也没找到这样的接口
        所以只能绕个弯路了
        先判断出一个变量是不是auto，然后找到这一行后面所有referenced的cursor
        遍历这些cursor，在他们referenced的cursor的这一行前面所有TYPE_REF类型的cursor都认为是referenced_node
        """
        offset_cursor_list = []
        if child.kind == clang.cindex.CursorKind.VAR_DECL and child.type.kind == clang.cindex.TypeKind.AUTO:
            start_offset = child.location.offset
            offset = start_offset
            while(True):
                offset += 1
                location = clang.cindex.SourceLocation.from_offset(tu, child.location.file, offset)
                offset_cursor = clang.cindex.Cursor.from_location(tu, location)
                if offset_cursor.location.line != child.location.line:
                    return
                if not offset_cursor.referenced:
                    continue
                if offset_cursor.referenced.location.file.name == child.location.file.name:
                    continue
                if offset_cursor not in offset_cursor_list:
                    offset_cursor_list.append(offset_cursor)
                    for i in range(offset_cursor.referenced.location.column):
                        type_ref_location = clang.cindex.SourceLocation.from_position(\
                            tu, offset_cursor.referenced.location.file, offset_cursor.referenced.location.line, i)
                        type_ref_cursor = clang.cindex.Cursor.from_location(tu, type_ref_location)
                        if type_ref_cursor and type_ref_cursor.kind == clang.cindex.CursorKind.TYPE_REF:
                            Utility.print_or_write_normal("Auto Reference", "%s %s %s %s %s" %(type_ref_cursor.displayname, \
                                str(type_ref_cursor.kind), type_ref_cursor.location.line, type_ref_cursor.location.column, \
                                type_ref_cursor.referenced.location.file.name), self.f_debug, False, True)
                            self.referenced_include_set.add(os.path.abspath(type_ref_cursor.referenced.location.file.name))

    def parse_dag(self):
        # 如果没有条件性的#include语句，则不用进行这一部分特殊处理
        if not self.include_conditional:
            self.macro_referenced_include_set.clear()

        self.dag.process(self.referenced_include_set, self.macro_referenced_include_set, \
            self.complete_original_include_set_dict, self.complete_referenced_include_set_dict)

        Utility.print_or_write_normal("self.referenced_include_set", self.referenced_include_set, self.f_debug, False, True)

        include_dict = self.dag.get_include_dict()

        # 根据DAG分析结果得到to_delete_include_dict、to_replace_include_dict和unchanged_include_dict
        for rel_path, abs_path in self.original_include_dict.items():
            if abs_path not in include_dict:
                self.to_delete_include_dict[rel_path] = abs_path
            elif include_dict[abs_path] != abs_path:
                self.to_replace_include_dict[rel_path] = include_dict[abs_path]
            else:
                self.unchanged_include_dict[rel_path] = abs_path

        # 如果替换后的路径其实就在原始的#include路径里，处理一下
        for key in self.to_replace_include_dict.keys():
            if self.to_replace_include_dict[key] in self.original_include_dict.values():
                for rel_path, abs_path in self.original_include_dict.items():
                    if rel_path == key:
                        self.to_delete_include_dict[rel_path] = abs_path
                    if abs_path == self.to_replace_include_dict[key]:
                        self.unchanged_include_dict[rel_path] = self.to_replace_include_dict[key]
                        del self.to_delete_include_dict[rel_path]
                del self.to_replace_include_dict[key]

        self.cleaner.statistics.original_include_num += len(self.original_include_dict)
        self.cleaner.statistics.can_delete_include_num += len(self.to_delete_include_dict)
        self.cleaner.statistics.can_replace_include_num += len(self.to_replace_include_dict)

        Utility.print_or_write_dict("self.original_include_dict", self.original_include_dict, self.f_debug, False, True)
        Utility.print_or_write_dict("self.to_delete_include_dict", self.to_delete_include_dict, self.f_debug, False, True)
        Utility.print_or_write_dict("self.to_replace_include_dict", self.to_replace_include_dict, self.f_debug, False, True)
        Utility.print_or_write_dict("self.unchanged_include_dict", self.unchanged_include_dict, self.f_debug, False, True)

        # 写入最终结果
        f_result = Utility.make_output_file("result/", self.file_path, self.cleaner.vcxproj_path)
        f_result.write("可以删除的#include语句如下：\n")
        for key, value in self.to_delete_include_dict.items():
            f_result.write(value + "\n")
        f_result.write("\n可以替换的#include语句如下：\n")
        for key, value in self.to_replace_include_dict.items():
            f_result.write("%s 替换为： %s\n" %(key, value))
        f_result.close()

    def auto_clean(self):
        if self.cleaner.enable_auto_clean != "1":
            return
        if not self.cl_compile and self.cleaner.enable_auto_clean_not_cl_compile != "1":
            self.cleaner.statistics.skip_clean_cl_compile_num += 1
            self.cleaner.statistics.skip_clean_cl_compile_list.append(self.file_path)
            return
        if self.excluded_from_file and self.cleaner.enable_auto_clean_excluded_from_build != "1":
            self.cleaner.statistics.skip_clean_excluded_from_build_num += 1
            self.cleaner.statistics.skip_clean_excluded_from_build_list.append(self.file_path)
            return
        if len(self.to_delete_include_dict) == 0 and len(self.to_replace_include_dict) == 0:
            return

        lines = []
        pre_str = ""
        count = 0
        f = open(self.file_path, 'r')
        for line in f.readlines():
            count += 1
            if count in self.line_include_dict:
                include_path = self.line_include_dict[count]
                if include_path in self.to_delete_include_dict:
                    Utility.print_or_write_normal("Auto Delete #include", include_path, self.f_debug, False, True)
                    # 文件开头有可能有几个字符是用来标识编码的（比如带BOM的编码就是三个字符），如果第一行被删了，那么需要把这几个字符加回去
                    if count == 1:
                        pos = line.find("#")
                        pre_str = line[0:pos]
                elif include_path in self.to_replace_include_dict:
                    new_include_path = Utility.get_rel_path(self.to_replace_include_dict[include_path], self.search_path_list)
                    if new_include_path:
                        Utility.print_or_write_normal("Auto Replace #include", include_path, self.f_debug, False, True)
                        new_line = line.replace(include_path, new_include_path)
                        lines.append(new_line)
                    else:
                        Utility.print_or_write_normal("Error! Invalid Repalce #include", \
                            include_path, self.f_debug, False, True) 
                        lines.append(line)
                elif include_path in self.unchanged_include_dict:
                    lines.append(line)
                else:
                    Utility.print_or_write_normal("Error! Invalid #include", include_path, self.f_debug, False, True)
                    lines.append(line)         
            else:
                lines.append(line)
        f.close()

        shutil.copyfile(self.file_path, self.file_path.replace(".cpp", "_bk.cpp"))

        count = 0
        with open(self.file_path, 'w') as f:
            for line in lines:
                count += 1
                if count == 1:
                    f.write(pre_str + line)
                else:
                    f.write(line)

        # 重新解析一遍，看看会不会失败
        if self.reparse():       
            self.cleaner.statistics.clean_file_num += 1
            self.cleaner.statistics.auto_delete_include_num += len(self.to_delete_include_dict)
            self.cleaner.statistics.auto_replace_include_num += len(self.to_replace_include_dict)
        else:
            self.cleaner.statistics.original_include_num -= len(self.original_include_dict)
            self.cleaner.statistics.can_delete_include_num -= len(self.to_delete_include_dict)
            self.cleaner.statistics.can_replace_include_num -= len(self.to_replace_include_dict)

    def reparse(self):
        if self.cleaner.enable_reparse != "1":
            os.remove(self.file_path.replace(".cpp", "_bk.cpp"))
            return True

        for configuration in self.cleaner.vcxproj_configuration_dict.values():
            index = clang.cindex.Index.create()
            with open("macro.txt", 'w') as f_macro:
                count = 0
                for key, value in configuration.vcxproj_macro_dict.items():
                    count += 1
                    if count > 1:
                        f_macro.write("\n")
                    if value != None:
                        f_macro.write("#define " + key + " " + value)
                    else:
                        f_macro.write("#define " + key)
            tu = index.parse(self.file_path, configuration.clang_arg_list)
            has_error = False
            for diag in tu.diagnostics:
                if diag.severity >= 3:
                    has_error = True
                    break
            if has_error:
                self.cleaner.statistics.skip_parse_reparse_fail_num += 1
                self.cleaner.statistics.skip_parse_reparse_fail_list.append(self.file_path)
                os.remove(self.file_path)
                os.rename(self.file_path.replace(".cpp", "_bk.cpp"), self.file_path)
                return False

        os.remove(self.file_path.replace(".cpp", "_bk.cpp"))
        return True

