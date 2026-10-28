"""Build a self-contained private local plugin outside the source tree."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent


def build(output: Path) -> Path:
    output = output.resolve()
    if output.is_relative_to(ROOT) or output.exists():
        raise ValueError('请提供源码外尚不存在的输出目录。')
    target = output / 'plugins' / 'local-journal'
    shutil.copytree(ROOT / 'plugins' / 'local-journal', target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copytree(ROOT / 'prompt_journal', target / 'server' / 'prompt_journal', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    # Pin the tested interpreter for this machine's installation; source remains portable.
    config = json.loads((target / 'mcp.json').read_text(encoding='utf-8'))
    config['mcpServers']['local-journal']['command'] = sys.executable
    (target / 'mcp.json').write_text(json.dumps(config, indent=2), encoding='utf-8')
    market = output / '.agents' / 'plugins' / 'marketplace.json'
    market.parent.mkdir(parents=True)
    market.write_text(json.dumps({'name': 'local-journal-dev', 'interface': {'displayName': '本机会话记录'},
        'plugins': [{'name': 'local-journal', 'source': {'source': 'local', 'path': './plugins/local-journal'},
                     'policy': {'installation': 'AVAILABLE', 'authentication': 'ON_INSTALL'}, 'category': 'Productivity'}]}, ensure_ascii=False, indent=2), encoding='utf-8')
    archive = output / 'local-journal.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(target.rglob('*')):
            if path.is_file():
                bundle.write(path, path.relative_to(target).as_posix())
    with zipfile.ZipFile(archive) as bundle:
        for name in ('plugin.json', '.codex-plugin/plugin.json', 'mcp.json'):
            json.loads(bundle.read(name))
        if bundle.testzip():
            raise ValueError('插件压缩包校验失败。')
    return archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    print(build(parser.parse_args().output))
