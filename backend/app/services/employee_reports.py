"""Small, dependency-free Excel exports and printable PDF reports."""
import csv
import io
from zipfile import ZipFile,ZIP_DEFLATED
from xml.sax.saxutils import escape
from fastapi.responses import Response
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4,landscape
from reportlab.platypus import SimpleDocTemplate,Table,TableStyle,Paragraph,Spacer
from reportlab.lib.styles import getSampleStyleSheet

COLUMNS={'master':['employee_code','name','father_name','phone','branch','client_name','site_name','designation','category','joining_date','status','joining_status','aadhaar_masked'],'attendance':['attendance_date','employee_code','name','branch','site_name','status','shift_hours','overtime_hours','night_shift','late_minutes','violation_type','verification_status'],'compliance':['employee_code','name','branch','status','joining_status','missing_documents','expiry_alerts']}


def safe_cell(value):
    value='' if value is None else str(value)
    return "'"+value if value.lstrip().startswith(('=','+','-','@')) else value


def xlsx_bytes(data):
    out=io.BytesIO()
    with ZipFile(out,'w',ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Employees" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        xml='<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
        for number,row in enumerate(data,1):
            xml+=f'<row r="{number}">'+''.join('<c t="inlineStr"><is><t xml:space="preserve">'+escape(safe_cell(v))+'</t></is></c>' for v in row)+'</row>'
        z.writestr('xl/worksheets/sheet1.xml',xml+'</sheetData></worksheet>')
    return out.getvalue()


def export_report(rows,kind,format):
    keys=COLUMNS[kind];headers=[k.replace('_',' ').title() for k in keys];data=[headers]+[[r.get(k) for k in keys] for r in rows]
    if format=='xlsx': body=xlsx_bytes(data);mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    elif format=='csv':
        out=io.StringIO();writer=csv.writer(out);writer.writerows([[safe_cell(v) for v in row] for row in data]);body=('\ufeff'+out.getvalue()).encode();mime='text/csv'
    else:
        out=io.BytesIO();styles=getSampleStyleSheet();style=styles['BodyText'];style.fontSize=6;style.leading=8
        printable=[[Paragraph(escape('' if x is None else str(x)),style) for x in row] for row in data]
        doc=SimpleDocTemplate(out,pagesize=landscape(A4),leftMargin=18,rightMargin=18)
        table=Table(printable,repeatRows=1,colWidths=[(landscape(A4)[0]-36)/len(keys)]*len(keys));table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dbeafe')),('GRID',(0,0),(-1,-1),.3,colors.lightgrey),('VALIGN',(0,0),(-1,-1),'TOP')]))
        doc.build([Paragraph('DestinLane — Employee '+kind.title()+' Report',styles['Heading2']),Spacer(1,12),table]);body=out.getvalue();mime='application/pdf'
    return Response(body,media_type=mime,headers={'Content-Disposition':f'attachment; filename="employee-{kind}.{format}"','Cache-Control':'no-store'})
