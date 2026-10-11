"""Outbound CAL assistance contract. This stub has no movement authority."""
from memory.evidence import digest


def request_recovery(*, episode, symptoms, camera_session=None):
    request = dict(schema='charlie-cal-recovery-request-v1', episode=str(episode),
                   camera_session=camera_session, symptoms=symptoms,
                   hypotheses=['viewpoint, illumination or camera fault remains unqualified'],
                   requested_evidence='fresh independently qualified camera view before a new marathon',
                   physical_authorization=False)
    return dict(request_id=digest(request), request=request, status='unavailable',
                reason='CAL recovery capability is not implemented or authorized',
                action='controls neutral; affected episode invalid; preserve original observations')
