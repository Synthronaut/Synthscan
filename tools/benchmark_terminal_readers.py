"""Controlled pixel replay. Generated fixtures are not live-game validation."""
import json
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw, ImageFont
from fabricator_inbox import FabricatorInbox
from refinery_orders import RefineryOrderBook
from screen_readers import read_image, refinery_orders, fabricator_candidates


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / 'research/terminal_reader_replay'
    output.mkdir(exist_ok=True)
    font = ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf', 24)
    def fixture(name, rows):
        image = Image.new('RGB', (1100, 700), '#172027')
        draw = ImageDraw.Draw(image)
        for text, x, y in rows:
            draw.text((x, y), text, font=font, fill='white')
        image.save(output / (name + '.png'))
        return image
    refinery = fixture('refinery_generated', [('Levski',40,20), ('COMPLETED',40,90), ('WORK ORDER 1',560,90),
                         ('MATERIALS YIELDED (CSCU)',40,160), ('QUALITY',430,160), ('YIELD',590,160),
                         ('IRON',40,225), ('874',450,225), ('235',600,225)])
    fabricator = fixture('fabricator_generated', [('FABRICATOR',40,30), ('BLUEPRINTS',40,90),
                         ('FR-76',40,160), ('XL-1',40,220), ('ADP Arms Black',40,280),
                         ('ADP Arms',40,340), ('BroadSpec',40,400)])
    cases = []
    with tempfile.TemporaryDirectory(prefix='SynthScan_TerminalReplay_') as temp:
        book = RefineryOrderBook(Path(temp) / 'orders.json')
        inbox = FabricatorInbox(Path(temp) / 'inbox.json')
        for name, image in [('refinery_generated',refinery), ('fabricator_generated',fabricator)]:
            for attempt in range(2):
                start = time.perf_counter()
                boxes = read_image(image)
                orders, blueprints = refinery_orders(boxes), fabricator_candidates(boxes)
                outcomes = [book.observe(o, now=100+attempt*6) for o in orders]
                inbox.add(blueprints)
                cases.append(dict(name=name, synthetic=True, attempt=attempt+1,
                                  ms=round((time.perf_counter()-start)*1000, 1),
                                  text=[b.text for b in boxes], orders=orders,
                                  blueprints=[b['name'] for b in blueprints], outcomes=outcomes))
        assert book.snapshot()[0]['parts'] == [dict(material='Iron', quality=874, scu=2.35)]
        assert book.snapshot()[0]['status'] == 'completed'
        assert {v['name'] for v in inbox.pending.values()} == {'FR-76','XL-1','ADP Arms Black'}
        # Real game images from upstream, containing mining instrumentation,
        # must not create fabricator ownership candidates or refinery orders.
        negatives = [root / 'research/bedrock_upstream/tests/scanpanel/scan_fullscreen_1080.png',
                     root / 'research/bedrock_upstream/tests/scanpanel/panel_mole_cockpit_1440.png']
        for path in negatives:
            start = time.perf_counter()
            boxes = read_image(str(path))
            orders, blueprints = refinery_orders(boxes, 'Levski'), fabricator_candidates(boxes)
            assert not orders and not blueprints
            cases.append(dict(name=path.name, synthetic=False, role='negative_only',
                              ms=round((time.perf_counter()-start)*1000,1), orders=orders, blueprints=blueprints))
        result = dict(cases=cases, order_count=len(book.snapshot()), inbox_count=len(inbox.pending),
                      limitation='Generated positive fixtures; real mining negative fixtures. No actual fabricator/refinery terminal validation.')
        (output / 'results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
