"""Independent explicit assistant queue consumer: python -m app.assistant_runner [--once]."""
import argparse
import logging
import signal
import threading

from app.core.config import get_settings
from app.core.identity import DEVELOPMENT_USER_ID
from app.core.schema_version import schema_status
from app.db.session import SessionLocal
from app.services.assistant_execution import process_next


def serve(*,settings,stop,once=False,session_factory=SessionLocal):
    while not stop.is_set():
        try:
            with session_factory() as db:
                result=process_next(db,user_id=DEVELOPMENT_USER_ID,settings=settings)
        except Exception as exc:
            logging.error('assistant_iteration_failed error_type=%s',type(exc).__name__)
            if once:return 1
            stop.wait(2);continue
        if once:return 1 if result is not None and result.status=='failed' else 0
        if result is None:stop.wait(2)
    return 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once',action='store_true')
    args=parser.parse_args()
    with SessionLocal() as db:
        ready,_=schema_status(db)
        if not ready:logging.error('assistant_schema_not_ready');return 1
    stop=threading.Event()
    for kind in (signal.SIGINT,signal.SIGTERM):signal.signal(kind,lambda *_:stop.set())
    return serve(settings=get_settings(),stop=stop,once=args.once)


if __name__=='__main__':raise SystemExit(main())
