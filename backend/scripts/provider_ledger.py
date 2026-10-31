"""Persistent attempt reservations shared by all runs under one user authorization."""
from datetime import datetime,timezone
import json
from pathlib import Path
from contextlib import contextmanager
import hashlib


class ProviderLedger:
    def __init__(self,path: Path):
        self.path=path
        self.lock=path.with_suffix('.lock')
        path.parent.mkdir(parents=True,exist_ok=True)

    def reserve(self,kind):
        # Failed/unknown requests count, and concurrent writers fail closed.
        owned=False
        try:
            with self.lock.open('x',encoding='utf-8'):
                owned=True
                data=json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else dict(
                    authorization='2026-10-26 functional completion; public inputs only',limits={'model':120,'embedding':160},
                    reserved={'model':0,'embedding':0},attempts=[])
                bucket='embedding' if kind=='embedding' else 'model'
                if data['limits']!={'model':120,'embedding':160} or data['reserved'][bucket]>=data['limits'][bucket]:
                    raise RuntimeError('Authorized cumulative provider budget exhausted')
                data['reserved'][bucket]+=1
                data['attempts'].append(dict(kind=kind,at=datetime.now(timezone.utc).isoformat()))
                self.path.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
        finally:
            if owned:
                self.lock.unlink()


class RoundLedger:
    """An existing, explicitly granted holdout round; never creates a new grant on use."""

    LIMITS = {'model': 96, 'embedding': 73}
    PROTOCOL = 'holdout-provider-authorization-v1'

    @staticmethod
    def identity(data):
        value = {key: data[key] for key in ('protocol', 'authorization', 'scope', 'limits')}
        return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    @classmethod
    def create(cls, path, *, authorization, scope):
        path = Path(path)
        data = dict(protocol=cls.PROTOCOL, authorization=authorization, scope=scope,
                    limits=dict(cls.LIMITS), reserved={'model': 0, 'embedding': 0}, attempts=[], run_output=None)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x', encoding='utf-8') as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
        return cls(path, scope=scope)

    def __init__(self, path, *, scope):
        self.path = Path(path)
        self.lock = self.path.with_suffix('.lock')
        self.scope = scope
        self.fingerprint = self.identity(self.read())

    def read(self):
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if (data['protocol'] != self.PROTOCOL or data['limits'] != self.LIMITS
                or any(type(value) is not int for value in data['limits'].values())
                or data['scope'] != self.scope or not isinstance(data['authorization'], dict)
                or not all(isinstance(data['authorization'].get(key), str) and data['authorization'][key].strip()
                           for key in ('id', 'source', 'authorized_at'))):
            raise ValueError('Round authorization does not match the approved scope/limits')
        if hasattr(self, 'fingerprint') and self.identity(data) != self.fingerprint:
            raise ValueError('Round authorization changed')
        counts = {'model': 0, 'embedding': 0}
        for item in data['attempts']:
            counts[item['bucket']] += 1
        if set(data['reserved']) != set(counts) or any(
            type(data['reserved'][kind]) is not int or not 0 <= data['reserved'][kind] <= self.LIMITS[kind]
            or data['reserved'][kind] != counts[kind] for kind in counts
        ):
            raise ValueError('Round reservation history is inconsistent')
        return data

    @contextmanager
    def update(self):
        with self.lock.open('x', encoding='utf-8'):
            pass
        try:
            data = self.read()
            yield data
            temporary = self.path.with_suffix('.tmp')
            with temporary.open('x', encoding='utf-8') as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.write('\n')
                handle.flush()
                import os
                os.fsync(handle.fileno())
            temporary.replace(self.path)
        finally:
            self.lock.unlink()

    def claim_run(self, output):
        with self.update() as data:
            if data['run_output'] is not None or any(data['reserved'].values()):
                raise RuntimeError('Round already claimed; no retry/resume or new-output replay')
            data['run_output'] = str(Path(output).resolve())

    def reserve(self, kind):
        if kind not in {'answer', 'question', 'embedding'}:
            raise ValueError('This grant authorizes only single-step answers and embeddings')
        bucket = 'embedding' if kind == 'embedding' else 'model'
        with self.update() as data:
            if data['run_output'] is None or data['reserved'][bucket] >= self.LIMITS[bucket]:
                raise RuntimeError('Round not claimed or authorized budget exhausted')
            data['reserved'][bucket] += 1
            data['attempts'].append(dict(kind=kind, bucket=bucket, at=datetime.now(timezone.utc).isoformat()))
