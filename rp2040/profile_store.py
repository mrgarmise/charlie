"""Read immutable qualified profile + activation pointer; quarantine is sticky.

No boot motion. Any missing/corrupt/incompatible file fails closed.
"""
try:
    import ujson as json
    import uhashlib as hashlib
    import ubinascii as binascii
except ImportError:
    import json, hashlib, binascii
from servos import Envelope, MotionError, token

HARDWARE = {'controller':'rp2040', 'head_a':[4,5], 'head_b_disabled':[14,15],
            'calibration_input':10, 'calibration_input_only':True}


def digest(raw):
    return binascii.hexlify(hashlib.sha256(raw).digest()).decode()


def validate(document):
    from neck_profile_schema import validate as validate_schema
    try: validate_schema(document)
    except (ValueError,TypeError,KeyError,OverflowError) as exc: raise MotionError(str(exc))
    if (not isinstance(document,dict) or document.get('schema')!='charlie-neck-profile-v1'
            or document.get('hardware')!=HARDWARE or document.get('validation_status')!='QUALIFIED'
            or document.get('pose_source')!='operator_confirmed_estimate'
            or document.get('measured_position') is not None
            or document.get('simulated') is not False):
        raise MotionError('UNQUALIFIED_OR_INCOMPATIBLE_PROFILE')
    review=document.get('independent_review',{})
    if (not review.get('operator') or not review.get('reviewer') or review['operator']==review['reviewer']
            or review.get('physical_validation') is not True or not review.get('evidence')):
        raise MotionError('INDEPENDENT_PHYSICAL_REVIEW_REQUIRED')
    token(document.get('calibration_id'))
    if not document.get('created_at') or not document.get('qualified_at') or not document.get('evidence_sha256'):
        raise MotionError('PROFILE_PROVENANCE_REQUIRED')
    if not isinstance(document.get('supersedes'),list): raise MotionError('PROFILE_HISTORY_REQUIRED')
    envelope=Envelope(document)
    if envelope.region is None or not 0 < float(document.get('clearance_margin',0)) <= 2:
        raise MotionError('COMBINED_CLEARANCE_REQUIRED')
    return document


def load(directory):
    try:
        with open(directory+'/activation.json') as f: selected=json.load(f)
        identifier=token(selected['calibration_id'])
        try:
            with open(directory+'/'+identifier+'.running') as f: f.read()
        except OSError as exc:
            if exc.args[0]!=2: raise
        else: raise MotionError('UNCLEAN_OPERATION_REQUIRES_RECALIBRATION')
        # Do not treat corrupt quarantine markers as clearance.
        try:
            with open(directory+'/'+identifier+'.quarantine.json') as f: f.read()
        except OSError as exc:
            if exc.args[0] != 2: raise
        else: raise MotionError('PROFILE_QUARANTINED')
        with open(directory+'/'+identifier+'.json','rb') as f: raw=f.read()
        if digest(raw)!=selected['sha256']: raise MotionError('PROFILE_DIGEST_MISMATCH')
        document=validate(json.loads(raw.decode()))
        if document['calibration_id']!=identifier: raise MotionError('PROFILE_ID_MISMATCH')
        return document
    except (OSError,ValueError,KeyError,TypeError,MotionError) as exc:
        raise MotionError('PERSISTENT_PROFILE_REFUSED: '+str(exc))


def quarantine(directory, identifier, reason):
    identifier=token(identifier)
    # Never overwrite a previous diagnostic marker; mere existence blocks boot.
    path=directory+'/'+identifier+'.quarantine.json'
    try:
        with open(path) as f: f.read()
        return
    except OSError as exc:
        if exc.args[0]!=2: raise
    with open(path,'w') as f:
        json.dump(dict(calibration_id=identifier,reason=str(reason),status='QUARANTINED'),f)
        f.flush()
    try:
        import os
        os.sync()
    except AttributeError: pass


def operation(directory,identifier,active):
    import os
    path=directory+'/'+token(identifier)+'.running'
    if active:
        with open(path,'w') as f: f.write('Unclean operation blocks profile reuse');f.flush()
    else:
        try:os.remove(path)
        except OSError as exc:
            if exc.args[0]!=2: raise
    try:os.sync()
    except AttributeError:pass
