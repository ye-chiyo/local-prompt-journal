"""Controlled producer benchmark, NOT Codex/model round-trip latency.

Same atomic stimulus writes and hash workload with and without Collector. Metrics
are actual Windows counters. Process I/O includes pipes. Managed file size is a
disk footprint observation, never physical write attribution.

Enabled CPU includes the producer, Collector, protocol source and an observer
polling Journal.session() every 5ms. Disabled has no equivalent observer; the
CPU difference cannot be attributed to Collector alone.
"""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

from release_paths import external_output


def process_counters(pid):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.restype = wintypes.HANDLE
    handle = kernel.OpenProcess(0x0400 | 0x0010, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    class IO(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in ('readOperations', 'writeOperations', 'otherOperations', 'readTransferBytes', 'writeTransferBytes', 'otherTransferBytes')]
    class MEM(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + [(n, ctypes.c_size_t) for n in ('peakWorkingSet', 'workingSet', 'peakPagedPool', 'pagedPool', 'peakNonPagedPool', 'nonPagedPool', 'pagefile', 'peakPagefile')]
    try:
        io, mem = IO(), MEM()
        mem.cb = ctypes.sizeof(mem)
        created, exited, kernel_time, user_time = (wintypes.FILETIME() for _ in range(4))
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        kernel.GetProcessIoCounters.argtypes = [wintypes.HANDLE, ctypes.POINTER(IO)]
        if not kernel.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel_time), ctypes.byref(user_time)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel.GetProcessIoCounters(handle, ctypes.byref(io)):
            raise ctypes.WinError(ctypes.get_last_error())
        psapi = ctypes.WinDLL('psapi', use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(MEM), wintypes.DWORD]
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(mem), ctypes.sizeof(mem)):
            raise ctypes.WinError(ctypes.get_last_error())
        seconds = lambda f: ((f.dwHighDateTime << 32) | f.dwLowDateTime) / 10_000_000
        return {'cpuSeconds': seconds(kernel_time) + seconds(user_time), 'workingSetBytes': mem.workingSet,
                'peakWorkingSetBytes': mem.peakWorkingSet, **{n: getattr(io, n) for n, _ in IO._fields_}}
    finally:
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle(handle)


def worker(args):
    root = external_output(args.output, args.repo)
    sys.path.insert(0, str(Path(args.repo).resolve()))
    from release_facts import initial, message
    from prompt_journal import Journal, CodexHistory
    from prompt_journal.sync import Collector
    root.mkdir(parents=True, exist_ok=False)
    state_path = root / 'source.json'
    state = initial(root)
    # Performance workload intentionally has no attachment I/O.
    for s in state['sessions']:
        s['turns'][0]['items'] = [message('u-0', '受控回合基线')]
    def publish():
        temporary = state_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
        temporary.replace(state_path)
    publish()
    app = Journal(root / 'data')
    sources = []
    def factory():
        source = CodexHistory([sys.executable, str(Path(args.repo) / 'tests/fixtures/automatic_source.py'), str(state_path)])
        sources.append(source)
        return source
    collector = Collector(app, source_factory=factory, interval=0.1, enabled_at=190, page_size=100) if args.condition == 'enabled' else None
    if collector:
        collector.start()
        deadline = time.monotonic() + 10
        while len(app.sessions()) != 3 and time.monotonic() < deadline:
            time.sleep(0.01)
        if len(app.sessions()) != 3:
            raise RuntimeError('Initial automatic discovery did not finish')
    before = process_counters(os.getpid())
    source_before = {s.process.pid: process_counters(s.process.pid) for s in sources if s.process and s.process.poll() is None}
    managed_before = sum(p.stat().st_size for p in (root / 'data').rglob('*') if p.is_file())
    start = time.perf_counter()
    durations, latencies = [], []
    peak = before['workingSetBytes']
    for index in range(args.turns):
        begun = time.perf_counter()
        payload = ('受控生产回合-' + str(index)).encode()
        for _ in range(2500):
            payload = hashlib.sha256(payload).digest()
        state['sessions'][0]['turns'][0]['items'].append(message('u-' + str(index + 1), '受控新增中文-' + str(index)))
        publish()
        published = time.perf_counter()
        durations.append((published - begun) * 1000)
        if collector:
            deadline = begun + 0.2
            expected_id = 'u-' + str(index + 1)
            while app.session('A')['messages'][-1]['id'] != expected_id and time.monotonic() < deadline:
                time.sleep(0.005)
            if app.session('A')['messages'][-1]['id'] != expected_id:
                raise RuntimeError('Automatic save did not catch up')
            latencies.append((time.perf_counter() - published) * 1000)
        peak = max(peak, process_counters(os.getpid())['workingSetBytes'])
        # Identical 200ms stimulus cadence in both conditions.
        time.sleep(max(0, begun + 0.2 - time.perf_counter()))
    elapsed = time.perf_counter() - start
    after = process_counters(os.getpid())
    source_counters = []
    for source in sources:
        if source.process and source.process.poll() is None:
            pid = source.process.pid
            counter = process_counters(pid)
            baseline = source_before.get(pid, {})
            source_counters.append({'pid': pid, 'counters': counter, 'cpuDeltaSeconds': counter['cpuSeconds'] - baseline.get('cpuSeconds', 0), 'ioWriteTransferDeltaBytes': counter['writeTransferBytes'] - baseline.get('writeTransferBytes', 0), 'baselineKnown': bool(baseline)})
    if collector:
        collector.stop()
    result = {'condition': args.condition, 'turns': args.turns, 'sessions': 3, 'projects': 2,
              'elapsedSeconds': elapsed, 'stimulusCadenceMs': 200, 'producerTurnMs': durations, 'producerMedianMs': statistics.median(durations),
              'saveLatencyMs': latencies, 'saveMedianMs': statistics.median(latencies) if latencies else None,
              'journalCpuDeltaSeconds': after['cpuSeconds'] - before['cpuSeconds'], 'journalPeakObservedWorkingSetBytes': peak,
              'journalIoWriteTransferDeltaBytes': after['writeTransferBytes'] - before['writeTransferBytes'],
              'sourceProcessCounters': source_counters, 'managedFileBytesBefore': managed_before,
              'managedAllocatedLogicalFileBytes': sum(p.stat().st_size for p in (root / 'data').rglob('*') if p.is_file()),
              'scope': 'Synthetic producer workload; no model calls; not real Codex round-trip latency; process I/O includes pipes. Enabled CPU includes producer, Collector, protocol source and Journal.session() observer polling every 5ms; disabled has no equivalent observer. CPU difference is not attributable to Collector alone.'}
    result['managedLogicalFileGrowthBytes'] = result['managedAllocatedLogicalFileBytes'] - managed_before
    result['cpuProcessTreeDeltaSeconds'] = result['journalCpuDeltaSeconds'] + sum(s['cpuDeltaSeconds'] for s in source_counters)
    (root / 'report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument('--output', required=True)
    parser.add_argument('--turns', type=int, default=24)
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--condition', choices=('disabled', 'enabled'))
    args = parser.parse_args()
    try:
        output = external_output(args.output, args.repo)
    except ValueError as exc:
        parser.error(str(exc))
    args.repo = str(Path(args.repo).resolve())
    if args.condition:
        worker(args)
        return
    output.mkdir(parents=True, exist_ok=False)
    reports = []
    for repeat in range(args.repeats):
        for condition in (('disabled', 'enabled') if repeat % 2 == 0 else ('enabled', 'disabled')):
            destination = output / f'{repeat + 1}-{condition}'
            command = [sys.executable, __file__, '--repo', args.repo, '--output', str(destination), '--condition', condition, '--turns', str(args.turns)]
            completed = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', check=True)
            reports.append(json.loads(completed.stdout))
    (output / 'report.json').write_text(json.dumps({'reports': reports, 'userAccepted': False}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(str(output / 'report.json'))


if __name__ == '__main__':
    main()
