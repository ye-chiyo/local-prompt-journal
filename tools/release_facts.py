"""Independent release facts. No product outputs are used to construct expectations."""
from pathlib import Path
import struct
import zlib

DOCUMENT = b'Release 11 original document\r\n0123456789\x00\xff'


def image_bytes():
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    scanlines = b'\x00' + b'\xff\x00\x00' * 2 + b'\x00' + b'\x00\xff\x00' * 2
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 2, 2, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(scanlines)) + chunk(b'IEND', b'')


def message(identity, text):
    return {'id': identity, 'type': 'userMessage', 'content': [{'type': 'text', 'text': text}]}


def session(identity, cwd, created, text):
    return {'thread': {'id': identity, 'name': '演示会话 ' + identity, 'cwd': cwd, 'createdAt': created, 'updatedAt': 200},
            'turns': [{'id': 'turn-1', 'startedAt': 200, 'status': 'inProgress', 'items': [message('user-1', text)]}]}


def initial(root):
    a = session('A', 'C:/演示甲', 100, '甲会话中文原文：雨巷纸伞')
    a['turns'][0]['items'][0]['content'].append({'type': 'localImage', 'path': str(root / 'sample.png')})
    a['turns'][0]['items'].extend([
        {'id': 'command', 'type': 'commandExecution', 'command': 'controlled evidence only', 'cwd': 'C:/演示甲',
         'commandActions': [], 'status': 'inProgress', 'aggregatedOutput': None, 'exitCode': None},
        {'id': 'document', 'type': 'mcpToolCall', 'server': 'controlled', 'tool': 'release-document', 'arguments': {},
         'status': 'completed', 'error': None, 'result': {'content': [{'type': 'resource_link', 'name': 'sample.bin', 'uri': (root / 'sample.bin').as_uri()}]}}
    ])
    b = session('B', 'C:/演示甲', 160, '乙会话中文原文：相同项目独立记录')
    c = session('C', 'D:/演示乙', 110, '另一项目中文原文：项目隔离')
    c['thread']['parentThreadId'] = 'A'
    c['turns'][0]['items'][0]['content'].append({'type': 'localImage', 'path': str(root / 'sample.png')})
    return {'codexHome': str(root.resolve() / 'controlled-codex-home'),
            'forbidBodyBefore': 190, 'sessions': [a, b, c]}
