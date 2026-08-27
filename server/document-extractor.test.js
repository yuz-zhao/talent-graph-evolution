import test from 'node:test'
import assert from 'node:assert/strict'
import { writeFileSync, rmSync, mkdtempSync } from 'fs'
import { tmpdir } from 'os'
import { join } from 'path'
import { PDFDocument, StandardFonts } from 'pdf-lib'
import { extractPdf, extractPdfOcr, extractionQuality, orderedPageBlocks, parseDocxHtml, removeRepeatedPageArtifacts } from './document-extractor.js'

test('extracts native PDF blocks with page coordinates', async () => {
  const pdf=await PDFDocument.create(),page=pdf.addPage([600,800]),font=await pdf.embedFont(StandardFonts.Helvetica)
  page.drawText('PROJECT EXPERIENCE',{x:50,y:730,size:14,font});page.drawText('Built a Python and Docker service.',{x:50,y:700,size:12,font})
  const dir=mkdtempSync(join(tmpdir(),'talentgraph-pdf-')),path=join(dir,'native-layout-test.pdf');writeFileSync(path,await pdf.save())
  try { const result=await extractPdf(path,'eng');assert.equal(result.extraction_method,'pdf_text_layer');assert.ok(result.blocks.every(x=>Number.isFinite(x.x)&&Number.isFinite(x.y)));assert.match(result.blocks.map(x=>x.text).join(' '),/Python/) } finally { rmSync(dir,{recursive:true,force:true}) }
})

test('loads project Chinese OCR language pack', () => {
  const result=extractPdfOcr('not-used.pdf','chi_sim+eng')
  assert.notEqual(result.ocr_status,'language_missing')
})

test('preserves DOCX headings, lists, paragraphs and table cells', () => {
  const blocks=parseDocxHtml('<h1>项目经历</h1><p>推荐系统</p><ul><li>使用 Python</li></ul><table><tr><th>技能</th><td>Docker</td></tr></table>')
  assert.deepEqual(blocks.map(x=>x.document_role),['heading','paragraph','list_item','table_cell','table_cell'])
  assert.equal(blocks[0].heading_level,1)
})

test('orders a complex two-column PDF down the left column before the right', () => {
  const item=(str,x,y)=>({str,width:40,height:10,transform:[1,0,0,1,x,y]})
  const blocks=orderedPageBlocks([item('L2',40,650),item('R1',360,700),item('L1',40,700),item('R3',360,600),item('L3',40,600),item('R2',360,650)],1,600)
  assert.deepEqual(blocks.map(x=>x.text),['L1','L2','L3','R1','R2','R3'])
})

test('keeps right-aligned resume annotations in row reading order', () => {
  const item=(str,x,y,width=40)=>({str,width,height:10,transform:[1,0,0,1,x,y]})
  const blocks=orderedPageBlocks([
    item('项目一',50,300),item('2023-2024',430,300),
    item('项目描述',60,280,280),item('90%',430,280),
    item('项目二',50,200),item('2022-2023',430,200),
  ],1,600)
  assert.deepEqual(blocks.map(x=>x.text),['项目一','2023-2024','项目描述','90%','项目二','2022-2023'])
})

test('removes repeated page headers and footers without dropping body text', () => {
  const blocks=[1,2].flatMap(page=>[{page,y:790,text:'张伟｜个人简历'},{page,y:400,text:`第${page}页正文`},{page,y:20,text:'机密'}])
  assert.deepEqual(removeRepeatedPageArtifacts(blocks,2).map(x=>x.text),['第1页正文','第2页正文'])
})

test('gates low-confidence OCR for human confirmation', () => {
  const quality=extractionQuality([{character_confidence:.42},{character_confidence:.61},{character_confidence:.88}])
  assert.equal(quality.status,'low')
  assert.equal(quality.requires_human_confirmation,true)
})
