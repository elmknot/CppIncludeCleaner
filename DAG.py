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
import Utility
reload(sys)
sys.setdefaultencoding('utf-8')

class DAG(object):
    def __init__(self, root, f_debug):
        # DAG的root节点
        self.root = root
        # 用于输出调试结果的文件句柄
        self.f_debug = f_debug
        # 节点字典，key为name，value为DAG节点
        self.name_node_dict = {root.name: root}
        # 被引用节点集合
        self.referenced_node_set = set()
        # 用用的节点结合，即在被引用节点到根节点的路径里的节点集合
        self.used_node_set = set()
        # subroot节点集合
        self.subroot_set = set()
        # 被直接引用的subroot节点集合
        self.directly_referenced_subroot_set = set()
        # 至少一个被引用节点必须通过其#include的subroot节点集合，one_way指的是被引用节点只有这么一条被#include路径
        self.one_way_include_subroot_set = set()
        # 节点#include字典，key为subroot节点，value为其#include的被引用节点集合
        self.subroot_reference_dict = {}
        # include字典，key为原#include路径，value为替换其的最下层#include路径
        self.include_dict = {}

    def add_node(self, name, source, conditional):
        '''
        增加一个节点
        name为节点名字，source为直接#include这个节点的上层节点，conditional表示是否是条件性#include语句
        '''

        # 如果节点不在DAG中，则加入DAG
        if name not in self.name_node_dict:
            self.name_node_dict[name] = DAGNode(name, source, conditional)
        # 如果节点已经在DAG中，则更新节点的source_set
        else:
            self.name_node_dict[name].source_set.add(source)

        # 如果source就是根节点，说明这个节点是subroot节点
        if source == self.root:
            self.subroot_set.add(self.name_node_dict[name])

    def is_subroot(self, node):
        '''
        判断一个节点是否是subroot节点，即直接与root节点连接的节点
        '''

        return node in self.subroot_set

    def process(self, referenced_node_name_set, macro_referenced_node_name_set, \
        complete_original_include_set_dict, complete_referenced_include_set_dict):
        '''
        解析DAG的主函数
        '''

        # name和node的频繁转换太麻烦了，都用node操作
        self.preprocess_node_name_set(referenced_node_name_set)
        self.referenced_node_set = {self.name_node_dict[name] for name in referenced_node_name_set if name in self.name_node_dict}
        self.preprocess_node_name_set(macro_referenced_node_name_set)
        self.macro_referenced_node_set = {self.name_node_dict[name] for name in macro_referenced_node_name_set if name in self.name_node_dict}

        # #incldue的文件中可能有依赖自身，需要加进referenced_node_set的节点
        self.complete_traverse_nodes_to_root(complete_original_include_set_dict, complete_referenced_include_set_dict)

        # 遍历一下
        self.traverse_nodes_to_root()

        Utility.print_or_write_detailed_node_set("self.referenced_node_set", self.referenced_node_set, self.f_debug, False, True)
        # 被其他被引用节点#include的被引用节点是冗余的，可以不算做被引用节点
        self.remove_inner_include_referenced_nodes()

        Utility.print_or_write_normal("self.subroot_set", self.subroot_set, self.f_debug, False, True)
        # 被其他subroot节点#include的subroot节点是冗余的，可以不算做subroot节点
        self.remove_inner_include_subroot_nodes()

        # 对于被宏定义引用的节点，要优先被非conditional的subroot引用
        for node in self.macro_referenced_node_set:
            for source in node.recursive_source_set:
                if self.is_subroot(source) and not source.conditional:
                    if source not in self.subroot_reference_dict:
                        self.subroot_reference_dict[source] = set()
                    self.subroot_reference_dict[source].add(node)
                    break

        # 重置所有node的信息，准备下一次遍历
        self.used_node_set = {self.name_node_dict[name] for name in self.name_node_dict if self.name_node_dict[name].used}
        for node in self.used_node_set:
            node.used = False
            node.recursive_source_set.clear()

        # 再遍历一下
        self.traverse_nodes_to_root()

        # 更新一下used_node_set
        self.used_node_set = {node for node in self.used_node_set if node.used}

        # 标识一下#include每个被引用节点的subroot节点
        for node in self.used_node_set:
            if self.is_subroot(node):
                node.subroot_set.add(node)
            for source in node.recursive_source_set:
                if self.is_subroot(source):
                    node.subroot_set.add(source)

        # 如果一个节点的subroot_set为空，说明是无效节点
        self.referenced_node_set = {node for node in self.referenced_node_set if node.subroot_set}
        self.used_node_set = {node for node in self.used_node_set if node.subroot_set}

        Utility.print_or_write_detailed_node_set("self.referenced_node_set", self.referenced_node_set, self.f_debug, False, True)
        Utility.print_or_write_detailed_node_set("self.used_node_set", self.used_node_set, self.f_debug, False, True)

        # 标识一下哪些subroot节点是被被引用节点直接引用的
        for node in self.referenced_node_set:
            if self.is_subroot(node):
                self.directly_referenced_subroot_set.add(node)
        
        # 能被directly_referenced_subroot_set中的subroot节点#include的被引用节点结合
        directly_referenced_node_set = set()
        # 只有一条被#include路径的被引用节点集合
        one_way_referenced_node_set = set()
        for node in self.referenced_node_set:
            subroot_set = node.subroot_set
            # 如果一个引用节点能被直接引用的subroot所#include，则不用处理    
            for subroot in subroot_set:
                if subroot in self.directly_referenced_subroot_set:
                    directly_referenced_node_set.add(node)
                    break
            # 如果一个引用节点只能被一个不被直接引用的subroot引用，则单独列出
            if len(subroot_set) == 1:
                subroot = subroot_set.pop()
                subroot_set.add(subroot)
                if subroot not in self.directly_referenced_subroot_set:
                    self.one_way_include_subroot_set.add(subroot)
                    one_way_referenced_node_set.add(node)
                    if subroot not in self.subroot_reference_dict:
                        self.subroot_reference_dict[subroot] = set()
                    self.subroot_reference_dict[subroot].add(node)

        # 剩下的引用节点需要继续处理
        left_referenced_node_set = self.referenced_node_set - directly_referenced_node_set - one_way_referenced_node_set

        Utility.print_or_write_detailed_node_set("directly_referenced_node_set", directly_referenced_node_set, self.f_debug, False, True)
        Utility.print_or_write_detailed_node_set("one_way_referenced_node_set", one_way_referenced_node_set, self.f_debug, False, True)
        Utility.print_or_write_detailed_node_set("left_referenced_node_set", left_referenced_node_set, self.f_debug, False, True) 

        # 剩下的subroot需要继续处理
        left_subroot_set = {subroot for subroot in self.subroot_set \
        if subroot not in self.directly_referenced_subroot_set and subroot not in self.subroot_reference_dict}

        Utility.print_or_write_normal("self.subroot_set", self.subroot_set, self.f_debug, False, True)
        Utility.print_or_write_normal("self.directly_referenced_subroot_set", self.directly_referenced_subroot_set, self.f_debug, False, True)
        Utility.print_or_write_normal("self.one_way_include_subroot_set", self.one_way_include_subroot_set, self.f_debug, False, True)
        Utility.print_or_write_normal("left_subroot_set", left_subroot_set, self.f_debug, False, True)

        # 挑出left_referenced_node_set中能被one_way_include_subroot_set中的subroot节点#include的节点
        remove_referenced_node_set = set()
        for node in left_referenced_node_set:
            for subroot in node.subroot_set:
                if subroot in self.one_way_include_subroot_set:
                    self.subroot_reference_dict[subroot].add(node)
                    remove_referenced_node_set.add(node)
                    break
        left_referenced_node_set = left_referenced_node_set - remove_referenced_node_set

        # 挑出剩下的subroot中可能有用的，这里因为后续算法要求有序，所以用list而不是set
        possible_referenced_subroot_list = []
        for node in left_referenced_node_set:
            for subroot in node.subroot_set:
                if subroot not in possible_referenced_subroot_list:
                    possible_referenced_subroot_list.append(subroot)

        # 计算一下possible_referenced_subroot_list中最少哪几个subroot可以覆盖剩下的被引用节点
        self.calculate_min_subroot_list(left_referenced_node_set, possible_referenced_subroot_list)

        for key, value in self.subroot_reference_dict.items():
            for node in value:
                if node in left_referenced_node_set:
                    left_referenced_node_set.remove(node)
        if left_referenced_node_set:
            f_result.write("以下被引用节点无法被#include：\n%s" %(str(left_referenced_node_set),))

        Utility.print_or_write_dict("self.subroot_reference_dict", self.subroot_reference_dict, self.f_debug, False, True)

        # 计算一下每个可以被替换的subroot最低可以用哪个节点替换
        self.calculate_lowest_include_dict()

    # 预处理一下节点名字集合，主要是兼容大小写
    def preprocess_node_name_set(self, node_name_set):
        node_name_add_set = set()
        for node_name in node_name_set:
            for name in self.name_node_dict:
                if node_name.lower() == name.lower():
                    node_name_add_set.add(name)
        node_name_set = node_name_set | node_name_add_set

    # 完整地遍历所有节点
    def complete_traverse_nodes_to_root(self, complete_original_include_set_dict, complete_referenced_include_set_dict):
        if complete_referenced_include_set_dict:
            complete_subroot_set_dict = {}   
            for key in complete_original_include_set_dict:
                complete_subroot_set_dict[key] = {self.name_node_dict[name] \
                for name in complete_original_include_set_dict[key] if name in self.name_node_dict}

            complete_referenced_node_set_dict = {}
            for key in complete_referenced_include_set_dict:
                complete_referenced_node_set_dict[key] = {self.name_node_dict[name] \
                for name in complete_referenced_include_set_dict[key] if name in self.name_node_dict}

            for key in complete_referenced_node_set_dict:
                for node in complete_referenced_node_set_dict[key]:
                    self.traverse_node_to_root(node, node.recursive_source_set)

            for node in self.referenced_node_set:
                self.traverse_node_to_root(node, node.recursive_source_set)

            for key, node_set in complete_referenced_node_set_dict.items():
                for node in node_set:
                    if key not in complete_subroot_set_dict:
                        print 1, node, key, node.recursive_source_set
                        self.referenced_node_set.add(node)
                    elif not node.recursive_source_set & complete_subroot_set_dict[key]:
                        print 2, node, key, node.recursive_source_set, complete_subroot_set_dict[key]
                        self.referenced_node_set.add(node)

        for name, node in self.name_node_dict.items():
            node.used = False
            node.recursive_source_set.clear()  

    # 标识一下哪些节点在引用节点到根节点的路径里，并计算有哪些节点能递归引用一个节点
    def traverse_nodes_to_root(self):
        for node in self.referenced_node_set:
            self.traverse_node_to_root(node, node.recursive_source_set)

    def traverse_node_to_root(self, node, recursive_source_set):
        # 理论上说不应该有交叉引用，但是为了安全还是加个检查
        if node.is_visiting:
            return
        node.is_visiting = True

        recursive_source_set.add(node)

        # 如果当前节点没有遍历过，则先遍历一下当前节点的source_set
        if not node.used:
            for source in node.source_set:
                self.traverse_node_to_root(source, node.recursive_source_set)

        # 把当前节点的recursive_source_set加到下一层传过来的recursive_source_set里
        for recursive_source in node.recursive_source_set:
            recursive_source_set.add(recursive_source)

        if node in node.recursive_source_set:
            node.recursive_source_set.remove(node)

        node.is_visiting = False
        node.used = True

    # 被引用节点集合中，如果有些节点可以被其他节点递归#include，且不是被宏定义引用的节点，则为冗余节点，删了
    def remove_inner_include_referenced_nodes(self):
        while(True):
            redundant_node = None
            for node in self.referenced_node_set:
                if node in self.macro_referenced_node_set:
                    continue
                is_redundant = False
                for source in node.recursive_source_set:
                    if source in self.referenced_node_set:
                        is_redundant = True
                        break
                if is_redundant:
                    redundant_node = node
                    break
            if redundant_node:
                self.referenced_node_set.remove(redundant_node)
            else:
                break  

    # subroot节点集合中，如果有些节点可以被其他节点递归#include，且不是conditional节点#include非conditional节点，则为冗余节点，删了
    def remove_inner_include_subroot_nodes(self):
        while(True):
            redundant_node = None
            for node in self.subroot_set:
                is_redundant = False
                for source in node.recursive_source_set:
                    if source in self.subroot_set:
                        if not node.conditional and source.conditional:
                            continue
                        is_redundant = True
                        break
                if is_redundant:
                    redundant_node = node
                    break
            if redundant_node:
                self.subroot_set.remove(redundant_node)
            else:
                break  

    # 计算subroot_list中最少几个subroot节点可以将referenced_node_set中的节点全部#include
    def calculate_min_subroot_list(self, referenced_node_set, subroot_list):
        for i in range(1, len(subroot_list) + 1):
            n = len(subroot_list)
            if self.calculate_min_subroot_list_n(referenced_node_set, subroot_list, [False] * n, i):
                break

    def calculate_min_subroot_list_n(self, referenced_node_set, subroot_list, used_subroot_index_list, n):
        if n == 0:
            used_subroot_list = []
            for i in range(len(used_subroot_index_list)):
                if used_subroot_index_list[i]:
                    used_subroot_list.append(subroot_list[i])
            for node in referenced_node_set:
                is_in = False
                for subroot in node.subroot_set:
                    if subroot in used_subroot_list:
                        is_in = True
                        break
                if not is_in:
                    return False
            for node in referenced_node_set:
                for subroot in node.subroot_set:
                    if subroot in used_subroot_list:
                        if subroot not in self.subroot_reference_dict:
                            self.subroot_reference_dict[subroot] = set()
                        self.subroot_reference_dict[subroot].add(node)
                        break
            return True
        else:
            length = len(used_subroot_index_list)
            index = -1
            for i in range(length):
                if used_subroot_index_list[length - 1 - i] == True:
                    index = length - 1 - i
                    break
            for i in range(index + 1, length):
                used_subroot_index_list[i] = True
                if self.calculate_min_subroot_list_n(referenced_node_set, subroot_list, used_subroot_index_list, n - 1):
                    return True
                else:
                    used_subroot_index_list[i] = False

    def calculate_lowest_include_dict(self):
        # 用广度优先遍历计算所有节点到所有节点的最短路径
        distance_dict = {}
        for node in self.used_node_set:
            distance_dict[node] = self.get_node_to_all_nodes_distance(node)

        Utility.print_or_write_dict("distance_dict", distance_dict, self.f_debug, False, True)

        # 遍历一下，找出最低的#include路径
        for subroot, referenced_node_set in self.subroot_reference_dict.items():
            max_distance = -1
            min_sum_distance = 10000
            lowest_node = None
            for used_node in self.used_node_set:
                is_valid = True
                for referenced_node in referenced_node_set:
                    if used_node not in distance_dict[referenced_node] or subroot not in distance_dict[used_node]:
                        is_valid = False
                        break
                if is_valid:
                    sum_distance = 0
                    for referenced_node in referenced_node_set:
                        sum_distance += distance_dict[referenced_node][used_node]
                    if distance_dict[used_node][subroot] > max_distance \
                    or (distance_dict[used_node][subroot] == max_distance and sum_distance < min_sum_distance):
                        max_distance = distance_dict[used_node][subroot]
                        min_sum_distance = sum_distance
                        lowest_node = used_node
            self.subroot_reference_dict[subroot] = lowest_node

    def get_node_to_all_nodes_distance(self, node):
        distance_dict = {}
        to_visit_node_set = set([node])
        to_to_visit_node_set = set()
        visited_node_set = set()
        distance = 0
        while(to_visit_node_set):
            to_to_visit_node_set.clear()
            for visit_node in to_visit_node_set:
                distance_dict[visit_node] = distance
                visited_node_set.add(visit_node)
                for source in visit_node.source_set:
                    if source not in to_visit_node_set and source not in visited_node_set:
                        to_to_visit_node_set.add(source)
            distance += 1
            to_visit_node_set = set(to_to_visit_node_set)
        return distance_dict

    # 生成每个有效#include语句与可以替换其的最下层#include语句的对应字典
    def get_include_dict(self):
        for subroot in self.directly_referenced_subroot_set:
            self.include_dict[subroot.name] = subroot.name
        for subroot, include_node in self.subroot_reference_dict.items():
            self.include_dict[subroot.name] = include_node.name
        Utility.print_or_write_dict("include_dict", self.include_dict, self.f_debug, False, True)
        return self.include_dict


class DAGNode(object):
    def __init__(self, name, source, conditional):
        # 名字
        self.name = name
        # 是否是条件性的#include语句
        self.conditional = conditional
        # 直接#include此节点的节点集合
        self.source_set = set([source]) if source else set()
        # 递归#include此节点的节点集合
        self.recursive_source_set = set()
        # subroot节点集合
        self.subroot_set = set()
        # 节点是否正在被访问
        self.is_visiting = False
        # 节点是否有用，即是否在被引用节点到根节点的路径里
        self.used = False

    def __repr__(self):
        # 为了便于debug，print的时候直接显示name
        return self.name

    def __str__(self):
        # 为了便于debug，用str输出的时候直接显示name
        return self.name

    def __hash__(self):
        # 为了使DAGNode能加入set，能做key，定制一下__hash__函数
        return hash(self.name)