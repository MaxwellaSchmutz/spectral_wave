// Restricted parser and formatter for the potential-matrix field.
//
// Accepts exactly the desktop syntax, e.g.  [[[0.40, 0.25j], [-0.25j, -0.20]]]
// : nested square-bracket lists of numbers, where a number is a real literal
// (with optional exponent), an imaginary literal with a j suffix, or a sum /
// difference "a+bj" / "a-bj", with optional unary minus/plus and optional
// parentheses around a single complex value (as Python prints them).
// Nothing else is accepted and nothing is ever evaluated.
import type { Complex } from "./types";

export class LiteralError extends Error {
  constructor(
    message: string,
    public position: number,
  ) {
    super(message);
  }
}

type Node = Complex | Node[];

const NUMBER = /[0-9]*\.?[0-9]*(?:[eE][+-]?[0-9]+)?/y;

/** Bracket levels in a K x L x L potential. */
const MAX_DEPTH = 3;

class Parser {
  pos = 0;
  constructor(private text: string) {}

  fail(what: string, at = this.pos): never {
    const shown = at >= this.text.length ? "end of input" : `"${this.text[at]}"`;
    throw new LiteralError(`${what} at character ${at + 1} (found ${shown})`, at);
  }

  skip(): void {
    while (this.pos < this.text.length && /\s/.test(this.text[this.pos])) this.pos++;
  }

  peek(): string {
    this.skip();
    return this.text[this.pos] ?? "";
  }

  parseValue(depth = 0): Node {
    const c = this.peek();
    if (c === "[") return this.parseList(depth + 1);
    return this.parseComplex();
  }

  parseList(depth: number): Node[] {
    const open = this.pos;
    // sites > rows > entries: anything deeper is not a potential (and must not recurse without bound).
    if (depth > MAX_DEPTH) {
      this.fail(`Too many nested "[" (at most ${MAX_DEPTH} levels: sites, rows, entries)`);
    }
    this.pos++; // '['
    const items: Node[] = [];
    if (this.peek() === "]") {
      this.pos++;
      return items;
    }
    for (;;) {
      items.push(this.parseValue(depth));
      const c = this.peek();
      if (c === ",") {
        this.pos++;
        if (this.peek() === "]") {
          this.pos++;
          return items;
        }
        continue;
      }
      if (c === "]") {
        this.pos++;
        return items;
      }
      if (c === "") this.fail(`Unclosed "[" opened at character ${open + 1}: expected "," or "]"`);
      this.fail('Expected "," or "]"');
    }
  }

  /** One real or imaginary literal, returning its value and whether it had a j. */
  parseLiteral(): { value: number; imag: boolean } {
    this.skip();
    const start = this.pos;
    NUMBER.lastIndex = this.pos;
    const m = NUMBER.exec(this.text);
    const body = m ? m[0] : "";
    if (!/[0-9]/.test(body.replace(/[eE][+-]?[0-9]+$/, ""))) {
      this.fail("Expected a number", start);
    }
    // Reject forms like "1e" or "e5" that the regex could split oddly.
    if (/^[eE]/.test(body)) this.fail("Expected a number", start);
    this.pos = start + body.length;
    let imag = false;
    if (this.text[this.pos] === "j" || this.text[this.pos] === "J") {
      imag = true;
      this.pos++;
    }
    // A literal must not run straight into letters or digits (e.g. "1.2.3", "2x").
    const next = this.text[this.pos];
    if (next !== undefined && /[0-9A-Za-z_.]/.test(next)) this.fail("Unexpected character in number");
    const value = Number(body);
    if (!Number.isFinite(value)) {
      throw new LiteralError(`Number "${body}" at character ${start + 1} is too large`, start);
    }
    return { value, imag };
  }

  signedLiteral(): { value: number; imag: boolean } {
    let sign = 1;
    let c = this.peek();
    while (c === "-" || c === "+") {
      if (c === "-") sign = -sign;
      this.pos++;
      c = this.peek();
    }
    const lit = this.parseLiteral();
    return { value: sign * lit.value, imag: lit.imag };
  }

  parseComplex(): Complex {
    this.skip();
    const start = this.pos;
    if (this.text[this.pos] === "(") {
      this.pos++;
      const z = this.parseComplexBody();
      if (this.peek() !== ")") this.fail(`Expected ")" to close "(" at character ${start + 1}`);
      this.pos++;
      return z;
    }
    const c = this.text[this.pos] ?? "";
    if (c === "" || !/[0-9.+\-]/.test(c)) this.fail("Expected a number or \"[\"");
    return this.parseComplexBody();
  }

  parseComplexBody(): Complex {
    const first = this.signedLiteral();
    let re = first.imag ? 0 : first.value;
    let im = first.imag ? first.value : 0;
    const c = this.peek();
    if (!first.imag && (c === "+" || c === "-")) {
      // a+bj / a-bj : the second term must be imaginary.
      const opAt = this.pos;
      this.pos++;
      const sign = c === "-" ? -1 : 1;
      const second = this.parseLiteral();
      if (!second.imag) this.fail('Only "real + imaginary" sums like 0.4+0.25j are allowed', opAt);
      im = sign * second.value;
    }
    // Normalise negative zero so formatting stays tidy.
    re = re === 0 ? 0 : re;
    im = im === 0 ? 0 : im;
    return [re, im];
  }
}

function isComplex(node: Node): node is Complex {
  return node.length === 2 && typeof node[0] === "number";
}

/**
 * Parse the potential-matrix text into a K x L x L array of [re, im].
 * Empty text or "[]" means no potential sites. Throws LiteralError with a
 * position-specific message; shape against L and j_sites is checked by the
 * caller (and again by Python).
 */
export function parsePotential(text: string): Complex[][][] {
  const trimmed = text.trim();
  if (trimmed === "") return [];
  const p = new Parser(text);
  if (p.peek() !== "[") p.fail('The potential must start with "["');
  const root = p.parseValue() as Node[];
  if (p.peek() !== "") p.fail("Unexpected text after the closing \"]\"");

  const out: Complex[][][] = [];
  root.forEach((site, k) => {
    if (isComplex(site) || !Array.isArray(site)) {
      throw new LiteralError(`Site ${k + 1}: expected a matrix like [[v11, v12], [v21, v22]], found a number`, 0);
    }
    const rows: Complex[][] = [];
    (site as Node[]).forEach((row, r) => {
      if (isComplex(row)) {
        throw new LiteralError(`Site ${k + 1}, row ${r + 1}: expected a list of numbers, found a single number`, 0);
      }
      const cols: Complex[] = [];
      (row as Node[]).forEach((entry, c) => {
        if (!isComplex(entry)) {
          throw new LiteralError(`Site ${k + 1}, row ${r + 1}, entry ${c + 1}: expected a number, found a list`, 0);
        }
        cols.push(entry);
      });
      rows.push(cols);
    });
    const n = rows.length;
    rows.forEach((row, r) => {
      if (row.length !== n) {
        throw new LiteralError(
          `Site ${k + 1}: the matrix must be square; row ${r + 1} has ${row.length} entries but there are ${n} rows`,
          0,
        );
      }
    });
    out.push(rows);
  });
  return out;
}

function fmtReal(x: number): string {
  if (x === 0) return "0";
  const s = String(x);
  return s;
}

export function formatComplex([re, im]: Complex): string {
  if (im === 0) return fmtReal(re);
  if (re === 0) return `${fmtReal(im)}j`;
  return `${fmtReal(re)}${im < 0 ? "-" : "+"}${fmtReal(Math.abs(im))}j`;
}

/** Show a structured potential back in the desktop syntax. */
export function formatPotential(v: Complex[][][]): string {
  if (v.length === 0) return "[]";
  return `[${v.map((m) => `[${m.map((row) => `[${row.map(formatComplex).join(", ")}]`).join(", ")}]`).join(", ")}]`;
}
