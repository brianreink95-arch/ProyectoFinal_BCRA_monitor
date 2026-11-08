"""Estadísticas descriptivas previas a construir índices."""
from pathlib import Path
import numpy as np
import pandas as pd
from ejecutar import tabla,crecimiento

EPOCAS=[('2017_expansion','2016-12-31','2017-12-31'),
        ('2018_2019_contraccion','2017-12-31','2019-12-31'),
        ('2020_2021_pandemia','2019-12-31','2021-12-31'),
        ('2022_2023_inflacion','2021-12-31','2023-12-31'),
        ('2024_primer_trimestre','2023-12-31','2024-03-31'),
        ('2024_recuperacion','2024-03-31','2024-12-31'),
        ('2025','2024-12-31','2025-12-31'),('2026_1sem','2025-12-31','2026-06-30')]

def ejecutar_exploracion(root,out,frames,desc):
    rows=[];relations=[];jumps=[]
    for d in desc:
        if d['ya_cerrado']:continue
        f=frames[d['serie']]
        for name,a,b in EPOCAS:
            x=f.loc[a];y=f.loc[b]
            rows.append(dict(serie=d['serie'],familia=d['familia'],moneda=d['moneda'],epoca=name,
                             desde=a,hasta=b,R_desde=x.R,R_hasta=y.R,
                             variacion_R_pct=100*(y.R/x.R-1) if x.R>0 else None,
                             tasa_desde=x.tasa_pct,tasa_hasta=y.tasa_pct,
                             delta_tasa_pp=y.tasa_pct-x.tasa_pct))
        z=f.loc['2017-03-31':]
        for a,b in [('R','tasa_pct'),('g3_pct','tasa_pct'),('g3_pct','g1_pct'),('g3_pct','volatilidad_6m_pp')]:
            v=z[[a,b]].dropna()
            rho=v[a].rank().corr(v[b].rank()) if len(v)>2 and v[a].nunique()>1 and v[b].nunique()>1 else None
            relations.append(dict(serie=d['serie'],variable_a=a,variable_b=b,n=len(v),spearman=rho))
        for k in [0,1,3]:
            v=pd.concat([z.g3_pct,z.tasa_pct.shift(k)],axis=1).dropna()
            rho=v.iloc[:,0].rank().corr(v.iloc[:,1].rank()) if len(v)>2 and v.iloc[:,1].nunique()>1 else None
            relations.append(dict(serie=d['serie'],variable_a='g3_pct',variable_b=f'tasa_rezago_{k}',n=len(v),spearman=rho))
        for dt in z.g1_pct.abs().nlargest(3).index:
            jumps.append(dict(serie=d['serie'],fecha_mes=str(dt.date()),g1_pct=z.loc[dt,'g1_pct'],R=z.loc[dt,'R'],motivo='salto_a_revisar_no_identifica_causa'))
    pd.DataFrame(rows).to_csv(out/'epocas_stock_tasa.csv',index=False)
    pd.DataFrame(relations).to_csv(out/'relaciones_exploratorias.csv',index=False)
    pd.DataFrame(jumps).to_csv(out/'saltos_exploratorios.csv',index=False)
    destinations=[]
    for holder,sn in [('PH','fis'),('PJ_agregado','jur')]:
        raw=pd.read_excel(root/'fuentes/perser_dest.xls',sn,header=None)
        for mon,base in [('ML',31),('ME',48)]:
            t=tabla(raw,2,{'total':base,'automotores':base+1,'maquinarias':base+2,'otros':base+4})/1000
            for name in ['automotores','maquinarias','otros']:t['participacion_'+name+'_pct']=100*t[name]/t.total.where(t.total.gt(0))
            t['residual']=t.total-t[['automotores','maquinarias','otros']].sum(axis=1,min_count=3)
            t['titular']=holder;t['moneda']=mon;destinations.append(t)
    pd.concat(destinations).to_csv(out/'prendarios_destinos.csv',index_label='fecha_mes')
    # Tasas API como contraste: la media diaria no es un promedio por montos.
    api=pd.read_csv(root/'fuentes/observaciones.csv',parse_dates=['fecha'])
    rr=[]
    for sid in [14,1215,1218,1220]:
        t=api.loc[api.serie_id.eq(sid)].copy();t['fecha_mes']=t.fecha.dt.to_period('M').dt.to_timestamp('M')
        t=t.groupby('fecha_mes').valor_analitico.agg(['mean','count']).rename(columns={'mean':'tasa_api_pct','count':'n_observaciones'})
        t['serie_tasa_api']=sid;rr.append(t)
    pd.concat(rr).to_csv(out/'tasas_api_mensuales_contexto.csv',index_label='fecha_mes')

if __name__=='__main__':
    from ejecutar import ROOT,descriptors
    out=ROOT/'resultados';desc=pd.read_csv(out/'catalogo_auditado.csv',dtype={'serie':str}).to_dict('records')
    frames={d['serie']:pd.read_csv(out/'features'/f"{d['serie']}.csv",parse_dates=['fecha_mes']).set_index('fecha_mes') for d in desc}
    ejecutar_exploracion(ROOT,out,frames,desc)
    print('EDA por épocas, relaciones, saltos, destinos y tasas de contexto generados')
