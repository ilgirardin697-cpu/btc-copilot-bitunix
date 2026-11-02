"""Render annotations for ONE actual capture. Refuses absent evidence."""
import argparse
import json
from pathlib import Path
from .render import save_comparison


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case',type=Path,required=True)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    case=json.loads(args.case.read_text(encoding='utf-8'))
    save_comparison(case,args.source,args.out)
    print('LOCAL_VISUAL_COMPARISON_ONLY; NO_SIGNAL; NO_CALIBRATED_PRICE_INFERRED')


if __name__=='__main__':main()
