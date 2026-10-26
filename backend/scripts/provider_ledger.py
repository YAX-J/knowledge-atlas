"""Persistent attempt reservations shared by all runs under one user authorization."""
from datetime import datetime,timezone
import json
from pathlib import Path


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
