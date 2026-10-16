#!/usr/bin/env python3
"""Refresh metadata for quantitative macros actually used in maintained manuscripts.

Numerical claims are resolved separately by make_claim_matrix.py from released
activity/emission/uncertainty products. This registry refresh never copies a
plotted numerical value into its expected value or manufactures missing claims.
"""
import csv,json,re
from pathlib import Path
root=Path(__file__).resolve().parents[1]
facts={r['macro']:r for r in csv.DictReader((root/'paper_national/figures/integrated_inputs/integrated_facts.csv').open())}
defs=dict(re.findall(r'\\newcommand\{\\(\w+)\}\{([^{}]+)\}',(root/'paper_national/versions/v3/generated/integrated_facts.tex').read_text()))
registry=root/'data/shared/evidence/claim_matrix.csv'
fields=next(csv.reader(registry.open()))
def central(f,period=None):
 p=period or f['period'];s=f['species'];cfg='S_TAN'
 if s in ('CO2','CH4','N2O','AR5','AR6'):
  col='co2e_Mt_'+s if s in ('AR5','AR6') else 'emission_native_mass'
  key=f'period_id={p},configuration_id={cfg}' + (',gas='+s if s not in ('AR5','AR6') else '')
  expr='sum_where:pakemis_ghg_configuration_atoms.csv#'+key+'#'+col
  return 'scale:0.001|'+expr if s=='CO2' else expr
 return 'sum_where:pakemis_air_annual_fy2015_16_fy2024_25.csv#period_id='+p+',configuration_id='+cfg+',pollutant='+s+'#emissions_Gg'
def pointer(f):
 m=f['macro'];p=f['period'];s=f['species']
 if 'NPartition' in m:
  key='period_id='+p+',configuration_id=S_TAN,scenario_id=nitrogen_all_volatilised_n_as_nh3_diagnostic'
  if s in ('CO2e_AR5','CO2e_AR6'):
   return 'pakemis_nitrogen_partition_sensitivity.csv#'+key+',metric='+s+'#change_quantity'
  return 'pakemis_air_structural_sensitivities.csv#'+key+',pollutant='+s+'#change_Gg'
 if m.startswith('PakChange'):return 'change_pct:'+central(f,'FY2015-16')+'|'+central(f,'FY2024-25')
 if m.startswith('PakDungCase'):
  return 'pakemis_air_structural_sensitivities.csv#period_id='+p+',configuration_id=S_TAN,pollutant='+s+',scenario_id=all_diverted_dung_household_combustion#case_covered_Gg'
 for suffix,quant in [('Low','P2_5'),('Median','P50'),('High','P97_5')]:
  if m.endswith(suffix):
   ghg=s=='AR5';filename='pakemis_ghg_conditional_uncertainty.csv' if ghg else 'pakemis_air_conditional_uncertainty.csv'
   key='species_or_metric=CO2e_AR5' if ghg else 'pollutant='+s
   return filename+'#period_id='+p+',configuration_id=S_TAN,sector_id=national_covered,dependence_case=persistent_parameters,'+key+'#'+quant+('_quantity' if ghg else '_Gg')
 return central(f)
rows=[]
def manuscript_sources():
 paths=set()
 for entry in ('versions/v3/paper.tex','versions/v3/technical_supplement.tex',
               'versions/v1/paper_national.tex','versions/v1/supplement.tex'):
  start=root/'paper_national'/entry
  def visit(path):
   if path in paths or not path.is_file() or 'generated' in path.parts:return
   paths.add(path)
   text=re.sub(r'(?m)^\s*%.*$','',path.read_text())
   for name in re.findall(r'\\(?:input|include)\{([^}]+)\}',text):
    if '#' in name:continue
    for parent in (start.parent,path.parent):
     candidate=parent/name
     if not candidate.suffix:candidate=candidate.with_suffix('.tex')
     if candidate.is_file():visit(candidate.resolve());break
  visit(start.resolve())
 return sorted(paths)
paths=manuscript_sources()
for path in paths:
 text=re.sub(r'(?m)^\s*%.*$','',path.read_text())
 for name in sorted(set(re.findall(r'\\(\w+)',text)) & set(defs)):
  target=name;seen=set()
  while defs[target].startswith('\\') and target not in seen:seen.add(target);target=defs[target][1:]
  if target not in facts:continue
  f=facts[target];row=dict.fromkeys(fields,'')
  row.update(claim_id=path.stem+'_'+name,essd_section='4',section_file=str(path.relative_to(root)),claim_text='\\'+name,
   printed_pattern='macro:'+name,quantity_refs='macro:'+target,source_product_id='integrated_release',source_pointer=pointer(f),
   configuration='S_TAN',unit=f['unit'],rounding='1' if target.startswith('PakChange') else 'sig:4',
   evidence_class='parametric' if target.endswith(('Low','Median','High')) else ('structural' if target.startswith('PakDungCase') or 'NPartition' in target else 'estimated-mixed'),
   limitation_ref='sec:uncertainty' if target.endswith(('Low','Median','High')) else 'sec:scope')
  rows.append(row)
with registry.open('w',newline='') as h:w=csv.DictWriter(h,fields);w.writeheader();w.writerows(rows)
print('current manuscript macro claims',len(rows))
