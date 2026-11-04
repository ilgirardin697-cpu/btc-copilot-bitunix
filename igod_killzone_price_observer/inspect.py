"""Offline inspection of a journal/raw copy; never creates observations."""
import argparse
import json
from .clock import Clock
from .journal import Store
from .reports import derive


def main():
    p=argparse.ArgumentParser(description='Read existing observer evidence copy, no network or new records')
    p.add_argument('--evidence-copy',required=True)
    args=p.parse_args();rows=Store.inspect(args.evidence_copy)
    print(json.dumps(derive(rows,Clock().now_ms()),indent=2,allow_nan=False))


if __name__=='__main__':main()
