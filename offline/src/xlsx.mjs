// Leitura e escrita mínimas de .xlsx, sem bibliotecas (funciona offline e no Node 18+).
// Leitura: zip (DecompressionStream "deflate-raw") + XML por expressões regulares.
// Escrita: zip sem compressão (STORE) com strings inline. Só o que o simulador precisa.
import { D } from "./engine.mjs";

const u16 = (b, o) => b[o] | (b[o + 1] << 8);
const u32 = (b, o) => (b[o] | (b[o + 1] << 8) | (b[o + 2] << 16) | (b[o + 3] << 24)) >>> 0;
const dec = new TextDecoder("utf-8");

async function inflateRaw(data) {
  const ds = new DecompressionStream("deflate-raw");
  const out = new Response(new Blob([data]).stream().pipeThrough(ds));
  return new Uint8Array(await out.arrayBuffer());
}
export async function unzip(bytes) {
  const b = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  let eocd = -1;
  for (let i = b.length - 22; i >= Math.max(0, b.length - 65557); i--) if (u32(b, i) === 0x06054b50) { eocd = i; break; }
  if (eocd < 0) throw new Error("arquivo não é um .xlsx (zip) válido");
  const n = u16(b, eocd + 10);
  let p = u32(b, eocd + 16);
  const files = new Map();
  for (let k = 0; k < n; k++) {
    if (u32(b, p) !== 0x02014b50) throw new Error("diretório do zip corrompido");
    const method = u16(b, p + 10), csize = u32(b, p + 20), nlen = u16(b, p + 28), xlen = u16(b, p + 30), clen = u16(b, p + 32), off = u32(b, p + 42);
    const name = dec.decode(b.subarray(p + 46, p + 46 + nlen));
    const lstart = off + 30 + u16(b, off + 26) + u16(b, off + 28);
    const raw = b.subarray(lstart, lstart + csize);
    files.set(name, method === 0 ? raw : method === 8 ? await inflateRaw(raw) : null);
    p += 46 + nlen + xlen + clen;
  }
  return files;
}

const unesc = (s) => s.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&apos;/g, "'")
  .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(Number(n))).replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCodePoint(parseInt(n, 16))).replace(/&amp;/g, "&");
const attr = (tag, name) => { const m = tag.match(new RegExp(`\\b${name}="([^"]*)"`)); return m ? unesc(m[1]) : null; };
const allT = (xml) => [...xml.matchAll(/<t(?:\s[^>]*)?>([\s\S]*?)<\/t>/g)].map((m) => unesc(m[1])).join("");
function colIndex(ref) { let n = 0; for (const ch of ref.replace(/\d+/g, "")) n = n * 26 + (ch.charCodeAt(0) - 64); return n - 1; }
const EXCEL_EPOCH = D(1899, 12, 30);
function isDateFormat(id, code) {
  if ((id >= 14 && id <= 22) || (id >= 45 && id <= 47)) return true;
  if (!code) return false;
  const c = code.replace(/"[^"]*"/g, "").replace(/\[[^\]]*\]/g, "").toLowerCase();
  return /[dy]/.test(c) || (/m/.test(c) && !/[0#]/.test(c));
}

/** Lê um .xlsx -> [{name, rows}] com valores: número, texto, booleano ou {dn} (data). */
export async function readXlsx(bytes) {
  const files = await unzip(bytes);
  const get = (n) => { const f = files.get(n) || files.get(n.replace(/^\//, "")); return f ? dec.decode(f) : null; };
  const ss = get("xl/sharedStrings.xml");
  const shared = ss ? [...ss.matchAll(/<si>([\s\S]*?)<\/si>/g)].map((m) => allT(m[1])) : [];
  const styles = get("xl/styles.xml") || "";
  const fmts = Object.fromEntries([...styles.matchAll(/<numFmt\b[^>]*>/g)].map((m) => [Number(attr(m[0], "numFmtId")), attr(m[0], "formatCode")]));
  const cellXfs = (styles.match(/<cellXfs\b[\s\S]*?<\/cellXfs>/) || [""])[0];
  const xfDate = [...cellXfs.matchAll(/<xf\b[^>]*>/g)].map((m) => { const id = Number(attr(m[0], "numFmtId") || 0); return isDateFormat(id, fmts[id]); });
  const wb = get("xl/workbook.xml") || "";
  const rels = get("xl/_rels/workbook.xml.rels") || "";
  const relMap = Object.fromEntries([...rels.matchAll(/<Relationship\b[^>]*>/g)].map((m) => [attr(m[0], "Id"), attr(m[0], "Target")]));
  const sheets = [];
  for (const m of wb.matchAll(/<sheet\b[^>]*>/g)) {
    const name = attr(m[0], "name"), rid = attr(m[0], "r:id");
    let target = relMap[rid] || "";
    target = target.startsWith("/") ? target.slice(1) : `xl/${target}`;
    const xml = get(target);
    if (!xml) continue;
    const rows = [];
    for (const rm of xml.matchAll(/<row\b([^>]*)>([\s\S]*?)<\/row>|<row\b([^>]*)\/>/g)) {
      const rtag = rm[1] ?? rm[3] ?? "";
      const r = Number(attr(`<row ${rtag}>`, "r")) - 1;
      const row = [];
      for (const cm of (rm[2] || "").matchAll(/<c\b([^>]*?)(?:\/>|>([\s\S]*?)<\/c>)/g)) {
        const ctag = `<c ${cm[1]}>`, inner = cm[2] || "";
        const ref = attr(ctag, "r"), t = attr(ctag, "t"), s = Number(attr(ctag, "s") || 0);
        const vm = inner.match(/<v>([\s\S]*?)<\/v>/);
        let v = null;
        if (t === "s") v = vm ? shared[Number(vm[1])] ?? null : null;
        else if (t === "inlineStr") v = allT(inner);
        else if (t === "str") v = vm ? unesc(vm[1]) : null;
        else if (t === "b") v = vm ? vm[1] === "1" : null;
        else if (t === "e") v = null;
        else if (vm) { const num = Number(vm[1]); v = xfDate[s] ? { dn: EXCEL_EPOCH + Math.floor(num) } : num; }
        row[ref ? colIndex(ref) : row.length] = v;
      }
      rows[r] = row;
    }
    sheets.push({ name, rows });
  }
  return sheets;
}

// ------------------------------------------------------------------------------- escrita
const CRC_TABLE = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
function crc32(b) { let c = 0xffffffff; for (let i = 0; i < b.length; i++) c = CRC_TABLE[(c ^ b[i]) & 0xff] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; }
function zipStore(entries) {
  const enc = new TextEncoder(), parts = [], central = [];
  let off = 0;
  const w16 = (v) => [v & 0xff, (v >>> 8) & 0xff], w32 = (v) => [v & 0xff, (v >>> 8) & 0xff, (v >>> 16) & 0xff, (v >>> 24) & 0xff];
  for (const [name, text] of entries) {
    const nb = enc.encode(name), data = enc.encode(text), crc = crc32(data);
    const local = new Uint8Array([...w32(0x04034b50), ...w16(20), ...w16(0x0800), ...w16(0), ...w16(0), ...w16(0x21), ...w32(crc), ...w32(data.length), ...w32(data.length), ...w16(nb.length), ...w16(0)]);
    parts.push(local, nb, data);
    central.push(new Uint8Array([...w32(0x02014b50), ...w16(20), ...w16(20), ...w16(0x0800), ...w16(0), ...w16(0), ...w16(0x21), ...w32(crc), ...w32(data.length), ...w32(data.length), ...w16(nb.length), ...w16(0), ...w16(0), ...w16(0), ...w16(0), ...w32(0), ...w32(off)]), nb);
    off += local.length + nb.length + data.length;
  }
  const csize = central.reduce((s, x) => s + x.length, 0);
  const end = new Uint8Array([...w32(0x06054b50), ...w16(0), ...w16(0), ...w16(entries.length), ...w16(entries.length), ...w32(csize), ...w32(off), ...w16(0)]);
  const all = [...parts, ...central, end];
  const out = new Uint8Array(all.reduce((s, x) => s + x.length, 0));
  let p = 0; for (const x of all) { out.set(x, p); p += x.length; }
  return out;
}
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, "");
const colName = (i) => { let s = ""; i += 1; while (i) { const m = (i - 1) % 26; s = String.fromCharCode(65 + m) + s; i = Math.floor((i - 1) / 26); } return s; };

/** sheets: [{name, rows: [[...]]}] (primeira linha = cabeçalho, em negrito). */
export function writeXlsx(sheets) {
  const sheetXml = (rows) => {
    const body = rows.map((row, r) => `<row r="${r + 1}">` + row.map((v, c) => {
      if (v == null || v === "" || (typeof v === "number" && !Number.isFinite(v))) return "";
      const ref = `${colName(c)}${r + 1}`, st = r === 0 ? ' s="1"' : "";
      return typeof v === "number" ? `<c r="${ref}"${st}><v>${v}</v></c>` : `<c r="${ref}" t="inlineStr"${st}><is><t xml:space="preserve">${esc(v)}</t></is></c>`;
    }).join("") + "</row>").join("");
    return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>${body}</sheetData></worksheet>`;
  };
  const names = sheets.map((s, i) => esc(String(s.name).replace(/[\\/?*[\]:]/g, " ").slice(0, 31) || `Plan${i + 1}`));
  const entries = [
    ["[Content_Types].xml", `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>${sheets.map((_, i) => `<Override PartName="/xl/worksheets/sheet${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`).join("")}</Types>`],
    ["_rels/.rels", `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>`],
    ["xl/workbook.xml", `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>${names.map((n, i) => `<sheet name="${n}" sheetId="${i + 1}" r:id="rId${i + 1}"/>`).join("")}</sheets></workbook>`],
    ["xl/_rels/workbook.xml.rels", `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${sheets.map((_, i) => `<Relationship Id="rId${i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${i + 1}.xml"/>`).join("")}<Relationship Id="rId${sheets.length + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>`],
    ["xl/styles.xml", `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="2"><xf fontId="0"/><xf fontId="1" applyFont="1"/></cellXfs></styleSheet>`],
    ...sheets.map((s, i) => [`xl/worksheets/sheet${i + 1}.xml`, sheetXml(s.rows)]),
  ];
  return zipStore(entries);
}
/** Converte lista de objetos (linhas de tabela) em matriz com cabeçalho. */
export function rowsFromObjects(objs) {
  const cols = []; for (const o of objs) for (const k of Object.keys(o)) if (!cols.includes(k)) cols.push(k);
  return [cols, ...objs.map((o) => cols.map((c) => o[c] ?? null))];
}
