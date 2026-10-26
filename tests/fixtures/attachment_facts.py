"""Independent attachment facts; no product-generated expectations."""
import base64

# One controlled pixel, original PNG bytes (no image conversion in the application).
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=')
DOCUMENT = b'Task 09 offline evidence\r\nOriginal bytes: 0123456789\x00\xff'
OTHER = b'Different content, same filename.\n'


def facts(root):
    image = str(root / 'sample.png')
    document = (root / 'sample.bin').as_uri()
    missing = str(root / 'absent.png')
    def session(identity, name, items, **metadata):
        return {'thread': {'id': identity, 'name': name, 'cwd': 'C:/Task09',
                           'createdAt': 100, 'updatedAt': 200, **metadata},
                'turns': [{'id': 'turn', 'startedAt': 200, 'status': 'completed', 'items': items}]}
    return {'sessions': [
        session('main', '任务09 · 附件归档', [
            {'id': 'picture', 'type': 'userMessage', 'content': [
                {'type': 'text', 'text': '受控图片与普通附件。正文 C:/never-read.txt 不算附件。'},
                {'type': 'localImage', 'path': image}]},
            {'id': 'shared', 'type': 'userMessage', 'content': [{'type': 'localImage', 'path': image}]},
            {'id': 'documents', 'type': 'mcpToolCall', 'server': 'controlled', 'tool': 'evidence',
             'arguments': {}, 'status': 'completed', 'error': None, 'result': {'content': [
                 {'type': 'resource_link', 'name': '../sample.bin', 'uri': document},
                 {'type': 'resource_link', 'name': 'sample.bin', 'uri': (root / 'other' / 'sample.bin').as_uri()}]}},
            {'id': 'missing', 'type': 'userMessage', 'content': [
                {'type': 'text', 'text': '缺失附件不能影响消息保存。'},
                {'type': 'localImage', 'path': missing},
                {'type': 'image', 'url': 'https://example.invalid/remote.png'}]},
            {'id': 'reply', 'type': 'agentMessage', 'phase': 'final_answer', 'text': '已保留对话和工具证据。'},
            {'id': 'unarchived', 'type': 'subAgentActivity', 'agentThreadId': 'unarchived', 'kind': 'started'}]),
        session('child', '一层关联 · 共享图片', [
            {'id': 'child-picture', 'type': 'userMessage', 'content': [{'type': 'localImage', 'path': image}]}], parentThreadId='main'),
        session('grandchild', '二层 · 不应导出', [
            {'id': 'secret', 'type': 'userMessage', 'content': [{'type': 'text', 'text': '二层正文不应装入主包'}]}], parentThreadId='child'),
        session('empty', '无附件会话', [
            {'id': 'plain', 'type': 'userMessage', 'content': [{'type': 'text', 'text': '普通中文对话'}]}])
    ]}
