"""Frozen ladder input contract shared by the private grading and calibration tools."""
from dataclasses import dataclass
from hashlib import sha256
from itertools import product
import json
import math
from pathlib import Path, PurePosixPath
import re


@dataclass(frozen=True)
class Member:
    code: str
    source: Path
    source_hash: str
    language: str
    elo: float
    slots: tuple[int, ...]


@dataclass(frozen=True)
class Ladder:
    version: str
    levels: tuple[tuple[Member, ...], ...]
    seeds: tuple[int, int]
    grading: tuple[dict, ...]
    calibration: dict

    @property
    def members(self) -> tuple[Member, ...]:
        return tuple(m for level in self.levels for m in level)


def private_path(root: Path, path: Path, *, exists: bool = True) -> Path:
    absolute = path.absolute()
    if any(p.is_symlink() for p in (absolute,*absolute.parents)):
        raise ValueError('private release paths must not traverse links')
    safe = absolute.resolve(strict=exists)
    if not safe.is_relative_to(root.resolve()) or safe == root.resolve():
        raise ValueError('expected a path below this workspace private directory')
    return safe


def source_path(root: Path, name: str) -> Path:
    rel = PurePosixPath(name)
    if rel.is_absolute() or '..' in rel.parts or '\\' in name or rel.as_posix()!=name or not rel.parts:
        raise ValueError('noncanonical relative ladder source')
    return private_path(root,root/rel)


def is_digest(value):
    return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None


def source_digest(path):
    if path.is_symlink() or not path.is_dir():
        raise ValueError('expected an unlinked ladder source directory')
    entries = []
    for f in sorted(path.rglob('*')):
        if f.is_symlink() or not (f.is_dir() or f.is_file()):
            raise ValueError('linked or special ladder source')
        if f.is_file() and '__pycache__' not in f.relative_to(path).parts:
            entries.append([f.relative_to(path).as_posix(),sha256(f.read_bytes()).hexdigest()])
    if not entries:
        raise ValueError('empty ladder source')
    return sha256(json.dumps(entries,ensure_ascii=True,separators=(',',':')).encode()).hexdigest()


def map_records(records, count):
    if (not isinstance(records,list) or len(records)!=count or any(
        not isinstance(m,dict) or not isinstance(m.get('name'),str)
        or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*\.map',m['name']) is None
        or not is_digest(m.get('sha256')) for m in records
    ) or len({m['sha256'] for m in records})!=count or len({m['name'] for m in records})!=count):
        raise ValueError(f'expected {count} fixed, distinct maps')
    return tuple(records)


def checked_maps(root: Path, directory: Path, records):
    directory = private_path(root,directory)
    paths = tuple(private_path(root,directory/m['name']) for m in records)
    if any(sha256(path.read_bytes()).hexdigest()!=row['sha256'] for path,row in zip(paths,records,strict=True)):
        raise ValueError('map bytes do not match the ladder')
    return paths


def load_ladder(path: Path, root: Path) -> Ladder:
    blob = json.loads(private_path(root,path).read_bytes())
    version = blob['ladderVersion']
    if (blob.get('schemaVersion')!=1 or not isinstance(version,str)
        or re.fullmatch(r'1\.0\.\d+',version) is None or blob.get('ruleset')!='standard-1'):
        raise ValueError('unsupported ladder schema, version or ruleset')
    grading = map_records(blob['grading'],24)
    cal = blob['calibration']
    map_records(cal['maps'],12)
    if set(m['sha256'] for m in grading)&set(m['sha256'] for m in cal['maps']):
        raise ValueError('grading and calibration maps overlap')
    levels = []
    for i,level in enumerate(blob['levels']):
        if level['level']!=f'L{i}' or len(level['members']) not in (2,3):
            raise ValueError('invalid ladder tier')
        members = []
        seen_slots = set()
        for row in level['members']:
            code,language,slots = row['code'], row['language'], tuple(row['gradingSlots'])
            elo = row['elo']
            source = source_path(root,row['source'])
            if (re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}',code) is None
                or not is_digest(row['sourceSha256']) or language not in ('cpp','python')
                or type(elo) not in (float,int) or not math.isfinite(elo) or len(slots)!=7
                or any(type(n) is not int or not 0<=n<24 for n in slots)
                or len(set(slots))!=7 or seen_slots.intersection(slots)):
                raise ValueError('invalid ladder member or scoring slots')
            if source_digest(source)!=row['sourceSha256']:
                raise ValueError('ladder member bytes differ from the recorded digest')
            is_python=(source/'main.py').is_file()
            if is_python!=(language=='python') or is_python==bool(list(source.glob('*.cpp'))):
                raise ValueError('ladder member entry point does not match its language')
            members.append(Member(code,source,row['sourceSha256'],language,float(elo),slots))
            seen_slots.update(slots)
        levels.append(tuple(members))
    count = sum(map(len,levels))
    codes = {m.code for t in levels for m in t}
    if (len(levels),count) not in ((12,26),(13,28)) or len(codes)!=count or sum(
        m.code=='M-balanced' and m.elo==0 for t in levels for m in t)!=1:
        raise ValueError('invalid ladder size, duplicate code or missing fixed anchor')
    expected = {tuple(sorted((a.code,b.code))) for left,right in zip(levels,levels[1:]) for a,b in product(left,right)}
    got = [tuple(sorted(pair)) for pair in cal['pairings']]
    gaps=cal['gaps']
    if (len(got)!=len(expected) or set(got)!=expected or len(gaps)!=len(levels)-1
        or any(type(x) not in (float,int) or not math.isfinite(x) for x in gaps)):
        raise ValueError('invalid adjacent calibration plan')
    if blob['seeds']!=[17,29]:
        raise ValueError('unexpected scoring seed identities')
    return Ladder(version,tuple(levels),(17,29),grading,cal)
