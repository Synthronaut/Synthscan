"""Passive terminal readers. OCR produces evidence, not arbitrary inventory credits."""
from dataclasses import dataclass
import re
import threading

from crafting_catalog import get_catalog, normalize_name

_engine = None
_recognizer = None
_lock = threading.Lock()


@dataclass(frozen=True)
class TextBox:
    text: str
    confidence: float
    left: float
    top: float
    right: float
    bottom: float

    @property
    def x(self):
        return (self.left + self.right) / 2

    @property
    def y(self):
        return (self.top + self.bottom) / 2


def read_image(image, terminal_gate=False):
    import cv2
    import numpy as np
    from rapidocr_onnxruntime import RapidOCR
    if isinstance(image, str):
        frame = cv2.imread(image)
    elif hasattr(image, 'convert'):
        frame = cv2.cvtColor(np.asarray(image.convert('RGB')), cv2.COLOR_RGB2BGR)
    else:
        frame = image
    if frame is None or not frame.size:
        return []
    # Serialize this engine across manual scans and the passive terminal worker.
    global _engine, _recognizer
    with _lock:
        if _engine is None:
            _engine = RapidOCR(intra_op_num_threads=1, inter_op_num_threads=1,
                              det_model_path=None, det_limit_type='max', det_limit_side_len=1920)
            from textline_ocr import TextLineRecognizer
            _recognizer = TextLineRecognizer()
        detected, _ = _engine.text_detector(frame)
        if detected is None:
            return []
        detected = _engine.sorted_boxes(detected)
        crops = _engine.get_crop_img_list(frame, detected)
        readings = {}
        if terminal_gate:
            # A text-dense cockpit can contain hundreds of labels. Read a
            # bounded set of larger title candidates before spending work on
            # the whole image. Manual scans bypass this conservative gate.
            candidates = sorted(range(len(crops)), key=lambda i: -crops[i].shape[0])[:24]
            context = False
            for index in candidates:
                text, score = _recognizer.read(crops[index])
                readings[index] = (text, score)
                if score >= .85 and re.search(r'\b(?:WORK ORDER|REFINEMENT CENTER|FABRICATOR|FABRICATION|BLUEPRINTS)\b', text, re.I):
                    context = True
                    break
            if not context:
                return []
        results = []
        for index, (bounds, crop) in enumerate(zip(detected, crops)):
            text, score = readings[index] if index in readings else _recognizer.read(crop)
            if text:
                results.append((bounds, text, score))
    return [TextBox(text.strip(), float(score), float(min(p[0] for p in box)), float(min(p[1] for p in box)),
                    float(max(p[0] for p in box)), float(max(p[1] for p in box)))
            for box, text, score in results or [] if text.strip()]


def fabricator_candidates(boxes, catalog=None):
    """Exact item rows only. Ownership is reviewed because lock icons aren't read yet.

    Never concatenate the screen: doing so turns adjacent variants into matches.
    Screen labels, damaged OCR and partial names cannot create new recipes.
    """
    catalog = catalog or get_catalog()
    found = {}
    context = any(re.search(r'\b(fabricat(?:or|ion)|blueprints?|crafting)\b', b.text, re.I)
                  and b.confidence >= .85 for b in boxes)
    if not context:
        return []
    for box in boxes:
        if box.confidence < .90:
            continue
        name = re.sub(r'^blueprint\s*:\s*', '', box.text, flags=re.I)
        item = catalog.resolve(name)
        if item:
            found[item['id']] = dict(name=item['name'], id=item['id'], category=item['category'],
                                    confidence=box.confidence, evidence=box.text,
                                    ownership='review', source='Fabricator screen (review required)')
    return list(found.values())


def duration(text):
    text = text.strip().lower()
    found = re.findall(r'(\d+)\s*([dhms])\b', text)
    if not found:
        return None
    remainder = re.sub(r'\d+\s*[dhms]\b', '', text).strip()
    if remainder:
        return None
    return sum(int(n) * {'d': 86400, 'h': 3600, 'm': 60, 's': 1}[u] for n, u in found)


def _material(text, catalog):
    text = re.sub(r'\s*\((ore|raw)\)\s*$', '', text, flags=re.I)
    key = normalize_name(text).replace('aluminium', 'aluminum')
    aliases = {'raw ice': 'Pressurized Ice', 'raw silicon': 'Silicon',
               'construction materials': 'Construction Salvage'}
    if key in aliases:
        return aliases[key]
    for name in catalog.materials:
        if normalize_name(name) == key:
            return name
    return None


def refinery_orders(boxes, station_hint='', catalog=None):
    """Read panel-local, explicitly labelled QUALITY and YIELD columns.

    Only processing/completed work orders qualify. Setup quotes never count as
    orders. Unknown station/units/quality/columns yield no observation. Column
    boxes must be split by OCR; merged headers are rejected, never guessed.
    """
    catalog = catalog or get_catalog()
    boxes = [b for b in boxes if b.confidence >= .90]
    headers = []
    for b in boxes:
        m = re.fullmatch(r'WORK\s+ORDER\s*#?\s*(\d+)', b.text, re.I)
        if m:
            headers.append((b, int(m[1])))
    headers.sort(key=lambda h: h[0].x)
    if not headers:
        return []
    # An explicit station label wins. A user-selected station is an honest fallback.
    known_stations = {normalize_name(s): s for s in catalog.data['refinery_stations']}
    stations = []
    for b in boxes:
        label = re.sub(r'^(?:STATION|REFINERY)\s*:\s*', '', b.text, flags=re.I)
        if normalize_name(label) in known_stations:
            stations.append(known_stations[normalize_name(label)])
    if len(set(stations)) > 1:
        return []
    station = stations[0] if len(set(stations)) == 1 else station_hint.strip()
    if not station:
        return []
    output = []
    for i, (header, number) in enumerate(headers):
        # Pair each order label with the state on its left in the same band.
        # These observed anchors define panel boundaries without assuming a
        # fixed screen resolution or splitting a material row in half.
        anchors = []
        for candidate, _ in headers:
            band = [b for b in boxes if b.text.upper() in ('SETUP', 'PROCESSING', 'COMPLETED')
                    and b.right <= candidate.left and abs(b.y-candidate.y) <= max(5, candidate.bottom-candidate.top)]
            anchors.append(max(band, key=lambda b: b.right) if band else None)
        if anchors[i] is None:
            continue
        left = anchors[i].left - (header.bottom-header.top)
        right = anchors[i+1].left - (header.bottom-header.top) if i+1 < len(headers) and anchors[i+1] else header.right + (header.right-left)*.10
        panel = [b for b in boxes if left <= b.x < right and b.top >= header.top - 2 * (header.bottom-header.top)]
        statuses = [anchors[i].text.upper()] if anchors[i].text.upper() != 'SETUP' else []
        if len(set(statuses)) != 1:
            continue
        state = statuses[0].lower()
        quality_headers = [b for b in panel if b.text.upper() == 'QUALITY']
        yield_headers = [b for b in panel if re.fullmatch(r'YIELD(?:\s*\((?:C?SCU)\))?', b.text, re.I)]
        if len(quality_headers) != 1 or len(yield_headers) != 1:
            continue
        qh, yh = quality_headers[0], yield_headers[0]
        if abs(qh.y-yh.y) > max(qh.bottom-qh.top, yh.bottom-yh.top):
            continue
        alltext = ' '.join(b.text for b in panel)
        unit = 'cSCU' if re.search(r'\bCSCU\b', alltext, re.I) else 'SCU' if re.search(r'\bSCU\b', alltext, re.I) else None
        if unit is None:
            continue
        parts = []
        for label in panel:
            mat = _material(label.text, catalog)
            if not mat or label.y <= qh.y:
                continue
            tolerance = max(5, (label.bottom-label.top) * .6)
            row = [b for b in panel if abs(b.y-label.y) <= tolerance and re.fullmatch(r'\d[\d,]*(?:\.\d+)?', b.text)]
            qnums = [b for b in row if abs(b.x-qh.x) <= max(18, (qh.right-qh.left)*.6)]
            yields = [b for b in row if abs(b.x-yh.x) <= max(18, (yh.right-yh.left)*.6)]
            if len(qnums) != 1 or len(yields) != 1 or qnums[0] is yields[0]:
                continue
            if not qnums[0].text.isdigit():
                continue
            quality = int(qnums[0].text)
            amount = float(yields[0].text.replace(',', ''))
            if not 1 <= quality <= 1000 or not 0 < amount <= 100000000:
                continue
            # Reject qualities inconsistent with this material's game-file bands.
            bands = catalog.materials.get(mat, {}).get('quality_bands', [])
            if bands and quality not in bands:
                continue
            parts.append(dict(material=mat, quality=quality, scu=round(amount / 100 if unit == 'cSCU' else amount, 4)))
        if not parts:
            continue
        remaining = None
        for b in panel:
            m = re.fullmatch(r'TIME REMAINING\s*:?\s*(.+)', b.text, re.I)
            if m:
                remaining = duration(m[1])
        output.append(dict(station=station, number=number, status=state, parts=parts,
                           remaining_seconds=remaining, source='Terminal OCR', partial=True))
    return output
