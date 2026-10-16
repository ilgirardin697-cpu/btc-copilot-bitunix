"""Separate observational persistence. No operational state is accepted."""
import json
import os
from pathlib import Path
import uuid


def append(path,row):
    with Path(path).open('a',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())


def atomic(path,row):
    path=Path(path);temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('w',encoding='utf-8',newline='\n') as stream:
            json.dump(row,stream,ensure_ascii=False,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
        try:
            fd=os.open(str(path.parent),os.O_RDONLY)
            try:os.fsync(fd)
            finally:os.close(fd)
        except OSError:pass  # directory fsync not available on every OS
    finally:
        if temporary.exists():temporary.unlink()
