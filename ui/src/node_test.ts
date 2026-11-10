import { runPeopleRosterRegressionSuite } from './roster_suite';

type Listener = (ev: FakeEvent) => void;

class FakeEvent {
  public readonly type: string;
  public readonly bubbles: boolean;
  public readonly cancelable: boolean;
  public readonly shiftKey: boolean;
  public target: FakeElement | null = null;

  constructor(
    type: string,
    init?: { bubbles?: boolean; cancelable?: boolean; shiftKey?: boolean },
  ) {
    this.type = type;
    this.bubbles = Boolean(init?.bubbles);
    this.cancelable = Boolean(init?.cancelable);
    this.shiftKey = Boolean(init?.shiftKey);
  }
}

class FakeClassList {
  private set = new Set<string>();
  constructor(initial = '') {
    this.syncFrom(initial);
  }
  public syncFrom(cls: string): void {
    this.set.clear();
    for (const part of cls.split(/\s+/)) {
      if (part) this.set.add(part);
    }
  }
  public toString(): string {
    return Array.from(this.set).join(' ');
  }
  public add(...tokens: string[]): void {
    for (const t of tokens) if (t) this.set.add(t);
  }
  public remove(...tokens: string[]): void {
    for (const t of tokens) this.set.delete(t);
  }
  public toggle(token: string, force?: boolean): boolean {
    const shouldHave = force !== undefined ? force : !this.set.has(token);
    if (shouldHave) this.set.add(token);
    else this.set.delete(token);
    return shouldHave;
  }
  public contains(token: string): boolean {
    return this.set.has(token);
  }
}

class FakeElement {
  public readonly tagName: string;
  public readonly ownerDocument: FakeDocument;
  public parentNode: FakeElement | null = null;
  public children: FakeElement[] = [];
  public attributes = new Map<string, string>();
  public dataset: Record<string, string> = {};
  public style: Record<string, string> = {};
  public classList = new FakeClassList();
  public hidden = false;
  public disabled = false;
  public checked = false;
  public value = '';
  public placeholder = '';
  public scrollTop = 0;
  public scrollLeft = 0;
  private _textContent = '';
  private _innerHTML = '';
  private listeners = new Map<string, Listener[]>();

  constructor(tagName: string, doc: FakeDocument) {
    this.tagName = tagName.toUpperCase();
    this.ownerDocument = doc;
  }

  public get id(): string {
    return this.attributes.get('id') ?? '';
  }
  public set id(v: string) {
    this.attributes.set('id', v);
  }

  public get className(): string {
    return this.classList.toString();
  }
  public set className(v: string) {
    this.classList.syncFrom(v);
  }

  public get firstChild(): FakeElement | null {
    return this.children[0] ?? null;
  }

  public get nextSibling(): FakeElement | null {
    if (!this.parentNode) return null;
    const idx = this.parentNode.children.indexOf(this);
    return idx >= 0 && idx + 1 < this.parentNode.children.length
      ? this.parentNode.children[idx + 1]
      : null;
  }

  public get textContent(): string {
    if (this.children.length > 0) {
      return this.children.map((c) => c.textContent).join('');
    }
    return this._textContent;
  }
  public set textContent(v: string) {
    this.children = [];
    this._textContent = String(v ?? '');
  }

  public get innerHTML(): string {
    return this._innerHTML;
  }
  public set innerHTML(html: string) {
    this._innerHTML = html;
    this.children = [];
    this._textContent = '';
    parseHtmlInto(this, html);
  }

  public setAttribute(name: string, val: string): void {
    this.attributes.set(name, val);
    if (name === 'id') {
      // handled
    } else if (name === 'class') {
      this.classList.syncFrom(val);
    } else if (name === 'hidden') {
      this.hidden = true;
    } else if (name === 'value') {
      this.value = val;
    } else if (name === 'placeholder') {
      this.placeholder = val;
    } else if (name.startsWith('data-')) {
      const camel = name
        .slice(5)
        .replace(/-([a-z])/g, (_, c: string) => c.toUpperCase());
      this.dataset[camel] = val;
    }
  }

  public getAttribute(name: string): string | null {
    return this.attributes.get(name) ?? null;
  }

  public appendChild(child: FakeElement): FakeElement {
    if (child.parentNode) {
      child.remove();
    }
    child.parentNode = this;
    this.children.push(child);
    if (this.tagName === 'SELECT' && child.tagName === 'OPTION' && !this.value) {
      this.value = child.value || child.textContent;
    }
    return child;
  }

  public insertBefore(node: FakeElement, ref: FakeElement | null): FakeElement {
    if (node === ref) return node;
    if (node.parentNode) {
      node.remove();
    }
    node.parentNode = this;
    if (!ref) {
      this.children.push(node);
    } else {
      const idx = this.children.indexOf(ref);
      if (idx >= 0) {
        this.children.splice(idx, 0, node);
      } else {
        this.children.push(node);
      }
    }
    return node;
  }

  public remove(): void {
    if (!this.parentNode) return;
    const idx = this.parentNode.children.indexOf(this);
    if (idx >= 0) {
      this.parentNode.children.splice(idx, 1);
    }
    this.parentNode = null;
  }

  public focus(): void {
    this.ownerDocument.activeElement = this;
  }

  public click(): void {
    if (this.disabled) return;
    if (this.tagName === 'INPUT' && this.attributes.get('type') === 'checkbox') {
      this.checked = !this.checked;
      this.dispatchEvent(new FakeEvent('change', { bubbles: true }));
    }
    this.dispatchEvent(new FakeEvent('click', { bubbles: true, cancelable: true }));
  }

  public addEventListener(type: string, listener: Listener): void {
    const arr = this.listeners.get(type) ?? [];
    arr.push(listener);
    this.listeners.set(type, arr);
  }

  public dispatchEvent(ev: FakeEvent): boolean {
    if (!ev.target) ev.target = this;
    let cur: FakeElement | null = this;
    while (cur) {
      const arr = cur.listeners.get(ev.type);
      if (arr) {
        for (const fn of [...arr]) {
          fn(ev);
        }
      }
      if (!ev.bubbles) break;
      cur = cur.parentNode;
    }
    return true;
  }

  public matches(selector: string): boolean {
    const s = selector.trim();
    if (s.startsWith('#')) {
      return this.id === s.slice(1);
    }
    if (s.startsWith('.')) {
      return this.classList.contains(s.slice(1));
    }
    const attrMatch = /^([a-zA-Z0-9_-]+)?\[([a-zA-Z0-9_-]+)(?:="([^"]*)")?\]$/.exec(s);
    if (attrMatch) {
      const [, tag, attr, val] = attrMatch;
      if (tag && this.tagName !== tag.toUpperCase()) return false;
      const hasAttr =
        attr.startsWith('data-')
          ? this.dataset[attr.slice(5).replace(/-([a-z])/g, (_, c: string) => c.toUpperCase())] !== undefined
          : this.attributes.has(attr);
      if (!hasAttr) return false;
      if (val !== undefined) {
        const actual = attr.startsWith('data-')
          ? this.dataset[attr.slice(5).replace(/-([a-z])/g, (_, c: string) => c.toUpperCase())]
          : this.attributes.get(attr);
        return actual === val;
      }
      return true;
    }
    return this.tagName === s.toUpperCase();
  }

  public closest(selector: string): FakeElement | null {
    let cur: FakeElement | null = this;
    while (cur) {
      if (cur.matches(selector)) return cur;
      cur = cur.parentNode;
    }
    return null;
  }

  public querySelector(selector: string): FakeElement | null {
    return this.querySelectorAll(selector)[0] ?? null;
  }

  public querySelectorAll(selector: string): FakeElement[] {
    const results: FakeElement[] = [];
    const visit = (el: FakeElement): void => {
      for (const child of el.children) {
        if (child.matches(selector)) {
          results.push(child);
        }
        visit(child);
      }
    };
    visit(this);
    return results;
  }
}

class FakeDocument {
  public activeElement: FakeElement | null = null;
  public createElement(tag: string): FakeElement {
    return new FakeElement(tag, this);
  }
}

function parseHtmlInto(root: FakeElement, html: string): void {
  const cleaned = html.replace(/<!--[\s\S]*?-->/g, '');
  const tagRegex = /<\/?([a-zA-Z0-9-]+)([^>]*?)\/?>|([^<]+)/g;
  const stack: FakeElement[] = [root];
  const voidTags = new Set(['INPUT', 'IMG', 'BR', 'HR', 'META', 'LINK']);

  let match: RegExpExecArray | null;
  while ((match = tagRegex.exec(cleaned)) !== null) {
    const [full, rawTag, rawAttrs, textNode] = match;
    const current = stack[stack.length - 1];
    if (textNode !== undefined) {
      if (current.children.length === 0 && textNode.trim().length > 0) {
        current.textContent = textNode.trim();
      }
      continue;
    }
    const isClosing = full.startsWith('</');
    const isSelfClosing = full.endsWith('/>') || voidTags.has(rawTag.toUpperCase());
    if (isClosing) {
      if (stack.length > 1) stack.pop();
      continue;
    }
    const el = root.ownerDocument.createElement(rawTag);
    const attrRegex = /([a-zA-Z0-9_-]+)(?:="([^"]*)")?/g;
    let attrMatch: RegExpExecArray | null;
    while ((attrMatch = attrRegex.exec(rawAttrs)) !== null) {
      const [, attrName, attrVal] = attrMatch;
      el.setAttribute(attrName, attrVal ?? '');
    }
    current.appendChild(el);
    if (!isSelfClosing) {
      stack.push(el);
    }
  }
}

async function main(): Promise<void> {
  const g = globalThis as Record<string, unknown>;
  g.Event = FakeEvent;
  g.MouseEvent = FakeEvent;
  const doc = new FakeDocument();
  const root = doc.createElement('div');
  g.window = {
    dispatchEvent: () => true,
    addEventListener: () => {},
  };
  g.document = doc;

  const result = await runPeopleRosterRegressionSuite(root as unknown as HTMLElement);
  console.log(JSON.stringify(result, null, 2));
  if (!result.passed) {
    const proc = (globalThis as { process?: { exit?: (code: number) => void } }).process;
    if (proc?.exit) proc.exit(1);
  }
}

void main();
