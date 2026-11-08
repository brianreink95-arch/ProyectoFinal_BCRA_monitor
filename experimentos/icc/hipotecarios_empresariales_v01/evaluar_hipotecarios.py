"""Experimento empresarial 0.1. No modifica el piloto ni promueve modelos.

Reutiliza controles numéricos S1 con un adaptador explícito de población/tasa.
El campo interno tasa_uva_tna_pct es SOLO una interfaz del evaluador heredado;
se renombra en todas las matrices de salida como tasa_hipotecaria_nominal_pct.
"""
from pathlib import Path
import sys
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
import argparse, hashlib, json
import numpy as np
import pandas as pd
from ml import baseline as b, train as t, factor as fa, pca2

ROOT = Path(__file__).resolve().parent

def fuente(root, name):
    names = {'observaciones_api.csv': 'observaciones.csv'}
    return root.parent / 'series_v01' / 'fuentes' / names.get(name, name)
SEGMENTOS = {935: ('PyMEs',25,'Tasas_pers_jur_pymes'),
             936: ('No_PyMEs',26,'Tasas_pers_jur_otras')}

def fechas(codes):
    n=pd.to_numeric(codes,errors='coerce')
    ok=n.notna() & n.mod(100).between(1,12) & n.between(199001,209912) & n.eq(n.round())
    return pd.to_datetime(n.where(ok).astype('Int64').astype('string'),format='%Y%m',errors='coerce').dt.to_period('M').dt.to_timestamp('M')

def numerico(values):
    # Guiones y celdas vacías son ausencia, nunca tasa cero.
    return pd.to_numeric(values,errors='coerce').where(lambda x:x.ge(0))

def leer_fuentes(root):
    stocks=pd.read_excel(fuente(root,'perser_priv.xls'),sheet_name='Prest-Hip',header=None)
    if stocks.iloc[25,25]!='pes_jur_otr_pyme' or stocks.iloc[25,26]!='pes_jur_otr_res':
        raise ValueError('Cambió estructura del XLS de saldos')
    ipc=pd.read_csv(fuente(root,'deflactor_ipc.csv'))
    ipc['fecha_mes']=pd.to_datetime(ipc.fecha_mes)
    if ipc.fecha_mes.duplicated().any():raise ValueError('IPC duplicado')
    api=pd.read_csv(fuente(root,'observaciones_api.csv'));api['fecha']=pd.to_datetime(api.fecha)
    frames={};audit=[]
    for sid,(name,col,sheet) in SEGMENTOS.items():
        sx=pd.DataFrame({'fecha_mes':fechas(stocks[2]),'stock_nominal_millones_ars':numerico(stocks[col])/1000}).dropna(subset=['fecha_mes'])
        if sx.fecha_mes.duplicated().any():raise ValueError('Stock duplicado')
        sx=sx.set_index('fecha_mes')
        rates=pd.read_excel(fuente(root,'preser_tas.xls'),sheet_name=sheet,header=None)
        if 'Hipotecarios' not in rates.iloc[:25,29].astype(str).tolist():raise ValueError('Cambió estructura del XLS de tasas')
        rx=pd.DataFrame({'fecha_mes':fechas(rates[2]),'tasa_hipotecaria_nominal_pct':numerico(rates[29])}).dropna(subset=['fecha_mes'])
        if rx.fecha_mes.duplicated().any():raise ValueError('Tasa duplicada')
        rx=rx.set_index('fecha_mes')
        # Calendario completo: no comprimir huecos ni arrastrar valores.
        grid=pd.date_range('1999-12-31',max(sx.index.max(),rx.index.max()),freq='ME')
        f=sx.join(rx,how='outer').reindex(grid);f.index.name='fecha_mes'
        f=f.join(ipc.set_index('fecha_mes')[['factor_deflacion']])
        R=f.stock_nominal_millones_ars*f.factor_deflacion
        f[b.STOCK_REAL]=R;f[b.TASA]=f.tasa_hipotecaria_nominal_pct
        for k,key in [(1,b.G1),(3,b.G3),(12,'credito_var_real_12m_pct')]:
            complete=R.rolling(k+1,min_periods=k+1).count().eq(k+1)
            f[key]=(100*(R/R.shift(k)-1)).where(complete & R.shift(k).gt(0))
        f[b.DELTA_STOCK_REAL]=(R-R.shift(3)).where(R.rolling(4,min_periods=4).count().eq(4))
        f[b.DELTA]=(f[b.TASA]-f[b.TASA].shift(3)).where(f[b.TASA].rolling(4,min_periods=4).count().eq(4))
        f['credito_aceleracion_real_3m_pp']=f[b.G3]-f[b.G3].shift(3)
        f['credito_volatilidad_real_6m_pp']=f[b.G1].rolling(6,min_periods=6).std(ddof=0)
        for key in b.FEATURES_ICC:
            if key not in f:f[key]=np.nan
            f['motivo_'+key]=np.where(f[key].notna(),'','dato_o_historia_ausente')
        f['elegible_comparacion_2_0']=False;f['candidatas_completas']=False
        f['segmento']=name;f['serie_stock_equivalente']=sid
        f['fuente_stock']='perser_priv.xls/Prest-Hip';f['fuente_tasa']=sheet+'/columna_29'
        f['fecha_captura_tasa_utc']='2026-10-09';f['fecha_captura_tasa_buenos_aires']='2026-10-08';f['disponibilidad_historica_verificada']=False
        f=f.reset_index();f['fecha_mes']=f.fecha_mes.dt.strftime('%Y-%m-%d')
        frames[sid]=f
        a=api.loc[api.serie_id.eq(sid),['fecha','valor_original']].merge(sx.reset_index(),left_on='fecha',right_on='fecha_mes')
        a['serie_id']=sid;a['diferencia_api_menos_xls_millones']=a.valor_original-a.stock_nominal_millones_ars
        a['coincide_redondeo']=a.diferencia_api_menos_xls_millones.abs().le(.501)
        audit.append(a)
    return frames,pd.concat(audit,ignore_index=True)

def splits(frame):
    # Adaptador de validación propio: el validador PH exige fuentes/destinos PH.
    dates=pd.to_datetime(frame.fecha_mes)
    if dates.duplicated().any() or not dates.is_monotonic_increasing:raise ValueError('Calendario inválido')
    expected=pd.date_range(dates.min(),dates.max(),freq='ME')
    if not np.array_equal(dates.to_numpy(),expected.to_numpy()):raise ValueError('Hueco en calendario')
    return b._splits_por_fecha(frame.fecha_mes)

def salida_publica(frame):
    out=frame.drop(columns=['tasa_hipotecaria_nominal_pct'],errors='ignore').rename(columns={b.TASA:'tasa_hipotecaria_nominal_pct',b.DELTA:'tasa_hipotecaria_delta_3m_pp'})
    out=out.rename(columns={c:c.replace('tasa_uva','tasa_hipotecaria_nominal') for c in out.columns if 'tasa_uva' in c})
    return out

def vocabulario(obj):
    if isinstance(obj,dict):
        return {str(k).replace('tasa_uva_tna_pct','tasa_hipotecaria_nominal_pct').replace('tasa_uva_delta_3m_pp','tasa_hipotecaria_delta_3m_pp'):vocabulario(v) for k,v in obj.items()}
    if isinstance(obj,list):return [vocabulario(v) for v in obj]
    if isinstance(obj,tuple):return [vocabulario(v) for v in obj]
    if isinstance(obj,str):return obj.replace('tasa_uva_tna_pct','tasa_hipotecaria_nominal_pct').replace('tasa_uva_delta_3m_pp','tasa_hipotecaria_delta_3m_pp')
    return obj

def ejecutar(root=ROOT,output=None):
    root=Path(root);output=Path(output or root/'resultados');output.mkdir(parents=True,exist_ok=True)
    b.asignar_splits_icc=splits
    frames,audit=leer_fuentes(root);audit.to_csv(output/'auditoria_api_xls.csv',index=False)
    source={'experimento':'hipotecarios_empresariales_0.1','fuentes_reconstruidas':True,
            'hashes_codigo':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*.py'))},
            'hashes_fuentes':{name:hashlib.sha256(fuente(root,name).read_bytes()).hexdigest() for name in ['perser_priv.xls','deflactor_ipc.csv','observaciones_api.csv','preser_tas.xls']}}
    summary={}
    for sid,f in frames.items():
        dest=output/str(sid);dest.mkdir(exist_ok=True)
        salida_publica(f).to_csv(dest/'features.csv',index=False)
        methods={}
        for label,runner in [('pca1',t.entrenar_icc),('fa1',fa.entrenar_icc),('pca2',pca2.entrenar_icc)]:
            model,sc=runner(f,source)
            # El gate estadístico NO resuelve equivalencia económica de la tasa.
            gates=model.get('gates',model.get('controles_diagnosticos'))
            diagnostic={'controles':gates,'parametros':model.get('parametros_pca',model.get('parametros_factor',model.get('parametros_pca2'))),
                        'referencias':model['referencias'],'config':model.get('config_s1',model.get('config_fa',model.get('config_pca2'))),
                        'fuente':source,'serie_stock':sid,'tasa':'nominal ML fija/repactable por titular, no UVA',
                        'modelo_admitido_para_icc':False,'uso':'diagnóstico exploratorio; equivalencia de modalidad/población pendiente'}
            (dest/(label+'.json')).write_bytes(b.json_bytes(vocabulario(diagnostic)))
            sc=sc.rename(columns={'icc_indice':'icc_diagnostico_heredado'})
            sc['icc_aprobado']=False
            salida_publica(sc).to_csv(dest/(label+'_diagnostico.csv'),index=False)
            methods[label]={'controles_pasan':all(v['pasa'] for v in gates.values()),'fallos':[k for k,v in gates.items() if not v['pasa']]}
        refs=b.ajustar_referencias_icc(f)
        score=b.aplicar_baseline_icc(f,refs)
        score['icc_candidato_s1']=score.pop('icc_baseline_s1')
        score['icc_aprobado']=False;score['estado_producto']='experimental_proxy_nominal'
        # Descomposición exacta del nivel y cambio: orden simétrico en V/H.
        score['aporte_costo']=100*score.V_volumen*.8*score.C_costo
        score['aporte_momentum']=100*score.V_volumen*.2*score.M_momentum
        H=.8*score.C_costo+.2*score.M_momentum;V=score.V_volumen
        score['delta_icc']=score.icc_candidato_s1.diff()
        score['aporte_delta_volumen']=100*V.diff()*(H+H.shift(1))/2
        score['aporte_delta_costo']=100*(V+V.shift(1))/2*.8*score.C_costo.diff()
        score['aporte_delta_momentum']=100*(V+V.shift(1))/2*.2*score.M_momentum.diff()
        salida_publica(score).to_csv(dest/'icc_candidato.csv',index=False)
        last=score.loc[score.utilizable_baseline].iloc[-1]
        summary[str(sid)]={'referencias':refs,'metodos':methods,'ultimo':{'fecha':last.fecha_mes,'stock_real':float(last[b.STOCK_REAL]),'tasa':float(last[b.TASA]),'g3':float(last[b.G3]),'icc_candidato':float(last.icc_candidato_s1)},
                           'cobertura':{'cortes':b.CORTES_ICC,'meses_elegibles_por_split':b.comprobar_protocolo_icc(f)['meses_elegibles_por_split']},'pesos':{'costo':.8,'momentum':.2},'decision_pesos':'conservar como ancla de comparación; no optimizados ni aprobados'}
    (output/'resumen.json').write_bytes(b.json_bytes(vocabulario(summary)))
    print(json.dumps({sid:{'ultimo':v['ultimo'],'metodos':v['metodos']} for sid,v in summary.items()},ensure_ascii=False,indent=2))
    return frames,summary

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path);args=parser.parse_args()
    ejecutar(output=args.output)
