process.env.NODE_ENV = "production"

import fs from "fs"
import path from "path"
import { JSDOM } from "jsdom"

import { generateInvoice } from "./ksef-pdf-generator/dist/ksef-fe-invoice-converter.js";

const dom = new JSDOM("", { pretendToBeVisual: true });

global.window = dom.window;
global.document = dom.window.document;
global.FileReader = dom.window.FileReader;
global.Blob = dom.window.Blob;
global.File = dom.window.File;

const input = process.argv[2];
const output = process.argv[3];

if (!input || !output) {
  console.error("Usage: node render_invoice.mjs input.xml output.pdf");
  process.exit(1);
}

async function run() {

  const xmlBuffer = fs.readFileSync(input);

  const file = new File(
    [xmlBuffer],
    path.basename(input),
    { type: "text/xml" }
  );

  const pdfBase64 = await generateInvoice(
    file,
    {},
    "base64"
  );

  const pdfBuffer = Buffer.from(pdfBase64, "base64");

  fs.writeFileSync(output, pdfBuffer);

  console.log("PDF generated:", output);
}

run();
