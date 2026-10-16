"""Create public provenance receipts from the already acquired transcript cache.

No network calls, no additional paid requests, no full transcript publication.
"""
import hashlib
import json
from pathlib import Path

VIDEOS={
    'tDnUVybgL20':dict(user_date='2024',claims=[
        (870,'Zero line is part of the simplified Koncorde interpretation.'),
        (2507,'MA entering/leaving the mountain defines entry/exit in the explanation.'),
        (8947,'Quick exit/reentry can be interesting; no exact bar count is supplied.')]),
    'GtRimUXhMG4':dict(user_date='2026-09-07',claims=[
        (7559,'The creator names Awesome Oscillator.'),
        (8598,'Oscillator zero crossing and subsequent ADX turn are distinct observations.'),
        (8897,'An ADX turn can lag the oscillator; an impulse is not assumed before it turns.'),
        (26571,'A modified/adapted RSI is discussed, without a reproducible private formula.'),
        (30756,'Interpreting only a green or red bar is insufficient.')]),
    'H-oPU2snPJQ':dict(user_date='2026-10-06',claims=[
        (8708,'Oscillator reaching/breaking zero precedes the described ADX impulse.'),
        (9248,'Volatility is sought alongside the developing impulse, rather than assumed from color.')]),
    'chmnhyuJUic':dict(user_date='2026-10-14',claims=[
        (6213,'Oscillator zero is a meaningful reference in the commentary.'),
        (6581,'An isolated colored candle is not enough.'),
        (6979,'ADX turn is discussed in relation to the oscillator crossing zero.'),
        (9252,'Volatility starting to increase is relevant.'),
        (11571,'A volatility reference around 50 percent is explicitly mentioned.'),
        (11645,'Koncorde near zero is discussed as context.'),
        (12998,'An adapted hourly RSI is discussed, without revealing its formula.')])}


def receipt(cache=None):
    root=Path(__file__).resolve().parents[2]
    cache=Path(cache) if cache else root/'research/cache/bitman_phase4_sources'
    out={}
    for video,meta in VIDEOS.items():
        p=cache/(video+'.json');raw=p.read_bytes();r=json.loads(raw)
        text=r['transcription']
        out[video]=dict(url='https://www.youtube.com/watch?v='+video,
            user_attested_date=meta['user_date'],publication_metadata_independently_verified=False,
            provider='vidIQ public transcript',language=r['language'],characters=len(text),
            cache_file_sha256=hashlib.sha256(raw).hexdigest(),
            transcript_utf8_sha256=hashlib.sha256(text.encode()).hexdigest(),
            claims=[dict(character_offset=offset,paraphrase=claim) for offset,claim in meta['claims']],
            note='Character offsets, not video timestamps; no visual verification or full copyrighted transcript committed.')
    return dict(videos=out,authorization=dict(maximum_credits=20,transcript_calls=4,
        nominal_credits_per_call=5,nominal_total=20,actual_billed_credits=None,
        note='The tool did not return actual billed credits. No extra paid calls authorized or made.'),
        limitation='Primary public statements support qualitative hypotheses, not private indicator parity. '
            'The volatility indicator in the videos is not proven mathematically identical to our BBWP proxy.')


if __name__=='__main__':
    dest=Path(__file__).parent/'artifacts';dest.mkdir(exist_ok=True)
    (dest/'primary_sources.json').write_text(json.dumps(receipt(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
