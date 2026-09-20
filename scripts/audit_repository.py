"""Audit exactly the staged Git blobs before sharing; never print secret values.

This is a conservative release hygiene check, not a guarantee that every kind
of confidential information is detectable. It rejects common credentials,
model weights, local environments, accidental symlinks and oversized objects.
"""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
PATTERNS={
    'Hugging Face credential': rb'hf_[A-Za-z0-9]{25,}',
    'GitHub credential': rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})',
    'OpenAI-style credential': rb'sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{35,}',
    'AWS access identifier': rb'AKIA[A-Z0-9]{16}',
    'Private key': rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
}


def forbidden_path(path):
    p=PurePosixPath(path)
    if any(part in {'.cache','.python','__pycache__','models'} or part.startswith('.venv') for part in p.parts):
        return True
    return (p.name.startswith('._') or p.name=='.env' or p.name.startswith('.env.') or
            p.name.endswith('.local.json') or p.suffix in {'.pt','.pth','.ckpt','.safetensors','.pem','.key'} or
            p.name in {'uma-s-1p1-cpu-local.json','uma-s-1p1-a100.json'})


def main():
    records=subprocess.check_output(['git','ls-files','--stage','-z'],cwd=ROOT).split(b'\0')
    issues=[];total=0;files=0;largest=[]
    with subprocess.Popen(['git','cat-file','--batch'],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE) as git:
        for record in filter(None,records):
            fields,name=record.split(b'\t',1);mode,oid,stage=fields.split()
            path=name.decode('utf-8');files+=1
            if mode==b'120000' or stage!=b'0' or forbidden_path(path):
                issues.append({'path':path,'problem':'Excluded path, symlink or unmerged entry'})
            git.stdin.write(oid+b'\n');git.stdin.flush()
            header=git.stdout.readline().split();size=int(header[2])
            body=git.stdout.read(size);git.stdout.read(1)
            total+=size;largest.append((size,path))
            if size>50*1024*1024:
                issues.append({'path':path,'problem':'File exceeds 50 MiB release budget'})
            if b'\0' not in body:
                for label,pattern in PATTERNS.items():
                    if re.search(pattern,body):
                        issues.append({'path':path,'problem':label+' pattern; inspect locally'})
        git.stdin.close();git.wait()
    report={'status':'passed' if files and not issues else 'needs_review','files':files,
            'bytes':total,'largest_files':[{'bytes':n,'path':p} for n,p in sorted(largest,reverse=True)[:5]],
            'issues':issues,'scope':'Common credential/path/size checks on staged blobs; not an exhaustive security audit.'}
    print(json.dumps(report,indent=2))
    return 0 if report['status']=='passed' else 1


if __name__=='__main__':
    raise SystemExit(main())
