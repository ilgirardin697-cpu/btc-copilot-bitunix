"""Reproduce frozen selections into a NEW directory; originals are never written."""
import argparse
import json
from pathlib import Path
import shutil
from . import run
from .evaluate import main as evaluate


def reproduce(output_dir,verify_development=False):
    original=run.ART;out=Path(output_dir).resolve()
    if out.is_relative_to(original.resolve()) or original.resolve().is_relative_to(out):
        raise ValueError('REPRODUCTION_OUTPUT_MUST_BE_SEPARATE')
    if out.exists() and any(out.iterdir()): raise ValueError('OUTPUT_MUST_BE_NEW_OR_EMPTY')
    out.mkdir(parents=True,exist_ok=True)
    for name in ('preregistered.json','data_manifest.json','classic_lock.json','selection_lock.json'):
        shutil.copyfile(original/name,out/name)
    try:
        if verify_development:
            dev=out/'development';dev.mkdir()
            for name in ('preregistered.json','data_manifest.json'): shutil.copyfile(original/name,dev/name)
            run.ART=dev;run.develop()
            regenerated=json.loads((dev/'selection_lock.json').read_text())
            frozen=json.loads((original/'selection_lock.json').read_text())
            for family in ('classic','fusion'):
                for side in ('1','-1'):
                    for field in ('selected','eligible'):
                        if regenerated[family][side][field]!=frozen[family][side][field]:
                            raise ValueError('DEVELOPMENT_SELECTION_DIFFERED')
        run.ART=out;evaluate()
        actual=json.loads((out/'test_results.json').read_text())
        expected=json.loads((original/'test_results.json').read_text())
        if actual!=expected: raise ValueError('FROZEN_TEST_REPRODUCTION_DIFFERED')
        (out/'reproduction_verified.txt').write_text('Exact frozen TEST JSON reproduced; no original artifact changed.\n')
    finally: run.ART=original


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',required=True)
    parser.add_argument('--verify-development',action='store_true')
    args=parser.parse_args();reproduce(args.output_dir,args.verify_development)
