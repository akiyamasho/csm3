#!/usr/bin/env python3
"""Extract original inline NAME controls from the selected PSI3 ROM scripts.

The output contains token metadata and source anchors only; it never copies ROM
bytes or Japanese text. Run with --rom, --manifest, and --output.
"""
import argparse
import hashlib
import json
import re
import struct
import sys
import difflib
from collections import Counter
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_ROM_SHA1 = '3f5253fcf57e07ce52472bd29a61d16b98a12376'
ROOT = DEFAULT_ROOT
OPCODES = ROOT / 'translation_patch/script_inserter/opcodes.cpp'

def opcode_args():
    text=OPCODES.read_text(encoding='utf-8')
    start=text.index('const Opcode optable[5][0x100]{')
    end=text.index('\n};',start)
    body=text[start:end]
    headings=list(re.finditer(r'^\s*// 0x([0-9a-fA-F]{4})\s*$',body,re.M))
    opmap={}; aliasmap={}
    for i,h in enumerate(headings):
        stop=headings[i+1].start() if i+1<len(headings) else len(body)
        segment=body[h.end():stop]; code=int(h.group(1),16)
        entries=re.finditer(r'UNUSED|OP\(\s*"([^"]*)"(?:\s*,\s*"([^"]*)")?',segment)
        for j,m in enumerate(entries):
            if m.group(0)=='UNUSED': continue
            opmap[code+j]=m.group(1)
            if m.group(2): aliasmap[m.group(2)]=code+j
    return opmap,aliasmap

OPS,ALIASES=opcode_args()

def lz(data, start):
    if data[start] != 0x10:
        raise ValueError('not GBA LZ77')
    n = data[start+1] | data[start+2] << 8 | data[start+3] << 16
    out = bytearray(); i = start + 4
    while len(out) < n:
        flags = data[i]; i += 1
        for bit in range(7, -1, -1):
            if len(out) >= n: break
            if flags & (1 << bit):
                a, b = data[i], data[i+1]; i += 2
                length = (a >> 4) + 3; distance = ((a & 15) << 8 | b) + 1
                if distance > len(out): raise ValueError('invalid LZ distance')
                for _ in range(length): out.append(out[-distance])
            else:
                out.append(data[i]); i += 1
    return bytes(out)

def source_dialog_count(path):
    return sum(1 for line in path.read_text(encoding='utf-8').splitlines()
               if re.match(r'^\s*dialogtxt\s+', line))

def current_name_indices(value):
    greek='βγδεζηθικλμνξοπρ'
    pattern=re.compile(r'\[NAME\s*(\d+)\]|(['+greek+'])')
    return [int(m.group(1)) if m.group(1) is not None else greek.index(m.group(2))
            for m in pattern.finditer(value)]

def anchor_keys(events, kind):
    command_codes=[e['code'] for e in events if e['kind']=='command']
    cmd_index=-1; keys=[]
    for e in events:
        if e['kind']=='command':
            cmd_index+=1
            if kind=='command':
                prev=tuple(command_codes[max(0,cmd_index-2):cmd_index])
                nxt=tuple(command_codes[cmd_index+1:cmd_index+3])
                keys.append(((e['code'],),prev,nxt))
        elif e['kind']==kind:
            prev=tuple(command_codes[:cmd_index][-2:])
            nxt=tuple(command_codes[cmd_index:cmd_index+2])
            keys.append((prev,nxt))
    return keys

def safe_event_map(original_events, source_events, kind):
    oi=[i for i,e in enumerate(original_events) if e['kind']==kind]
    si=[i for i,e in enumerate(source_events) if e['kind']==kind]
    signature=lambda es:[(e['kind'],e.get('code'),e.get('label_id')) for e in es]
    if signature(original_events)==signature(source_events):
        return {n:[n] for n in range(min(len(oi),len(si)))}, 'exact_sequence'
    if kind=='dialog_block':
        olabs={e['label_id']:i for i,e in enumerate(original_events) if e['kind']=='label'}
        slabs={e['label_id']:i for i,e in enumerate(source_events) if e['kind']=='label'}
        common=[k for k in olabs if k in slabs]
        bounds=[(None,-1,-1)]+[(k,olabs[k],slabs[k]) for k in common]+[(None,len(original_events),len(source_events))]
        omap={}
        for (_,oi0,si0),(_,oi1,si1) in zip(bounds,bounds[1:]):
            def runs(es):
                out=[]; pending=[]
                for e in es:
                    if e['kind']=='label' or (e['kind']=='command' and e.get('code')==0x0309): continue
                    if e['kind']=='dialog_block': pending.append(e['index']); continue
                    if pending: out.append((('D',),pending)); pending=[]
                    out.append((('C',e.get('code')),[e.get('code')]))
                if pending: out.append((('D',),pending))
                return out
            oruns=runs(original_events[oi0+1:oi1]); sruns=runs(source_events[si0+1:si1])
            oa=[x[0] for x in oruns]; sa=[x[0] for x in sruns]
            if oa==sa:
                for (sig,ob),(ssig,sb) in zip(oruns,sruns):
                    if sig==('D',):
                        for a in ob: omap[a]=sb
            else:
                matcher=difflib.SequenceMatcher(a=oa,b=sa,autojunk=False)
                for a0,b0,size in matcher.get_matching_blocks():
                    chunk=oa[a0:a0+size]
                    if not any(x==('D',) for x in chunk) or not any(x[0]=='C' for x in chunk): continue
                    for n in range(size):
                        if oa[a0+n]==('D',):
                            for a in oruns[a0+n][1]: omap[a]=sruns[b0+n][1]
        if omap: return omap,'matched_source_label_regions'
    ok=anchor_keys(original_events,kind); sk=anchor_keys(source_events,kind)
    oc=Counter(ok); sc=Counter(sk); sm={k:i for i,k in enumerate(sk) if sc[k]==1}
    mapping={i:[sm[k]] for i,k in enumerate(ok) if oc[k]==1 and k in sm}
    return mapping, 'unique_neighboring_command_anchors'

def source_dialog_rows(path):
    events=[]; dialog_blocks=[]; current=[]; greek='βγδεζηθικλμνξοπρ'
    def close_dialog():
        nonlocal current
        if current:
            idx=len(dialog_blocks); dialog_blocks.append(current)
            events.append({'kind':'dialog_block','index':idx}); current=[]
    for no,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
        stripped=line.strip()
        if not stripped or stripped.startswith(('//','#',';')): continue
        lm=re.fullmatch(r'@[A-Za-z]+_([0-9a-fA-F]+):',stripped)
        if lm:
            close_dialog(); label_id=lm.group(1).lower()
            events.append({'kind':'label','label_id':label_id,'offset':int(label_id,16)+16,'source_line':no})
            continue
        if stripped.startswith('@'): continue
        m=re.match(r'([A-Za-z_][A-Za-z0-9_]*)\b(.*)$',stripped)
        if not m: continue
        name,tail=m.group(1),m.group(2)
        code=int(name[4:],16) if re.fullmatch(r'code[0-9a-fA-F]{4}',name) else ALIASES.get(name)
        if code is None: continue
        strings=[]
        operand_match=re.match(r'\s*((?:-?\d+\s*,\s*)+-?\d+)',tail)
        operands=[int(v.strip()) for v in operand_match.group(1).split(',')] if operand_match else []
        for q in re.finditer(r'"((?:\\.|[^"\\])*)"',tail):
            strings.append(q.group(1).replace('\\"','"').replace('\\\\','\\'))
        if code==0x0308:
            current.append({'source_line':no,'current_text':strings[0] if strings else '',
                            'current_name_tokens':[f'{{NAME_{x}}}' for x in current_name_indices(strings[0] if strings else '')]})
        else:
            close_dialog()
            events.append({'kind':'command','code':code,'source_line':no,'strings':strings,'operands':operands,
                           'source_name_tokens':[[f'{{NAME_{x}}}' for x in current_name_indices(s)] for s in strings]})
    close_dialog()
    return events,dialog_blocks

def decode_payload(raw):
    parts=[]; tokens=[]; buf=bytearray(); i=0
    while i < len(raw):
        if i+1 < len(raw) and raw[i] == 0x83 and 0xc0 <= raw[i+1] <= 0xcf:
            if buf:
                parts.append(buf.decode('cp932', errors='replace')); buf.clear()
            value=raw[i+1]-0xc0
            marker=f'{{NAME_{value}}}'
            parts.append(marker); tokens.append({'token':marker, 'raw_hex':raw[i:i+2].hex()})
            i += 2
        else:
            buf.append(raw[i]); i += 1
    if buf: parts.append(buf.decode('cp932', errors='replace'))
    return ''.join(parts), tokens

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom',type=Path,required=True,help='user-provided original baserom.gba')
    parser.add_argument('--manifest',type=Path,help='default: <root>/translation_patch/build_scripts.manifest')
    parser.add_argument('--root',type=Path,default=DEFAULT_ROOT,help='repository root (default: inferred from this script)')
    parser.add_argument('--output',type=Path,required=True,help='write the compact token-only JSON manifest here')
    cli=parser.parse_args(argv)
    global ROOT, OPCODES, OPS, ALIASES
    ROOT=cli.root.resolve()
    OPCODES=ROOT/'translation_patch/script_inserter/opcodes.cpp'
    manifest=(cli.manifest or ROOT/'translation_patch/build_scripts.manifest').resolve()
    try:
        OPS,ALIASES=opcode_args()
        rom=cli.rom.read_bytes()
    except OSError as exc:
        print(f'error: {exc}',file=sys.stderr); return 1
    except (ValueError,IndexError) as exc:
        print(f'error: cannot read opcode metadata: {exc}',file=sys.stderr); return 1
    sha=hashlib.sha1(rom).hexdigest()
    if sha!=EXPECTED_ROM_SHA1:
        print(f'error: original ROM SHA-1 mismatch: expected {EXPECTED_ROM_SHA1}, got {sha}',file=sys.stderr)
        return 1
    rows=[]
    try:
        for line in manifest.read_text(encoding='utf-8').splitlines():
            m=re.fullmatch(r'(.+?)\s+--pos=([0-9a-fA-F]+)', line)
            if not m: raise ValueError('bad manifest line: '+line)
            rows.append((m.group(2).lower(),m.group(1)))
    except (OSError,ValueError) as exc:
        print(f'error: {exc}',file=sys.stderr); return 1
    if len(rows)!=1052 or len({a for a,_ in rows})!=1052:
        print(f'error: manifest must contain 1,052 unique script addresses; found {len(rows)} entries',file=sys.stderr)
        return 1
    records={}
    for address, rel in rows:
        path=ROOT/'translation_patch'/rel
        try:
            source_count=source_dialog_count(path)
        except OSError as exc:
            print(f'error: selected manifest source is missing: {path}: {exc}',file=sys.stderr)
            return 1
        source_events,source_blocks=source_dialog_rows(path)
        off=int(address,16)
        try:
            raw=lz(rom,off)
            if raw[:4] != b'PSI3': raise ValueError('decompressed data lacks PSI3 header')
            declared=struct.unpack_from('<I',raw,4)[0]
            if declared != len(raw): raise ValueError(f'PSI3 size field {declared} != actual {len(raw)}')
            payloads=[]; p=16; commands=0; parse_stop=None; original_events=[]; current_dialog=[]; runtime_strings=[]
            source_label_offsets={e['offset']:e['label_id'] for e in source_events if e['kind']=='label'}
            def close_original_dialog():
                nonlocal_dummy=None
                if current_dialog:
                    original_events.append({'kind':'dialog_block','index':sum(1 for e in original_events if e['kind']=='dialog_block'),
                                            'start_offset':current_dialog[0]['command_offset'],
                                            'payload_ordinals':[d['ordinal'] for d in current_dialog]})
                    current_dialog.clear()
            while p+2 <= len(raw):
                cmdpos=p
                if cmdpos in source_label_offsets:
                    close_original_dialog()
                    original_events.append({'kind':'label','label_id':source_label_offsets[cmdpos],'offset':cmdpos})
                code=raw[p]|raw[p+1]<<8; p+=2; args=OPS.get(code); this_strings=[]; this_expressions=[]
                if code not in OPS:
                    parse_stop=f'unknown opcode 0x{code:04x} at {cmdpos}'; break
                commands+=1
                for arg in args:
                    if arg in 'hl': p+=2
                    elif arg=='e':
                        expression=[]
                        while True:
                            if p+2>len(raw): raise ValueError(f'truncated expression at {cmdpos}')
                            word=raw[p]|raw[p+1]<<8; p+=2; expression.append(word)
                            if word==0: break
                            if word in (1,2,3,4):
                                extra=4 if word==4 else 2
                                if p+extra>len(raw): raise ValueError(f'truncated expression operand at {cmdpos}')
                                expression.extend([raw[p]|raw[p+1]<<8] if extra==2 else [raw[p]|raw[p+1]<<8,raw[p+2]|raw[p+3]<<8]); p+=extra
                            elif word & 0x0200: break
                        this_expressions.append(expression)
                    elif arg=='s':
                        end=raw.find(b'\0',p)
                        if end<0: raise ValueError(f'unterminated string at {cmdpos}')
                        data=raw[p:end]
                        text,tokens=decode_payload(data)
                        string_rec={'text':text,'control_tokens':tokens,'raw_hex':data.hex(),
                                    'command_offset':cmdpos,'decompressed_offset':p,
                                    'argument_index':len(this_strings)}
                        this_strings.append(string_rec)
                        p=(end+2)&~1
                    else:
                        parse_stop=f'unsupported opcode arg {arg!r} at {cmdpos}'; break
                if parse_stop: break
                if p>len(raw): raise ValueError(f'command overrun at {cmdpos}')
                if code==0x0308:
                    d=this_strings[0]
                    d.update({'ordinal':len(payloads),'block_index':sum(1 for e in original_events if e['kind']=='dialog_block')})
                    payloads.append(d); current_dialog.append(d)
                else:
                    close_original_dialog()
                    original_events.append({'kind':'command','code':code,'command_offset':cmdpos,
                                            'expression_signatures':this_expressions})
                    for sr in this_strings:
                        sr.update({'ordinal':len(runtime_strings),'code':code})
                        if this_expressions: sr['expression_signatures']=this_expressions
                        runtime_strings.append(sr)
                
                if code in (0x0003,0x0004,0x0008,0x030e,0x0315):
                    # Terminators end a code path, not necessarily the file; continue linear decoding.
                    pass
            close_original_dialog()
            count=len(payloads)
            match=count==source_count
            structure_match=(parse_stop is None and [(e['kind'],e.get('code'),e.get('label_id')) for e in original_events]==[(e['kind'],e.get('code'),e.get('label_id')) for e in source_events])
            block_map,map_method=safe_event_map(original_events,source_events,'dialog_block')
            block_events=[e for e in original_events if e['kind']=='dialog_block']
            # Reviewed branch collapses: the original has separate gender-dependent
            # dialogue paths, while HEAD routes both paths through one shared block.
            # Keep these explicitly distinct from wrapping/reflow components.
            reviewed_alternatives={
                '172d7ec':[(0,1,0),(2,3,1)],
                '188bfec':[(4,5,4)],
                '17d027c':[(0,1,0),(2,3,1)],
            }
            alternative_groups=[]
            reviewed_common_prefix={'1732aec':(103,[104,105],77)}
            if address in reviewed_common_prefix:
                common,variants,source_idx=reviewed_common_prefix[address]
                if block_map.get(common)!=[source_idx] or any(i in block_map for i in variants):
                    raise ValueError(f'reviewed common-prefix anchor changed at {address}')
                sequences=[]
                for variant in variants:
                    block_map[variant]=[source_idx]
                    seq=[t['token'] for n in block_events[common]['payload_ordinals']+block_events[variant]['payload_ordinals']
                         for t in payloads[n]['control_tokens']]
                    sequences.append(seq)
                current_tokens=[t for line in source_blocks[source_idx] for t in line['current_name_tokens']]
                alternative_groups.append({'original_block_indices':[common]+variants,'source_block_indices':[source_idx],
                    'mapping_kind':'alternative_branch_with_common_prefix','verified':True,
                    'evidence':'reviewed shared current block contains one common sentence and one gender-variant sentence',
                    'original_path_block_indices':[[common,v] for v in variants],
                    'original_alternative_tokens':sequences,'current_tokens':current_tokens,
                    'classification':'same_tokens' if all(seq==current_tokens for seq in sequences) else 'token_mismatch'})
            if address in reviewed_alternatives:
                grouped={}
                for verified_idx,alternate_idx,source_idx in reviewed_alternatives[address]:
                    # Only extend where the anchored decoder already established one
                    # side of the pair; fail closed if script structure has changed.
                    if block_map.get(verified_idx)!=[source_idx] or alternate_idx in block_map:
                        raise ValueError(f'reviewed alternative anchor changed at {address}:{alternate_idx}')
                    block_map[alternate_idx]=[source_idx]
                    grouped.setdefault(source_idx,[]).extend([verified_idx,alternate_idx])
                for source_idx,ois in grouped.items():
                    ois=sorted(set(ois)); sequences=[]
                    for oi in ois:
                        sequences.append([t['token'] for n in block_events[oi]['payload_ordinals'] for t in payloads[n]['control_tokens']])
                    current_tokens=[t for line in source_blocks[source_idx] for t in line['current_name_tokens']]
                    alternative_groups.append({'original_block_indices':ois,'source_block_indices':[source_idx],
                        'mapping_kind':'alternative_branch','verified':True,'evidence':'reviewed shared-target gender branch',
                        'original_alternative_tokens':sequences,'current_tokens':current_tokens,
                        'classification':'same_tokens' if all(seq==current_tokens for seq in sequences) else 'token_mismatch'})
            # Coordinator-reviewed current blocks whose source boundary shifted due
            # to shared gender prefixes or line wrapping. Guard the previous map so
            # this remains tied to the inspected source/ROM layout.
            reviewed_groups={
                '17bd14c':[
                    {'paths':[([28],[27,28]),([29],[27,29])],'kind':'alternative_branch_with_shared_prefix','evidence':'same 13f2 / 2e62 gender branch; each current path shares its opening dialog block'},
                    {'paths':[([87],[82,83]),([88],[82,84])],'kind':'alternative_branch_with_shared_prefix','evidence':'same 2e62 gender branch; shared encouragement precedes man/woman variant'},
                ],
                '17be5ec':[
                    {'paths':[([7],[7,8]),([8],[7,9])],'kind':'alternative_branch_with_shared_prefix','evidence':'root material-gift dialogue; shared announcement precedes gender-specific response'},
                ],
                '17c0b6c':[
                    {'paths':[([17],[15,16])],'kind':'reviewed_semantic_reflow','evidence':'0708 region; three Japanese sentences span current blocks 15 and 16'},
                ],
                '17c920c':[
                    {'paths':[([87],[81,82])],'kind':'reviewed_semantic_reflow','evidence':'213e region; three Japanese sentences span current blocks 81 and 82'},
                ],
                '17cc5bc':[
                    {'paths':[([11],[11,12])],'kind':'reviewed_semantic_reflow','evidence':'root region; Japanese three-sentence block spans current blocks 11 and 12'},
                    {'paths':[([12],[13])],'kind':'reviewed_content_match','evidence':'root region; Japanese Rob-side sentence directly matches current block 13'},
                ],
            }
            reviewed_groups_for_record=[]
            if address in reviewed_groups:
                for definition in reviewed_groups[address]:
                    paths=definition['paths']
                    expected_old={
                        '17bd14c':{28:[28],29:[29],87:[83],88:[84]},
                        '17be5ec':{7:[8],8:[9]},'17c0b6c':{17:[15]},
                        '17c920c':{87:[82]},'17cc5bc':{11:[11],12:[12]},
                    }[address]
                    for orig_path,source_path in paths:
                        for oi in orig_path:
                            if block_map.get(oi)!=expected_old[oi]:
                                raise ValueError(f'reviewed source anchor changed at {address}:O{oi}')
                        for oi in orig_path:
                            block_map.pop(oi)
                    for orig_path,source_path in paths:
                        for oi in orig_path:
                            block_map[oi]=source_path
                    original_paths=[]; current_paths=[]
                    for orig_path,source_path in paths:
                        original_paths.append([t['token'] for oi in orig_path for n in block_events[oi]['payload_ordinals'] for t in payloads[n]['control_tokens']])
                        current_paths.append([t for si in source_path for line in source_blocks[si] for t in line['current_name_tokens']])
                    original_indices=sorted({oi for op,_ in paths for oi in op})
                    source_indices=sorted({si for _,sp in paths for si in sp})
                    if len(paths)>1:
                        group={'original_block_indices':original_indices,'source_block_indices':source_indices,
                            'mapping_kind':definition['kind'],'verified':True,'evidence':definition['evidence'],
                            'original_path_block_indices':[op for op,_ in paths],
                            'current_path_block_indices':[sp for _,sp in paths],
                            'original_alternative_tokens':original_paths,'current_alternative_tokens':current_paths,
                            'classification':'same_tokens' if original_paths==current_paths else 'token_mismatch'}
                    else:
                        group={'original_block_indices':original_indices,'source_block_indices':source_indices,
                            'mapping_kind':definition['kind'],'verified':True,'evidence':definition['evidence'],
                            'original_tokens':original_paths[0],'current_tokens':current_paths[0],
                            'classification':'same_tokens' if original_paths[0]==current_paths[0] else 'token_mismatch'}
                    reviewed_groups_for_record.append(group)
                alternative_groups.extend(reviewed_groups_for_record)
            command_map,_=safe_event_map(original_events,source_events,'command')
            original_block_keys=anchor_keys(original_events,'dialog_block')
            source_block_keys=anchor_keys(source_events,'dialog_block')
            source_block_alignments=[]
            for bi,be in enumerate(block_events):
                sj=block_map.get(bi)
                source_block_alignments.append({'original_block_index':bi,'source_block_indices':sj,
                                                'verified':sj is not None})
            # Mapping can be many-to-many when a version changes dialogue wrapping.
            # Build connected components of the proven alignment graph, then compare
            # the aggregate token stream once per component (never once per edge).
            # A one-current-block component fed by multiple original blocks is marked
            # as an alternative candidate; branch intent still needs explicit proof.
            comparison_groups=list(alternative_groups)
            alternative_originals={oi for group in alternative_groups for oi in group['original_block_indices']}
            pending_original=set(block_map)-alternative_originals
            while pending_original:
                seed=min(pending_original); original_group={seed}; source_group=set(block_map[seed])
                changed=True
                while changed:
                    changed=False
                    for oi in list(pending_original-original_group):
                        if source_group.intersection(block_map[oi]):
                            original_group.add(oi); source_group.update(block_map[oi]); changed=True
                pending_original-=original_group
                ordered_original=sorted(original_group); ordered_source=sorted(source_group)
                original_tokens=[t['token'] for oi in ordered_original
                    for n in block_events[oi]['payload_ordinals'] for t in payloads[n]['control_tokens']]
                current_tokens=[t for si in ordered_source for line in source_blocks[si]
                    for t in line['current_name_tokens']]
                if len(ordered_original)>1 and len(ordered_source)==1:
                    mapping_kind='alternative_branch_candidate'
                elif len(ordered_original)>1 or len(ordered_source)>1:
                    mapping_kind='anchored_many_to_many'
                else:
                    mapping_kind='one_to_one'
                comparison_groups.append({'original_block_indices':ordered_original,
                    'source_block_indices':ordered_source,'mapping_kind':mapping_kind,
                    'verified':True,'original_tokens':original_tokens,'current_tokens':current_tokens,
                    'classification':('same_tokens' if original_tokens==current_tokens else 'token_mismatch')
                        if original_tokens else ('false_head_name_artifact' if current_tokens else 'no_name_token')})
            mapped_blocks=sum(x['verified'] for x in source_block_alignments)
            if structure_match: alignment='verified_full_structure'
            elif mapped_blocks: alignment='verified_anchored_blocks'
            else: alignment='structure_mismatch'
            records[address]={
                'manifest_path':rel,'rom_offset':f'0x{off:x}',
                'original_decompressed_size':len(raw),
                'decoded_command_count':commands,
                'decoder_stop':parse_stop,
                'source_dialogtxt_count':source_count,
                'original_dialogtxt_count':count,
                'alignment':alignment,
                'alignment_method':'complete event sequence matched' if structure_match else 'unique neighboring non-dialog opcode anchors; ambiguous/unmatched blocks excluded',
                'source_structure_match':structure_match,
                'source_labels':[{'label_id':e['label_id'],'offset':e['offset'],'source_line':e['source_line']} for e in source_events if e['kind']=='label'],
                'original_labels':[{'label_id':e['label_id'],'offset':e['offset']} for e in original_events if e['kind']=='label'],
                'block_anchor_method':map_method,'verified_block_count':mapped_blocks,
                'unmatched_block_count':len(block_events)-mapped_blocks,
                'original_event_count':len(original_events),'source_event_count':len(source_events),
                'original_non_dialog_strings':runtime_strings,
                'dialogtxt':payloads,
                'original_blocks':[{'block_index':e['index'],'payload_ordinals':e['payload_ordinals'],
                                    'source_block_indices':block_map.get(i),'verified':i in block_map,
                                    'anchor_signature':{'previous_opcodes':list(original_block_keys[i][0]),
                                                        'next_opcodes':list(original_block_keys[i][1])}}
                                   for i,e in enumerate(block_events)],
                'block_alignment':source_block_alignments,
                'comparison_groups':comparison_groups,
                'source_blocks':[{'block_index':i,'anchor_signature':{'previous_opcodes':list(source_block_keys[i][0]),
                                                                       'next_opcodes':list(source_block_keys[i][1])},
                                  'lines':[{'source_line':d['source_line'],'current_text':d['current_text'],
                                            'current_name_tokens':d['current_name_tokens']} for d in b]}
                                 for i,b in enumerate(source_blocks)]
            }
            if block_map:
                for oi,sj in block_map.items():
                    ob=block_events[oi]; source_runs=[source_blocks[x] for x in sj]
                    originals=[payloads[o] for o in ob['payload_ordinals']]
                    original_tokens=[t['token'] for d in originals for t in d['control_tokens']]
                    current_tokens=[t for sb in source_runs for d in sb for t in d['current_name_tokens']]
                    current_lines=[d for sb in source_runs for d in sb]
                    for d in originals:
                        d['source_block_indices']=sj; d['block_alignment_verified']=True
                        d['current_block_lines']=[{'source_line':x['source_line'],'current_text':x['current_text']} for x in current_lines]
                        d['block_control_comparison']={'original_tokens':original_tokens,'current_tokens':current_tokens,
                            'classification':('same_tokens' if original_tokens==current_tokens else 'token_mismatch') if original_tokens else ('false_head_name_artifact' if current_tokens else 'no_name_token')}
                source_commands=[e for e in source_events if e['kind']=='command']
                original_commands=[e for e in original_events if e['kind']=='command']
                reviewed_locations={
                    '172bbec':('ロブ工房　１階',"Rob's Workshop　1st Floor"),
                    '17627ec':('ルイーズ村　村長の家',"Louise Village　Mayor's House"),
                    '1762f3c':('ルイーズ村　民家Ｂ',"Louise Village　Villager's House B"),
                }
                if address in reviewed_locations:
                    jp,expected_current=reviewed_locations[address]
                    source_location=[e for e in source_commands if e.get('code')==0x0363]
                    original_location=[e for e in original_commands if e.get('code')==0x0363]
                    location_strings=[s for s in runtime_strings if s.get('code')==0x0363]
                    if (len(source_location)!=1 or len(original_location)!=1 or len(location_strings)!=1
                        or source_location[0]['strings']!=[expected_current]
                        or location_strings[0]['text']!=jp or location_strings[0]['control_tokens']
                        or current_name_indices(expected_current)):
                        raise ValueError(f'reviewed unique placetxt context changed at {address}')
                    location_strings[0].update({'source_line':source_location[0]['source_line'],
                        'current_text':expected_current,'source_alignment_method':'unique same-opcode placetxt; address-specific source text reviewed'})
                for oi,oe in enumerate(original_commands):
                    if oi not in command_map: continue
                    se=source_commands[command_map[oi][0]]
                    strs=[r for r in runtime_strings if r['command_offset']==oe['command_offset']]
                    oe['source_line']=se['source_line']; oe['current_strings']=se['strings']
                    for ix,sr in enumerate(strs):
                        if ix<len(se['strings']):
                            sr['source_line']=se['source_line']; sr['current_text']=se['strings'][ix]
                            sr['current_name_tokens']=[f'{{NAME_{x}}}' for x in current_name_indices(se['strings'][ix])]
                            orig=[t['token'] for t in sr['control_tokens']]; cur=sr['current_name_tokens']
                            sr['control_comparison']={'original_tokens':orig,'current_tokens':cur,
                                'classification':('same_tokens' if orig==cur else 'token_mismatch') if orig else ('false_head_name_artifact' if cur else 'no_name_token')}
            # Location-only scripts have no dialog blocks, so handle their one
            # address-reviewed placetxt binding independently of block alignment.
            reviewed_locations={
                '172bbec':('ロブ工房　１階',"Rob's Workshop　1st Floor"),
                '17627ec':('ルイーズ村　村長の家',"Louise Village　Mayor's House"),
                '1762f3c':('ルイーズ村　民家Ｂ',"Louise Village　Villager's House B"),
            }
            if address in reviewed_locations:
                jp,expected_current=reviewed_locations[address]
                source_location=[e for e in source_events if e['kind']=='command' and e.get('code')==0x0363]
                original_location=[e for e in original_events if e['kind']=='command' and e.get('code')==0x0363]
                location_strings=[s for s in runtime_strings if s.get('code')==0x0363]
                if (len(source_location)!=1 or len(original_location)!=1 or len(location_strings)!=1
                    or source_location[0]['strings']!=[expected_current]
                    or location_strings[0]['text']!=jp or location_strings[0]['control_tokens']
                    or current_name_indices(expected_current)):
                    raise ValueError(f'reviewed unique placetxt context changed at {address}')
                location_strings[0].update({'source_line':source_location[0]['source_line'],
                    'current_text':expected_current,'source_alignment_method':'unique same-opcode placetxt; address-specific source text reviewed'})
            runtime_comparison_groups=[]
            if address=='17c478c':
                source_big=[e for e in source_events if e['kind']=='command' and e.get('code')==0x030b]
                original_big=[e for e in original_events if e['kind']=='command' and e.get('code')==0x030b]
                source_big=[e for e in source_big if e['strings']==['γ!!']]
                original_name_big=[s for s in runtime_strings if s.get('code')==0x030b and s['control_tokens']]
                original_big=[e for e in original_big if any(s['command_offset']==e['command_offset'] for s in original_name_big)]
                raw_lines=path.read_text(encoding='utf-8').splitlines()
                branch_values=[]
                for se in source_big:
                    preceding='\n'.join(raw_lines[max(0,se['source_line']-5):se['source_line']-1])
                    tests=re.findall(r'\$h216\s*==\s*(\d+)',preceding)
                    branch_values.append(int(tests[-1]) if tests else None)
                if len(source_big)==6 and len(original_big)==6 and branch_values==[1,2,3,4,5,6]:
                    ordered_tokens=[]; current_tokens=[]; original_rows=[]; current_lines=[]; operands_ok=True
                    for sr,se,branch in zip(original_name_big,source_big,branch_values):
                        oe=next((e for e in original_events if e['kind']=='command' and e['command_offset']==sr['command_offset']),None)
                        ex=oe.get('expression_signatures',[]) if oe else []
                        if len(ex)!=5 or any(len(x)!=3 or x[0]!=1 or x[2]!=0 for x in ex): operands_ok=False; break
                        orig_values=[x[1] for x in ex]; cur_values=se['operands']
                        if len(cur_values)!=5 or orig_values[1:]!=cur_values[1:] or not se['strings']:
                            operands_ok=False; break
                        orig_tokens=[t['token'] for t in sr['control_tokens']]
                        cur_tokens=[f'{{NAME_{i}}}' for i in current_name_indices(se['strings'][0])]
                        if orig_tokens!=['{NAME_1}'] or cur_tokens!=orig_tokens: operands_ok=False; break
                        sr.update({'source_line':se['source_line'],'current_text':se['strings'][0],
                            'source_alignment_method':'reviewed ordered six-way h216 conditional run; NAME tokens and non-position operands match; x layout differs in first three branches'})
                        original_rows.append(sr['ordinal']); current_lines.append(se['source_line'])
                        ordered_tokens.extend(orig_tokens); current_tokens.extend(cur_tokens)
                    if operands_ok:
                        runtime_comparison_groups.append({'original_ordinals':original_rows,'current_source_lines':current_lines,
                            'mapping_kind':'ordered_conditional_run','verified':True,
                            'evidence':'six h216 branches in order; each original NAME1!! matches current γ!!; y/style/flags match, first three x positions reflect inherited HEAD layout',
                            'original_tokens':ordered_tokens,'current_tokens':current_tokens,
                            'classification':'same_tokens' if ordered_tokens==current_tokens else 'token_mismatch'})
            if address=='18b2d1c':
                source_popup=[e for e in source_events if e['kind']=='command' and e.get('code')==0x0317]
                original_popup=[e for e in original_events if e['kind']=='command' and e.get('code')==0x0317]
                popup_strings=[s for s in runtime_strings if s.get('code')==0x0317]
                expected_texts=['γ came to!','You can change equipment.']
                if (len(source_popup)==2 and len(original_popup)==2 and len(popup_strings)==2
                    and source_popup[0]['strings']==[expected_texts[0]] and source_popup[1]['strings']==[expected_texts[1]]
                    and popup_strings[0]['text']=='{NAME_1}が我に返った！' and popup_strings[1]['control_tokens']==[]):
                    original_tokens=[]; current_tokens=[]
                    for sr,se in zip(popup_strings,source_popup):
                        ot=[t['token'] for t in sr['control_tokens']]
                        ct=[f'{{NAME_{i}}}' for i in current_name_indices(se['strings'][0])]
                        if ot!=ct: break
                        sr.update({'source_line':se['source_line'],'current_text':se['strings'][0],
                            'source_alignment_method':'reviewed ordered two-popup run; original and current NAME token vectors match'})
                        original_tokens.extend(ot);current_tokens.extend(ct)
                    else:
                        runtime_comparison_groups.append({'original_ordinals':[s['ordinal'] for s in popup_strings],
                            'current_source_lines':[e['source_line'] for e in source_popup],
                            'mapping_kind':'ordered_runtime_string_run','verified':True,
                            'evidence':'unique ordered popup pair; first Japanese/current strings correspond and second pair has no NAME token',
                            'original_tokens':original_tokens,'current_tokens':current_tokens,
                            'classification':'same_tokens' if original_tokens==current_tokens else 'token_mismatch'})
            reviewed_cat_popup={
                '180184c','181177c','181e00c','1840e9c','184fdfc','185dfac'
            }
            if address in reviewed_cat_popup:
                original_popup=[s for s in runtime_strings if s.get('code')==0x0317 and s.get('ordinal')==0]
                source_popup=[e for e in source_events if e['kind']=='command' and e.get('code')==0x0317
                              and e['strings']==['The cat ran away!']]
                original_commands=[e for e in original_events if e['kind']=='command']
                source_commands=[e for e in source_events if e['kind']=='command']
                def const_expr_values(event):
                    vals=[]
                    for expr in event.get('expression_signatures',[]):
                        if len(expr)!=3 or expr[0]!=1 or expr[2]!=0: return None
                        v=expr[1]
                        vals.append(v-0x10000 if v>=0x8000 else v)
                    return vals
                if len(original_popup)==1 and len(source_popup)==1 and original_popup[0]['text']=='ネコが逃げ出した！' and not original_popup[0]['control_tokens']:
                    op=next(i for i,e in enumerate(original_commands) if e['command_offset']==original_popup[0]['command_offset'])
                    sp=source_commands.index(source_popup[0])
                    if (op>=2 and op+1<len(original_commands) and sp>=2 and sp+1<len(source_commands)
                        and original_commands[op-2]['code']==0x0002
                        and original_commands[op-1]['code']==0x0366
                        and const_expr_values(original_commands[op-1])==[507,-1]
                        and original_commands[op+1]['code']==0x0318
                        and source_commands[sp-2]['code']==0x0002
                        and source_commands[sp-1]['code']==0x0366
                        and source_commands[sp-1]['operands']==[507,-1]
                        and source_commands[sp+1]['code']==0x0318):
                        prior='\n'.join(path.read_text(encoding='utf-8').splitlines()[source_popup[0]['source_line']-3:source_popup[0]['source_line']-1])
                        if re.search(r'jumpz\s+@\w+\s*,\s*\$b070\b',prior):
                            original_popup[0].update({'source_line':source_popup[0]['source_line'],
                                'current_text':'The cat ran away!',
                                'source_alignment_method':'reviewed cat popup: original/current code 2 branch then code0366(507,-1), popup, code0318; source branch is $b070'})
                            runtime_comparison_groups.append({'original_ordinals':[original_popup[0]['ordinal']],
                                'current_source_lines':[source_popup[0]['source_line']],
                                'mapping_kind':'reviewed_ordered_popup_context','verified':True,
                                'evidence':'JP ネコが逃げ出した！ has no NAME control; exact cat notice follows $b070 branch and code0366(507,-1), then code0318',
                                'original_tokens':[],'current_tokens':[],
                                'classification':'same_tokens'})
            records[address]['runtime_comparison_groups']=runtime_comparison_groups
        except Exception as e:
            records[address]={'manifest_path':rel,'rom_offset':f'0x{off:x}',
                              'source_dialogtxt_count':source_count,'alignment':'parse_failure',
                              'error':str(e),'dialogtxt':[]}
    failures=[a for a,r in records.items() if r.get('alignment')=='parse_failure']
    if failures or len(records)!=1052:
        print(f'error: structural extraction failed for {len(failures)} scripts; no map written',file=sys.stderr)
        return 1
    compact={'rom_sha1':sha,'expected_rom_sha1':EXPECTED_ROM_SHA1,
             'manifest_entries':len(rows),'unique_addresses':len(records),
             'day2_overrides':sum('/Day2_scripts/' in rel for _,rel in rows),
             'records':{a:{'manifest_path':r['manifest_path'],'alignment':r['alignment'],
                           'source_dialogtxt_count':r['source_dialogtxt_count'],
                           'original_dialogtxt_count':r.get('original_dialogtxt_count'),
                           'dialog_blocks':[{'block_index':b['block_index'],'payload_ordinals':b['payload_ordinals'],
                                             'source_block_indices':b['source_block_indices'],'verified':b['verified'],
                                             'anchor_signature':b['anchor_signature'],
                                             'tokens':[t['token'] for n in b['payload_ordinals'] for t in r['dialogtxt'][n]['control_tokens']]}
                                            for b in r.get('original_blocks',[])],
                           'comparison_groups':r.get('comparison_groups',[]),
                           'runtime_comparison_groups':r.get('runtime_comparison_groups',[]),
                           'runtime_strings':[{'ordinal':s['ordinal'],'code':s['code'],'source_line':s.get('source_line'),
                                               'verified':s.get('source_line') is not None,
                                               'source_alignment_method':s.get('source_alignment_method',
                                                   'unique neighboring command anchors' if s.get('source_line') is not None else None),
                                               'tokens':[t['token'] for t in s['control_tokens']]}
                                              for s in r.get('original_non_dialog_strings',[])]}
                        for a,r in records.items()}}
    dest=cli.output.resolve(); dest.parent.mkdir(parents=True,exist_ok=True)
    temp=dest.with_suffix(dest.suffix+'.tmp')
    temp.write_text(json.dumps(compact,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    temp.replace(dest)
    summary={'rom_sha1':sha,'manifest_entries':len(rows),'unique_addresses':len(records),
             'verified_blocks':sum(b['verified'] for r in records.values() for b in r.get('original_blocks',[])),
             'unverified_blocks':sum(not b['verified'] for r in records.values() for b in r.get('original_blocks',[])),
             'output':str(dest)}
    print(json.dumps(summary,indent=2))
if __name__=='__main__': main()
