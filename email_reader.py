#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import poplib
import getpass
import email
from email.parser import BytesParser
from email.header import decode_header
import ssl
import sys
import re
import time
# 2925.com去注册邮箱
def extract_email_and_code(content):
    """从邮件内容中提取邮箱地址和验证码"""
    email_pattern = r'([a-zA-Z0-9]+@2925\.com)'
    email_match = re.search(email_pattern, content)
    email = email_match.group(1) if email_match else None

    code_pattern = r'\b(\d{6})\b'
    code_match = re.search(code_pattern, content)
    code = code_match.group(1) if code_match else None

    return email, code

def decode_str(s):
    """解码邮件主题或发件人等字段"""
    if s is None:
        return ""
    value, charset = decode_header(s)[0]
    if isinstance(value, bytes):
        if charset:
            try:
                return value.decode(charset)
            except UnicodeDecodeError:
                return value.decode('utf-8', errors='replace')
        else:
            try:
                return value.decode('utf-8')
            except UnicodeDecodeError:
                return value.decode('utf-8', errors='replace')
    else:
        return value

def get_email_content(msg):
    """获取邮件内容"""
    content = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            
            if "attachment" in content_disposition:
                continue
                
            if content_type == "text/plain" or content_type == "text/html":
                try:
                    body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='replace')
                    content += body + "\n"
                except:
                    pass
    else:
        content_type = msg.get_content_type()
        if content_type == "text/plain" or content_type == "text/html":
            try:
                body = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8', errors='replace')
                content += body
            except:
                pass
    
    return content

def fetch_emails(target_email=None, timeout_minutes=10):
    """连接邮箱并持续监控特定邮件，返回(邮箱地址, 验证码)元组"""
    pop3_server = "mail.2925.com"
    target_sender = "Cursor"
    target_subject = "Verify your email address"
    
    username = ''#替换为你的2925邮箱
    password = ''#替换为你的2925邮箱密码
    
    print(f"正在监控邮箱 {username}@{pop3_server} 以获取验证码")
    print(f"目标邮箱: {target_email}")
    print(f"超时时间: {timeout_minutes}分钟")
    
    # 初始化已知邮件ID列表
    known_emails = set()
    start_time = time.time()
    
    while True:
        # 检查是否超时
        elapsed_seconds = time.time() - start_time
        if elapsed_seconds > timeout_minutes * 60:
            print(f"超时: 已监控 {int(elapsed_seconds)} 秒，未收到验证码")
            return (None, None)
        
        try:
            # 连接POP3服务器
            context = ssl.create_default_context()
            pop_conn = poplib.POP3_SSL(pop3_server, context=context)
            pop_conn.user(username)
            pop_conn.pass_(password)
            
            # 获取邮件统计
            msg_count = pop_conn.stat()[0]
            if msg_count == 0:
                print("邮箱为空，等待 3 秒后重试...")
                pop_conn.quit()
                time.sleep(3)
                continue
                
            # 获取所有邮件的 UIDL (唯一标识)
            resp, uidl_list, octets = pop_conn.uidl()
            current_emails = set()
            
            # 构建邮件ID到UIDL的映射
            id_to_uidl = {}
            for item in uidl_list:
                parts = item.decode().split()
                msg_id = int(parts[0])
                uidl = parts[1]
                current_emails.add(uidl)
                id_to_uidl[msg_id] = uidl
            
            # 查找新邮件 (在current_emails中但不在known_emails中的)
            new_uidls = current_emails - known_emails
            if new_uidls:
                # print(f"检测到 {len(new_uidls)} 封新邮件!")
                
                # 找出新UIDL对应的消息ID
                new_msg_ids = [msg_id for msg_id, uidl in id_to_uidl.items() if uidl in new_uidls]
                
                # 检查新邮件
                for msg_id in new_msg_ids:
                    try:
                        # print(f"检查邮件 ID: {msg_id}, UIDL: {id_to_uidl[msg_id]}")
                        
                        # 获取邮件内容
                        resp, lines, octets = pop_conn.retr(msg_id)
                        msg_content = b'\r\n'.join(lines)
                        msg = BytesParser().parsebytes(msg_content)
                        
                        # 获取邮件信息
                        subject = decode_str(msg.get("Subject", ""))
                        from_addr = decode_str(msg.get("From", ""))
                        date = decode_str(msg.get("Date", ""))
                        
                        # print(f"邮件信息: 发件人={from_addr}, 主题={subject}, 日期={date}")
                        
                        # 检查是否是目标邮件
                        if target_sender.lower() in from_addr.lower() and target_subject.lower() in subject.lower():
                            print(f"找到匹配的目标邮件!")
                            
                            # 获取邮件内容
                            content = get_email_content(msg)
                            
                            # 提取邮箱和验证码
                            extracted_email, code = extract_email_and_code(content)
                            # print(f"提取结果: 邮箱={extracted_email}, 验证码={code}")
                            
                            # 检查是否匹配目标邮箱
                            if target_email and extracted_email and extracted_email.lower() != target_email.lower():
                                # print(f"邮箱不匹配: 期望={target_email}, 实际={extracted_email}")
                                continue
                            
                            # 验证码格式检查
                            if code and code.isdigit() and len(code) == 6:
                                print(f"成功获取验证码: {code}")
                                pop_conn.quit()
                                return (extracted_email, code)
                    except Exception as e:
                        print(f"处理邮件 {msg_id} 时出错: {str(e)}")
            
            # 更新已知邮件集合
            known_emails = current_emails
            
            # 关闭连接
            pop_conn.quit()
            
            # 输出监控状态
            print(f"已监控 {int(elapsed_seconds)}秒... [{int((timeout_minutes*60 - elapsed_seconds)/60)}分钟后超时]")
            
            # 短暂等待后继续
            time.sleep(3)
            
        except Exception as e:
            print(f"连接或处理邮件时出错: {str(e)}")
            time.sleep(5)  # 发生错误时等待时间更长
    
    return (None, None)  # 如果跳出循环，返回None

if __name__ == "__main__":
    print("直接测试邮件监控功能")
    # 可以设置你要测试的目标邮箱
    test_email = None  # 设置为None则不检查邮箱匹配
    email_addr, verification_code = fetch_emails(target_email=test_email, timeout_minutes=2)
    if verification_code:
        print(f"成功! 邮箱: {email_addr}, 验证码: {verification_code}")
    else:
        print("未能获取验证码")

