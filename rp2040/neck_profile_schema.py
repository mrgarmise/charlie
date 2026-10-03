"""Hardware-free schema validation shared with Pi, no actuator imports."""
import math
try:
    from motion_geometry import polygon, contains
except ImportError:
    from .motion_geometry import polygon, contains

HARDWARE = dict(controller='rp2040',head_a=[4,5],head_b_disabled=[14,15],
                calibration_input=10,calibration_input_only=True)


def validate(document):
    if (not isinstance(document,dict) or document.get('schema')!='charlie-neck-profile-v1'
            or document.get('hardware')!=HARDWARE or document.get('validation_status')!='QUALIFIED'
            or document.get('pose_source')!='operator_confirmed_estimate'
            or document.get('measured_position') is not None or document.get('simulated') is not False
            or document.get('pins')!=[4,5] or document.get('assembled_head_verified') is not True):
        raise ValueError('UNQUALIFIED_OR_INCOMPATIBLE_PROFILE')
    review=document.get('independent_review',{})
    if (not review.get('operator') or not review.get('reviewer') or review['operator']==review['reviewer']
            or review.get('physical_validation') is not True or not review.get('evidence')):
        raise ValueError('INDEPENDENT_PHYSICAL_REVIEW_REQUIRED')
    if not document.get('created_at') or not document.get('qualified_at') or not document.get('evidence_sha256'):
        raise ValueError('PROFILE_PROVENANCE_REQUIRED')
    if not isinstance(document.get('supersedes'),list): raise ValueError('PROFILE_HISTORY_REQUIRED')
    region=polygon(document.get('clearance_polygon'))
    def finite(v):
        if isinstance(v,bool): raise ValueError('INVALID_PROFILE_NUMBER')
        v=float(v)
        if not math.isfinite(v): raise ValueError('INVALID_PROFILE_NUMBER')
        return v
    for name in ('pan','tilt'):
        a=document[name];lo,hi,pl,ph=[finite(a[k]) for k in ('min','max','min_us','max_us')]
        if not 0<=lo<hi<=180 or not 0<pl<ph<20000: raise ValueError('INVALID_PROFILE_INTERVAL')
    if not 0<finite(document['max_rate'])<=30 or not 0<finite(document['max_step'])<=12 or not 0<finite(document['clearance_margin'])<=2:
        raise ValueError('INVALID_PROFILE_LIMIT')
    for p in region+[document['confirmed_arm_pose'],document['home_pose']]:
        if len(p)!=2 or not contains(region,p) or any(not document[a]['min']<=finite(p[i])<=document[a]['max'] for i,a in enumerate(('pan','tilt'))):
            raise ValueError('INVALID_PROFILE_POSE')
    for axis in ('pan','tilt'):
        vector=document['visual_response'][axis]
        if len(vector)!=2 or sum(finite(v)**2 for v in vector)<.0025:
            raise ValueError('VISUAL_RESPONSE_REQUIRED')
    size=document['observation_size']
    if not isinstance(size,list) or len(size)!=2 or any(type(v) is not int or not 16<=v<=10000 for v in size):
        raise ValueError('VISUAL_REFERENCE_SIZE_REQUIRED')
    return document
