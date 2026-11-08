"""Geometric sunlight forecasts, in real UTC seconds and body-fixed km.

Catalogue conventions follow VerseTime (GPL-3.0); see third_party/versetime.
The solver is independent: signed declination, exact seconds, polar cases and
the upper stellar limb above a spherical horizon, including observer height.
No game process, clipboard, network or UI access belongs in this module.
"""
from dataclasses import dataclass
import math

EPOCH = 1577836800.0  # 2020-01-01 UTC; community rotation reference
TAU = 2 * math.pi


def finite(value):
    if isinstance(value, bool):
        raise ValueError('Expected a finite number')
    number = float(value)
    if not math.isfinite(number):
        raise ValueError('Expected a finite number')
    return number


def vector(values):
    if len(values) != 3:
        raise ValueError('Expected XYZ coordinates')
    result = tuple(finite(v) for v in values)
    if max(map(abs, result)) > 1e12:
        raise ValueError('Coordinate out of range')
    return result


def rotate(quaternion, point):
    if len(quaternion) != 4:
        raise ValueError('Expected WXYZ quaternion')
    q = [finite(v) for v in quaternion]
    norm = math.sqrt(sum(v*v for v in q))
    if norm < 1e-8:
        raise ValueError('Invalid rotation quaternion')
    w, x, y, z = [v/norm for v in q]
    a, b, c = vector(point)
    return ((1-2*y*y-2*z*z)*a+(2*x*y-2*z*w)*b+(2*x*z+2*y*w)*c,
            (2*x*y+2*z*w)*a+(1-2*x*x-2*z*z)*b+(2*y*z-2*x*w)*c,
            (2*x*z-2*y*w)*a+(2*y*z+2*x*w)*b+(1-2*x*x-2*y*y)*c)


@dataclass(frozen=True)
class Body:
    name: str
    radius: float
    period: float  # signed real seconds per rotation; zero means stationary
    sun_longitude: float  # radians at EPOCH
    declination: float
    star_radius_angle: float = 0.0

    def __post_init__(self):
        for value in (self.radius, self.period, self.sun_longitude, self.declination, self.star_radius_angle):
            finite(value)
        if self.radius <= 0 or (self.period and not 60 <= abs(self.period) <= 86400*365):
            raise ValueError('Unsupported body radius or rotation period')
        if abs(self.declination) > math.pi/2 or not 0 <= self.star_radius_angle < math.pi/2:
            raise ValueError('Invalid star geometry')

    @classmethod
    def from_record(cls, row):
        center, star = vector(row['center_km']), vector(row['star_km'])
        x, y, z = rotate(row['quaternion'], [s-b for s, b in zip(star, center)])
        distance = math.sqrt(x*x+y*y+z*z)
        radius = finite(row['star_radius_km'])
        if not 0 < radius < distance:
            raise ValueError('Invalid star radius/distance')
        return cls(row['name'], finite(row['radius_km']), finite(row['period_seconds']),
                   math.atan2(y, x)-math.pi/2-math.radians(finite(row['correction_degrees'])),
                   math.atan2(z, math.hypot(x, y)), math.asin(radius/distance))


@dataclass(frozen=True)
class Site:
    name: str
    coordinates: tuple

    def __post_init__(self):
        object.__setattr__(self, 'coordinates', vector(self.coordinates))
        if math.sqrt(sum(v*v for v in self.coordinates)) == 0:
            raise ValueError('Site cannot be at the body center')


def geometry(body, site):
    x, y, z = vector(site.coordinates)
    radius = math.sqrt(x*x+y*y+z*z)
    latitude = math.atan2(z, math.hypot(x, y))
    longitude = math.atan2(y, x)
    dip = math.acos(min(1.0, body.radius/radius)) if radius > body.radius else 0.0
    threshold = -min(math.pi/2, body.star_radius_angle+dip)
    a = math.sin(latitude)*math.sin(body.declination)
    b = math.cos(latitude)*math.cos(body.declination)
    return a, b, longitude, threshold


def forecast(body, site, at, phase_offset=0.0, cycles=3):
    """At arrival: state, true center altitude, next events and daylight windows.

    Windows are clipped at arrival; a current daylight window starts at arrival.
    Times are UTC Unix seconds, never fictional accelerated universe time.
    """
    at = finite(at)
    offset = finite(phase_offset)
    if not 1 <= cycles <= 8:
        raise ValueError('Use 1 to 8 forecast cycles')
    a, b, longitude, threshold = geometry(body, site)
    omega = -TAU/body.period if body.period else 0.0
    hour = (body.sun_longitude-longitude+offset+omega*((at-EPOCH) % abs(body.period))) if omega else body.sun_longitude-longitude+offset
    sine = max(-1.0, min(1.0, a+b*math.cos(hour)))
    altitude = math.asin(sine)
    light = altitude >= threshold
    if omega and abs(altitude-threshold) < 1e-10:
        light = a+b*math.cos(hour+omega*.001) >= math.sin(threshold)
    horizon = math.sin(threshold)
    result = dict(at=at, daylight=light, altitude_degrees=math.degrees(altitude),
                  sunrise=None, sunset=None, events=[], windows=[], period_seconds=abs(body.period),
                  continuous=None)
    if not omega or b < 1e-12 or horizon <= a-b or horizon >= a+b:
        result['continuous'] = 'daylight' if light else 'night'
        return result
    theta = math.acos(max(-1.0, min(1.0, (horizon-a)/b)))
    period = abs(body.period)
    events = []
    for target in (theta, -theta):
        delta = ((target-hour) if omega > 0 else (hour-target)) % TAU
        seconds = delta/abs(omega)
        if seconds < 0.001:
            seconds += period
        kind = 'sunrise' if -b*math.sin(target)*omega > 0 else 'sunset'
        for cycle in range(cycles):
            events.append(dict(kind=kind, at=at+seconds+cycle*period))
    events.sort(key=lambda event: event['at'])
    result['events'] = events
    for event in events:
        if result[event['kind']] is None:
            result[event['kind']] = event['at']
    start = at if light else None
    for event in events:
        if event['kind'] == 'sunrise':
            start = event['at']
        elif start is not None:
            result['windows'].append((start, event['at']))
            start = None
    return result


def observed_phase(body, site, at, kind):
    """Phase correction from an observed unobstructed horizon crossing."""
    if kind not in ('sunrise', 'sunset') or not body.period:
        raise ValueError('Choose sunrise/sunset on a rotating body')
    a, b, longitude, threshold = geometry(body, site)
    cosine = (math.sin(threshold)-a)/b if b > 1e-12 else 2
    if not -1 < cosine < 1:
        raise ValueError('This site has no distinct horizon crossing')
    theta = math.acos(cosine)
    # Positive H is sunrise for the normal negative hour-angle velocity.
    target = theta if (kind == 'sunrise') == (body.period > 0) else -theta
    hour = body.sun_longitude-longitude-TAU*((finite(at)-EPOCH) % abs(body.period))/body.period
    return (target-hour+math.pi) % TAU-math.pi
