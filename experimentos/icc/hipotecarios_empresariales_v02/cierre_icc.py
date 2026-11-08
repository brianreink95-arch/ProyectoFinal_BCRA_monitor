"""ICC empresarial 0.2: contraste externo y aplicación de pesos decididos.

No ajusta pesos automáticamente, ni refitea referencias o modelos ML.
"""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent

def json_write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False)+'\n')

def extraer_ecc(root):
    p=root.parent/'series_v01/fuentes/ECC-Empresas.xlsx';rows=[]
    roman={'I':1,'II':2,'III':3,'IV':4}
    specs={'1':{'general':{'estandares':11},'grandes':{'estandares':23},'pymes':{'estandares':35}},
           '4':{'general':{'spread':12,'plazo':42,'garantias':52},'grandes':{'spread':75,'plazo':105,'garantias':115},'pymes':{'spread':138,'plazo':168,'garantias':178}},
           '6':{'general':{'demanda':11},'grandes':{'demanda':23},'pymes':{'demanda':35}}}
    for sheet,groups in specs.items():
        d=pd.read_excel(p,sheet_name=sheet,header=None)
        for group,dims in groups.items():
            for dim,row in dims.items():
                if 'ID ponderado por respuesta y entidad'!=d.iloc[row,0]:raise ValueError('Cambió estructura ECC')
                for col in range(4,d.shape[1]):
                    label=d.iloc[3,col]
                    r,y=str(label).split('-');quarter=pd.Period(f'{2000+int(y)}Q{roman[r]}',freq='Q')
                    value=pd.to_numeric(d.iloc[row,col],errors='coerce')
                    rows.append({'trimestre':str(quarter),'poblacion':group,'dimension':dim,'id_ecc':value,'hoja':sheet,'fila_excel':row+1,'columna_excel_numero':col+1,'tipo':'observado_ponderado'})
    out=pd.DataFrame(rows)
    if out.duplicated(['trimestre','poblacion','dimension']).any():raise ValueError('ECC duplicada')
    if out.id_ecc.dropna().abs().gt(100).any():raise ValueError('ID ECC fuera de rango')
    # Cotejo contra cifras publicadas del research, con redondeo a un decimal.
    def value(q,g,k):return out.query('trimestre==@q and poblacion==@g and dimension==@k').id_ecc.iloc[0]
    assert abs(value('2024Q2','general','estandares')-15.8)<.051
    assert abs(value('2024Q2','general','demanda')-26.3)<.051
    assert abs(value('2024Q1','general','demanda')+33)<.051
    assert abs(value('2026Q2','general','estandares')+2.6)<.051
    return out

def candidatos(root,weights):
    frames=[]
    for sid in [935,936]:
        f=pd.read_csv(root/'insumos'/f'icc_80_20_{sid}.csv',parse_dates=['fecha_mes']).set_index('fecha_mes')
        if f.index.duplicated().any() or not f.index.is_monotonic_increasing:raise ValueError('Calendario inválido')
        for alpha in weights:
            o=f.copy();o['serie_id']=sid;o['peso_costo']=alpha;o['peso_momentum']=1-alpha
            o['icc_indice']=100*o.V_volumen*(alpha*o.C_costo+(1-alpha)*o.M_momentum)
            if alpha==.8:np.testing.assert_allclose(o.icc_indice,o.icc_candidato_s1,atol=1e-10,equal_nan=True)
            o['delta_icc']=o.icc_indice.diff();v=o.V_volumen;h=alpha*o.C_costo+(1-alpha)*o.M_momentum
            o['aporte_costo']=100*v*alpha*o.C_costo;o['aporte_momentum']=100*v*(1-alpha)*o.M_momentum
            o['aporte_delta_volumen']=100*v.diff()*(h+h.shift(1))/2
            o['aporte_delta_costo']=100*(v+v.shift(1))/2*alpha*o.C_costo.diff()
            o['aporte_delta_momentum']=100*(v+v.shift(1))/2*(1-alpha)*o.M_momentum.diff()
            np.testing.assert_allclose(o.aporte_costo+o.aporte_momentum,o.icc_indice,atol=1e-10,equal_nan=True)
            np.testing.assert_allclose(o.aporte_delta_volumen+o.aporte_delta_costo+o.aporte_delta_momentum,o.delta_icc,atol=1e-10,equal_nan=True)
            if o.loc[o.index>='2026-07-01','icc_indice'].notna().any():raise ValueError('Reserva puntuada')
            frames.append(o.reset_index())
    return pd.concat(frames,ignore_index=True)

def pares_trimestrales(ecc,frames):
    pairs=[]
    for (sid,alpha),f in frames.groupby(['serie_id','peso_costo']):
        f=f.set_index('fecha_mes')
        ends=f.loc[f.index.month.isin([3,6,9,12]),['icc_indice']].copy()
        ends['delta_indice']=ends.icc_indice.diff();ends['trimestre']=ends.index.to_period('Q').astype(str)
        group='pymes' if sid==935 else 'grandes'
        e=ecc.loc[ecc.poblacion.eq(group)]
        merged=ends.merge(e,on='trimestre',how='left',validate='one_to_many')
        merged['serie_id']=sid;merged['peso_costo']=alpha
        pairs.append(merged.loc[merged.delta_indice.notna()&merged.id_ecc.notna()])
    return pd.concat(pairs,ignore_index=True)

def metricas(pairs,deadbands):
    rows=[]
    for (sid,alpha,dim),f in pairs.groupby(['serie_id','peso_costo','dimension']):
        for db in deadbands:
            nonneutral=f.id_ecc.abs().gt(5)
            signal=np.where(f.delta_indice.abs().le(db),0,np.sign(f.delta_indice))
            match=signal==np.sign(f.id_ecc)
            rows.append({'serie_id':sid,'peso_costo':alpha,'dimension':dim,'deadband':db,'n':len(f),
                         'rho':f.delta_indice.corr(f.id_ecc,method='spearman'),
                         'n_ecc_no_neutral':int(nonneutral.sum()),'coincidencias':int((match&nonneutral).sum()),
                         'concordancia_no_neutrales':float(match[nonneutral].mean()) if nonneutral.any() else None,
                         'fraccion_delta_icc_neutral':float((signal==0).mean())})
    return pd.DataFrame(rows)

def robustez(frames,pairs,protocol_prev):
    jitter=[];exclusions=[]
    for (sid,alpha),f in frames.groupby(['serie_id','peso_costo']):
        f=f.set_index('fecha_mes')
        for ev in protocol_prev['episodios']:
            for offset in [-1,0,1]:
                a=(pd.Timestamp(ev['desde']).to_period('M')+offset).to_timestamp('M')
                b=(pd.Timestamp(ev['hasta']).to_period('M')+offset).to_timestamp('M')
                va=f.loc[a,'icc_indice'] if a in f.index else np.nan;vb=f.loc[b,'icc_indice'] if b in f.index else np.nan
                jitter.append({'serie_id':sid,'peso_costo':alpha,'episodio':ev['id'],'offset_meses':offset,'desde':str(a.date()),'hasta':str(b.date()),'delta_indice':vb-va,'direccion_esperada':ev['direccion_esperada']})
    years=sorted({int(q[:4]) for q in pairs.trimestre})
    for label,start,end in [(ev['id'],pd.Timestamp(ev['desde']),pd.Timestamp(ev['hasta'])) for ev in protocol_prev['episodios']]+[(str(y),pd.Timestamp(y,1,1),pd.Timestamp(y,12,31)) for y in years]:
        periods=pd.PeriodIndex(pairs.trimestre,freq='Q').to_timestamp(how='end').normalize()
        keep=periods.year!=int(label) if label.isnumeric() else ~((periods>start)&(periods<=end))
        metrics=metricas(pairs.loc[keep],[1]);metrics['exclusion']=label;exclusions.append(metrics)
    return pd.DataFrame(jitter),pd.concat(exclusions,ignore_index=True)

def ejecutar(root,apply=False):
    protocol=json.loads((root/'protocolo_cierre.json').read_text());out=root/'resultados';out.mkdir(exist_ok=True)
    ecc=extraer_ecc(root);frames=candidatos(root,protocol['pesos_costo']);pairs=pares_trimestrales(ecc,frames)
    metrics=metricas(pairs,protocol['deadband_delta_icc_puntos'])
    previous=json.loads((root/'protocolo_episodios.json').read_text());jitter,exclusion=robustez(frames,pairs,previous)
    for name,data in [('ecc_normalizada',ecc),('pares_ecc_icc',pairs),('metricas_ecc',metrics),('robustez_cortes',jitter),('robustez_exclusiones',exclusion)]:data.to_csv(out/(name+'.csv'),index=False)
    if apply:
        decision=json.loads((root/'decision.json').read_text())
        for sid in [935,936]:
            alpha=decision['segmentos'][str(sid)]['peso_costo']
            if alpha not in protocol['pesos_costo']:raise ValueError('Peso no evaluado')
            f=frames.loc[frames.serie_id.eq(sid)&frames.peso_costo.eq(alpha)].copy()
            f=f.drop(columns=['icc_candidato_s1','version_baseline','estado_producto','icc_aprobado'],errors='ignore')
            f['version_indice']='empresarial_0.2';f['estado_producto']='cerrado_experimental'
            f['adoptado_descriptivo_interno']=True;f['uso_operativo_habilitado']=False;f['integracion_web_realizada']=False
            f['fecha_decision']=decision['fecha'];f.to_csv(out/f'icc_{sid}_v02.csv',index=False)
            refs=json.loads((root/'insumos'/f'referencias_{sid}.json').read_text())
            json_write(out/f'modelo_{sid}_v02.json',{'schema':'icc_empresarial_reglas_0.2','serie_id':sid,'peso_costo':alpha,'peso_momentum':1-alpha,'formula':f'100*V*({alpha:.2f}*C+{1-alpha:.2f}*M)','referencias':refs,'decision':decision,'costo':'proxy_tna_nominal_fija_repactable','metodo':'reglas_S1','no_es_modelo_ml_admitido':True})
    json_write(out/'procedencia.json',{'fecha_captura_ecc_utc':'2026-10-15','url_ecc':'https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/ECC/ECC-Empresas.xlsx','fuentes_compartidas':{'../series_v01/fuentes/ECC-Empresas.xlsx':hashlib.sha256((root.parent/'series_v01/fuentes/ECC-Empresas.xlsx').read_bytes()).hexdigest()},'hashes':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file() and 'resultados' not in p.parts and '__pycache__' not in p.parts}})
    print(metrics.query('deadband==1')[['serie_id','peso_costo','dimension','n','rho','n_ecc_no_neutral','coincidencias']].round(3).to_string(index=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');a=p.parse_args();ejecutar(ROOT,a.apply)
