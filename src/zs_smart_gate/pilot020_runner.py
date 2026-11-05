"""Bounded020 one-shot engine with injected I/O and durable chunk claims.

Nothing calls this automatically. CLI separately checks native Windows, exact
Git HEAD, fixed Manifest and freshly fetched independent PM review before I/O.
"""
import base64
import hashlib
import os
from pathlib import Path
import threading
import time
from .pilot020 import Budget,REST_PLAN,canonical,sha,stream_payload,decision


class Journal:
    """Hierarchical claim-before-attempt: remote chunk reservation then local
    fsynced per-input claim; whole raw event+claim chain flushed/read back <=15s.
    A failed readback consumes the attempt; never retry the capture or PUT.
    """
    def __init__(self,root,store,study_id,initial_bytes=0):
        self.root=Path(root);self.store=store;self.study_id=study_id
        self.root.mkdir(parents=True,exist_ok=True);self.lock=threading.RLock()
        self.seq=0;self.previous='0'*64;self.pending=[];self.chunk=0;self.bytes=initial_bytes
        self.path=self.root/'events.jsonl';self.reserved=False
    def reserve(self):
        name=f'claims/chunk-{self.chunk:04}.json'
        body=canonical(dict(study_id=self.study_id,chunk=self.chunk,claim_before_attempt=True))
        self.store.create(name,body);self.bytes+=len(body);self.reserved=True
    def record(self,kind,payload):
        with self.lock:
            if not self.reserved:raise ValueError('REMOTE_CHUNK_NOT_RESERVED')
            value=dict(seq=self.seq+1,previous=self.previous,kind=kind,payload=payload)
            value['digest']=sha(value);raw=canonical(value)
            # Leave64KiB for terminal status/partial diagnostics and wrappers.
            if self.bytes+len(raw)+65536>3145728:raise ValueError('STUDY_SERIALIZED_CAP_STOP')
            with self.path.open('ab') as f:f.write(raw+b'\n');f.flush();os.fsync(f.fileno())
            self.pending.append(value);self.seq+=1;self.previous=value['digest'];self.bytes+=len(raw)+1
            return value
    def flush(self,*,next_chunk=True):
        with self.lock:
            body=canonical(dict(study_id=self.study_id,chunk=self.chunk,events=self.pending,last=self.previous))
            self.store.create(f'receipts/chunk-{self.chunk:04}.json',body)
            self.bytes+=len(body)-sum(len(canonical(x))+1 for x in self.pending)
            self.pending=[];self.chunk+=1;self.reserved=False
            if next_chunk:self.reserve()


def run_capture(m,*,journal,stream,rest,clock=time,health=lambda:None,cancel=lambda:False,
                execution_origin='SYNTHETIC_TEST_NOT_FIELD'):
    """Gate already verified by native entry; tests inject in-memory transports."""
    budget=stream.budget;raws=[];closed=set();status='HOLD';stop=threading.Event();errors=[]
    start=clock.monotonic();last_flush=start;last_health=start;old_wall=clock.time();old_mono=start
    def tick():
        nonlocal last_health,old_wall,old_mono
        now=clock.monotonic();wall=clock.time()
        if cancel():raise ValueError('CANCELLED_NO_RETRY')
        if wall>=m['end_at'] or now-start>=720:raise ValueError('HARD_END_NO_ROLLOVER')
        if abs((wall-old_wall)-(now-old_mono))>=1:raise ValueError('WALL_JUMP_OR_SLEEP')
        health()  # Native sleep/unbiased-counter guard; unavailable => stop.
        old_wall,old_mono=wall,now
        if now-last_health>=1:
            journal.record('HEALTH',dict(mono_ns=clock.monotonic_ns(),wall_ns=clock.time_ns(),state='ACTIVE'))
            last_health=now
    try:
        journal.reserve();journal.record('SESSION',dict(study_id=m['study_id'],phase='020-B',manifest_sha256=sha(m)))
        tick()
        if clock.time()>=m['target_close']:raise ValueError('TARGET_ALREADY_PASSED_BEFORE_CONNECT')
        stream.connect();budget=stream.budget
        while len(closed)<2:
            tick()
            # Shared15s checkpoint timer: source is never read while receipt
            # durability is unknown. Health is sampled before and after writes.
            if clock.monotonic()-last_flush>=15:
                journal.flush();tick();last_flush=clock.monotonic()
            if journal.bytes+524288>3145728:raise ValueError('STOP_BEFORE_READ_REST_AND_TERMINAL_CAPACITY_RESERVED')
            claimed=clock.monotonic_ns()
            journal.record('CLAIM_WS_READ',dict(claimed_mono_ns=claimed))
            raw,received,wall=stream.receive()
            if raw is None:
                journal.record('READ_IDLE_OR_CONTROL',dict(received_mono_ns=received));tick();continue
            record=dict(kind='ws',raw_base64=base64.b64encode(raw).decode(),raw_sha256=hashlib.sha256(raw).hexdigest(),
                claimed_mono_ns=claimed,sent_mono_ns=claimed,received_mono_ns=received,
                received_wall_ns=wall,epoch=m['study_id'])
            journal.record('RAW_WS',record);raws.append(record)
            tick()  # Even a clock/lifecycle fault must not erase arrived raw.
            symbol,value,tag=stream_payload(raw,m['target_close'])
            if value is not None:
                if symbol in closed:raise ValueError('DUPLICATE_FINAL_TARGET')
                closed.add(symbol)
        stream.close();tick()
        # Do not launch a five-second batch near the hard boundary.
        if m['end_at']-clock.time()<7:raise ValueError('INSUFFICIENT_REST_DEADLINE_RESERVE')
        claimed=clock.monotonic_ns()
        journal.record('CLAIM_SIX_REST',dict(claimed_mono_ns=claimed,plan=[list(x) for x in REST_PLAN]))
        batch=rest(REST_PLAN,on_attempt=budget.request)
        responses=batch['results'] if isinstance(batch,dict) else batch
        validation_errors=[]
        for response in responses:
            raw=base64.b64decode(response['raw_base64'],validate=True)
            response.update(kind='rest',claimed_mono_ns=claimed,epoch=m['study_id'],raw_sha256=hashlib.sha256(raw).hexdigest())
            journal.record('RAW_REST',response);raws.append(response)
            if response.get('error'):validation_errors.append('REST_CHILD_PARTIAL_OR_ERROR')
            try:budget.response(response['status'],raw,response['elapsed_seconds'])
            except ValueError as exc:validation_errors.append(str(exc))
        if isinstance(batch,dict) and batch.get('unavailable'):
            journal.record('MISSING_REST_RESPONSES',batch['unavailable']);validation_errors.append('REST_PARTIAL_BATCH_STOP')
        if validation_errors:raise ValueError(';'.join(validation_errors))
        tick();cutoff=clock.monotonic_ns()
        result=decision(m,raws,decision_mono_ns=cutoff,continuity_ok=True)
        journal.record('DECISION',result);journal.flush(next_chunk=False)
        status='FIELD_CAPTURE_EXECUTED_ON_OWNER_WINDOWS' if execution_origin=='OWNER_WINDOWS_VERIFIED' else 'SYNTHETIC_CAPTURE_SIMULATION_ONLY'
    except Exception as exc:
        errors.append(type(exc).__name__+':'+str(exc)[:160])
        result=dict(status='HOLD',field_relative_status='HOLD',reason=errors[-1],ABSOLUTE_UTC_PIT='HOLD',
                    publishable=False,score=None,OOS_QUALIFIED=False,forward='NOT_ARMED')
        # Storage failure may prevent remote closure. Preserve local report;
        # never retry the failed PUT or repeat source collection.
        try:
            if journal.reserved:
                partial=stream.partial() if hasattr(stream,'partial') else b''
                if partial:journal.record('INCOMPLETE_WS_PREFIX_NOT_A_VALID_MESSAGE',dict(raw_base64=base64.b64encode(partial).decode(),complete=False))
                journal.record('STOP_GAP_HOLD',result);journal.flush(next_chunk=False)
        except Exception:pass
    finally:
        stop.set();stream.close()
    report=dict(execution_status=status,execution_origin=execution_origin,result=result,ws_connection_attempts=budget.ws,
        ws_data_messages=budget.messages,ws_data_frames=budget.frames,ws_wire_bytes=budget.wire,GET_attempts=budget.gets,
        declared_weight_attempted=budget.weight,REST_response_bytes=budget.rest_bytes,
        errors=errors,serialized_study_bytes=journal.bytes,repeat_allowed=False)
    (journal.root/'result.json').write_bytes(canonical(report))
    return report


def verify_chunks(chunks):
    previous='0'*64;seq=0
    for i,chunk in enumerate(chunks):
        if chunk['chunk']!=i:raise ValueError('MISSING_CHUNK')
        for e in chunk['events']:
            body={k:v for k,v in e.items() if k!='digest'}
            if e['seq']!=seq+1 or e['previous']!=previous or e['digest']!=sha(body):
                raise ValueError('CHAIN_TAMPER_OR_GAP')
            previous=e['digest'];seq+=1
        if chunk['last']!=previous:raise ValueError('CHUNK_LAST_MISMATCH')
    return dict(records=seq,last=previous,application_only=True)
