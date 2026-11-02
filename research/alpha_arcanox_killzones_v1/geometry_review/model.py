"""Price-distance algebra, not a time-dependent breakout line or level provider."""
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PriceMark:
    case_id: str
    name: str
    value: Decimal | None
    evidence: str = 'UNVERIFIED'


@dataclass(frozen=True)
class Measurement:
    upper: PriceMark
    lower: PriceMark

    def __post_init__(self):
        same_case(self.upper,self.lower)
        for p in (self.upper,self.lower):
            if p.value is not None and (not p.value.is_finite() or p.value <= 0):
                raise ValueError('INVALID_CIRCLE_PRICE')
        if self.upper.value is not None and self.lower.value is not None and self.upper.value <= self.lower.value:
            raise ValueError('CIRCLE_PRICE_ORDER_INVALID')

    @property
    def case_id(self):
        return self.upper.case_id

    @property
    def height(self):
        if self.upper.value is None or self.lower.value is None:return None
        return self.upper.value-self.lower.value

    @property
    def observed(self):
        return self.height is not None and self.upper.evidence=='OBSERVED_PRICE' and self.lower.evidence=='OBSERVED_PRICE'


def same_case(*marks):
    ids={m.case_id for m in marks}
    if len(ids)!=1 or not next(iter(ids)):
        raise ValueError('MIXED_OR_UNSPECIFIED_SETUPS')


@dataclass(frozen=True)
class Projection:
    case_id: str
    direction: str
    support_circle: str
    anchor: PriceMark
    height: Decimal | None
    free_circle: str
    free_endpoint_price: Decimal | None
    status: str
    indicator_level: None = None  # Endpoint != verified SUPERIOR/INFERIOR automatically.


def project(measurement,anchor,direction):
    """UP: lower circle supports; DOWN: upper circle supports, conditionally.

    Anchor identity must come from the chart. HIGH/LOW are never arguments.
    No price is derived from pixel height or from a previously desired target.
    """
    same_case(measurement.upper,measurement.lower,anchor)
    if direction not in ('UP','DOWN'):raise ValueError('DIRECTION_INVALID')
    if anchor.value is not None and (not anchor.value.is_finite() or anchor.value <= 0):
        raise ValueError('INVALID_ANCHOR_PRICE')
    h=measurement.height
    target=None if h is None or anchor.value is None else anchor.value+(h if direction=='UP' else -h)
    if target is not None and target <= 0:raise ValueError('PROJECTED_PRICE_NONPOSITIVE')
    status=('MISSING_CIRCLE_OR_ANCHOR_PRICE' if target is None else
            'OBSERVED_GEOMETRY_ENDPOINT_ONLY' if measurement.observed and anchor.evidence=='OBSERVED_PRICE' else
            'CONDITIONAL_ANCHOR_HYPOTHESIS')
    return Projection(measurement.case_id,direction,'LOWER' if direction=='UP' else 'UPPER',anchor,h,
                      'UPPER' if direction=='UP' else 'LOWER',target,status)


def compare_verified_label(projection,label,*,same_setup_verified=False,endpoint_identity_verified=False):
    """No reverse fitting and no comparison across a new/old unidentified setup."""
    same_case(projection.anchor,label)
    if not same_setup_verified:return dict(status='SETUP_CORRESPONDENCE_UNVERIFIED',difference=None)
    if not endpoint_identity_verified:return dict(status='ENDPOINT_VS_INDICATOR_LEVEL_UNVERIFIED',difference=None)
    if (projection.status!='OBSERVED_GEOMETRY_ENDPOINT_ONLY' or label.evidence!='OBSERVED_PRICE'
            or label.value is None):
        return dict(status='PRICE_OR_ANCHOR_UNVERIFIED',difference=None)
    return dict(status='OBSERVED_SAME_SETUP_COMPARISON',difference=projection.free_endpoint_price-label.value)


@dataclass(frozen=True)
class PixelPoint:
    case_id: str
    x: Decimal
    y: Decimal


def clone_pixels(upper,lower,anchor,direction):
    """Literal photo-space translation; NOT calibrated price geometry."""
    same_case(upper,lower,anchor)
    if upper.y >= lower.y:raise ValueError('PIXEL_CIRCLE_ORDER_INVALID')
    dx,dy=upper.x-lower.x,upper.y-lower.y
    if direction=='UP':
        return PixelPoint(anchor.case_id,anchor.x+dx,anchor.y+dy),anchor
    if direction=='DOWN':
        return anchor,PixelPoint(anchor.case_id,anchor.x-dx,anchor.y-dy)
    raise ValueError('DIRECTION_INVALID')


def project_all_hypotheses(measurement,anchors,direction):
    """Retain input order and every documented anchor. Never rank by target fit."""
    return tuple(project(measurement,a,direction) for a in anchors)
