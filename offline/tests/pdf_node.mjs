// Extração de fragmentos com o pdf.js (mesma versão do HTML, build legacy para Node), para os testes.
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";
const here = path.dirname(fileURLToPath(import.meta.url));
const legacy = path.join(here, "..", "node_modules", "pdfjs-dist", "legacy", "build");
export async function extractFragments(bytes) {
  const lib = await import(pathToFileURL(path.join(legacy, "pdf.mjs")).href);
  lib.GlobalWorkerOptions.workerSrc = pathToFileURL(path.join(legacy, "pdf.worker.mjs")).href;
  const doc = await lib.getDocument({ data: new Uint8Array(bytes), isEvalSupported: false }).promise;
  const frags = [];
  for (let p = 1; p <= doc.numPages; p++) {
    const tc = await (await doc.getPage(p)).getTextContent();
    for (const it of tc.items) {
      const t = (it.str || "").trim();
      if (!t) continue;
      frags.push({ page: p, x: Math.round(it.transform[4] * 100) / 100, y: Math.round(it.transform[5] * 100) / 100, text: t });
    }
  }
  return { frags, nPages: doc.numPages };
}
