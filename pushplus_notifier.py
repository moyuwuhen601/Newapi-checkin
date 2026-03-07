# -*- coding: utf-8 -*-
"""
PushPlus 通知模块
用于发送签到结果到 PushPlus 推送服务
"""

import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

try:
    import requests
except ImportError:
    requests = None

PUSHPLUS_API = 'http://www.pushplus.plus/send'


class PushPlusNotifier:
    """PushPlus 推送通知类"""

    def __init__(self, token: str, topic: Optional[str] = None):
        """
        初始化 PushPlus 通知器

        Args:
            token: PushPlus 用户令牌
            topic: 群组编码（一对多推送时使用），为空则仅推送给自己
        """
        self.token = token
        self.topic = topic

    def send(self, title: str, content: str, template: str = 'markdown') -> bool:
        """
        发送消息

        Args:
            title: 消息标题
            content: 消息内容
            template: 内容模板 (html / txt / markdown / json)

        Returns:
            是否发送成功
        """
        if requests is None:
            print('[PushPlus] 错误: 未安装 requests 库')
            return False

        data = {
            'token': self.token,
            'title': title,
            'content': content,
            'template': template,
        }
        if self.topic:
            data['topic'] = self.topic

        try:
            resp = requests.post(PUSHPLUS_API, json=data, timeout=10)
            result = resp.json()

            if result.get('code') == 200:
                print('[PushPlus] 消息发送成功')
                return True
            else:
                print(f'[PushPlus] 发送失败: {result.get("msg", "未知错误")}')
                return False
        except Exception as e:
            print(f'[PushPlus] 发送异常: {e}')
            return False


def format_quota(quota: int) -> str:
    """格式化额度显示"""
    if quota >= 1000000:
        return f'{quota / 1000000:.2f}M'
    elif quota >= 1000:
        return f'{quota / 1000:.2f}K'
    return str(quota)


def _is_session_expired(result: Dict[str, Any]) -> bool:
    """判断是否为 session 失效"""
    if result.get('session_expired'):
        return True
    msg = result.get('message', '').lower()
    return any(kw in msg for kw in ['session', '认证', '过期'])


def build_checkin_report(results: List[Dict[str, Any]], execution_time: str) -> str:
    """
    构建签到报告 Markdown 内容

    Args:
        results: 签到结果列表
        execution_time: 执行时间字符串

    Returns:
        Markdown 格式的报告内容
    """
    success_list = [r for r in results if r.get('success')]
    fail_list = [r for r in results if not r.get('success')]

    lines = [
        '# 📋 NewAPI 签到报告',
        '',
        f'**执行时间**: {execution_time}',
        '',
        '---',
        '',
    ]

    # 成功列表
    if success_list:
        lines.append(f'## ✅ 成功 ({len(success_list)}个)')
        lines.append('')
        lines.append('| 账号 | 奖励 | 详情 |')
        lines.append('|------|------|------|')
        for r in success_list:
            name = r.get('name', '未知账号')
            quota = r.get('quota_awarded', 0)
            quota_str = f'+{format_quota(quota)}' if quota else '-'
            checkin_count = r.get('checkin_count')
            detail = f'已签 {checkin_count} 天' if checkin_count else r.get('message', '成功')
            lines.append(f'| {name} | {quota_str} | {detail} |')
        lines.append('')

    # 失败列表
    if fail_list:
        lines.append(f'## ❌ 失败 ({len(fail_list)}个)')
        lines.append('')
        lines.append('| 账号 | 原因 |')
        lines.append('|------|------|')
        for r in fail_list:
            name = r.get('name', '未知账号')
            message = r.get('message', '未知错误')
            if _is_session_expired(r):
                message = f'⚠️ {message}'
            lines.append(f'| {name} | {message} |')
        lines.append('')

    # 汇总
    lines.append('---')
    lines.append('')

    total = len(results)
    success_count = len(success_list)
    fail_count = len(fail_list)

    if fail_count == 0:
        lines.append(f'**汇总**: 全部成功 ✨ ({success_count}/{total})')
    elif success_count == 0:
        lines.append(f'**汇总**: 全部失败 ⚠️ ({fail_count}/{total})')
    else:
        lines.append(f'**汇总**: 成功 {success_count}，失败 {fail_count}')

    expired = [r for r in fail_list if _is_session_expired(r)]
    if expired:
        lines.append('')
        lines.append('> ⚠️ **注意**: 部分账号 Session 已失效，请及时更新 Cookie！')

    return '\n'.join(lines)


def send_checkin_notification(results: List[Dict[str, Any]], execution_time: Optional[str] = None) -> bool:
    """
    发送签到通知到 PushPlus

    从环境变量读取配置:
        PUSHPLUS_TOKEN: 用户令牌（必填）
        PUSHPLUS_TOPIC: 群组编码（选填）

    Args:
        results: 签到结果列表
        execution_time: 执行时间（可选，默认当前时间）

    Returns:
        是否发送成功
    """
    token = os.environ.get('PUSHPLUS_TOKEN', '')
    topic = os.environ.get('PUSHPLUS_TOPIC', '')

    if not token:
        print('[PushPlus] 未配置 PUSHPLUS_TOKEN，跳过通知')
        return False

    if not execution_time:
        execution_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    report = build_checkin_report(results, execution_time)

    success_count = len([r for r in results if r.get('success')])
    fail_count = len([r for r in results if not r.get('success')])

    if fail_count == 0:
        title = f'✅ 签到成功 ({success_count}个账号)'
    elif success_count == 0:
        title = f'❌ 签到失败 ({fail_count}个账号)'
    else:
        title = f'📋 签到完成 (成功{success_count}/失败{fail_count})'

    notifier = PushPlusNotifier(token, topic if topic else None)
    return notifier.send(title, report)


if __name__ == '__main__':
    test_results = [
        {
            'name': '主力站',
            'success': True,
            'message': '签到成功',
            'quota_awarded': 500000,
            'checkin_count': 15,
        },
        {
            'name': '备用站',
            'success': True,
            'message': '签到成功',
            'quota_awarded': 100000,
            'checkin_count': 8,
        },
        {
            'name': '测试站',
            'success': False,
            'message': 'Session 已过期',
            'session_expired': True,
        },
    ]

    report = build_checkin_report(test_results, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print('=== 消息预览 ===')
    print(report)
    print('================')

    if os.environ.get('PUSHPLUS_TOKEN'):
        send_checkin_notification(test_results)
    else:
        print('\n提示: 设置 PUSHPLUS_TOKEN 环境变量后可测试实际发送')
