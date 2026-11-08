"""Auditoría y EDA reproducibles. Fuentes locales congeladas, sin red ni imputación."""
from pathlib import Path
import argparse, hashlib, json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ROOT = Path(__file__).resolve().parent
GRID = pd.date_range('1999-12-31', '2026-06-30', freq='ME')
TRAIN = ('2017-03-31', '2022-02-28')
VALID = ('2022-03-31', '2023-12-31')
RETRO = ('2024-01-31', '2026-06-30')
TITULARES = {17:'PH',19:'Prestadoras',25:'PyMEs',26:'No_PyMEs'}
RATE_SHEETS = {'PH':'Tasas_personas_fisicas','PyMEs':'Tasas_pers_jur_pymes',
               'No_PyMEs':'Tasas_pers_jur_otras','Privado':'Tasas_sector_privado'}
AMT_NAMES = {'PH':'fisicas','PyMEs':'jur_pymes','No_PyMEs':'jur_otras','Privado':'sector_privado'}
COLS = {'Hipotecarios':(29,51),'Prendarios':(37,67),'Personales':(49,91),'Tarjetas':(56,104)}

def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)+'\n')

def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def fechas(values, decimal=False):
    n=pd.to_numeric(values,errors='coerce')
    if decimal:n=(n*100).round()
    ok=n.between(199001,209912)&n.mod(100).between(1,12)&n.eq(n.round())
    return pd.to_datetime(n.where(ok).astype('Int64').astype('string'),format='%Y%m',errors='coerce').dt.to_period('M').dt.to_timestamp('M')

def num(values):
    return pd.to_numeric(values,errors='coerce').where(lambda v:v.ge(0))

def tabla(df, date_col, value_cols, decimal=False):
    out=pd.DataFrame({'fecha_mes':fechas(df[date_col],decimal),**{k:num(df[c]) for k,c in value_cols.items()}}).dropna(subset=['fecha_mes'])
    if out.fecha_mes.duplicated().any():raise ValueError('Fecha duplicada en fuente')
    return out.set_index('fecha_mes').sort_index()

def crecimiento(s,k):
    complete=s.rolling(k+1,min_periods=k+1).count().eq(k+1)
    return (100*(s/s.shift(k)-1)).where(complete&s.shift(k).gt(0))

def split(dates):
    out=pd.Series('fuera_protocolo',index=dates)
    for name,(a,b) in [('train',TRAIN),('validacion',VALID),('retrospectiva',RETRO)]:
        out.loc[(dates>=a)&(dates<=b)]=name
    out.loc[dates>='2026-07-01']='reserva'
    return out

def load_sources(root):
    src=root/'fuentes'
    stocks={s:pd.read_excel(src/'perser_priv.xls',s,header=None) for s in ['Prest-Tot','Prest-Hip','Prest-Prend']}
    rates={s:pd.read_excel(src/'preser_tas.xls',s,header=None) for s in RATE_SHEETS.values()}
    amounts={s:pd.read_excel(src/'preser_mon.xls',s,header=None) for s in pd.ExcelFile(src/'preser_mon.xls').sheet_names if s!='Observaciones'}
    fx=pd.read_excel(src/'com3500.xls','TCR diario y TCNPM',header=None)
    # Solamente fechas reales del XLS, nunca el promedio TCNPM.
    fx=pd.DataFrame({'fecha_tc':pd.to_datetime(fx[2],errors='coerce',format='mixed'),'tc_a3500':num(fx[3])}).dropna()
    fx=fx.loc[fx.fecha_tc.le(GRID.max())]
    if fx.fecha_tc.duplicated().any():raise ValueError('FX duplicado')
    fx['fecha_mes']=fx.fecha_tc.dt.to_period('M').dt.to_timestamp('M')
    fx=fx.sort_values('fecha_tc').groupby('fecha_mes').tail(1).set_index('fecha_mes')
    fx['antiguedad_cierre_dias']=(fx.index.to_series()-fx.fecha_tc).dt.days
    if fx.antiguedad_cierre_dias.gt(7).any():raise ValueError('FX de cierre demasiado antiguo')
    ipc=pd.read_csv(src/'deflactor_ipc.csv',parse_dates=['fecha_mes']).set_index('fecha_mes')
    assert np.allclose(ipc.factor_deflacion,100/ipc.ipc_nacional)
    api=pd.read_csv(src/'observaciones.csv',parse_dates=['fecha'])
    return stocks,rates,amounts,fx,ipc,api

def get_rate(rates,amounts,family,holder,currency):
    if holder not in RATE_SHEETS:return pd.DataFrame(index=GRID)
    rs=RATE_SHEETS[holder];rc,ac=COLS[family]
    if currency=='ME':rc+=63
    raw=rates[rs]
    expected={'Hipotecarios':'Hipotecarios','Prendarios':'Prendarios','Personales':'Personales','Tarjetas':'Sistema de tarjetas de crédito'}[family]
    # Tarjetas 56/119 es la columna no cero dentro del bloque encabezado 55/118.
    header_col=rc-1 if family=='Tarjetas' else rc
    if expected not in ' '.join(raw[header_col].iloc[18:22].dropna().astype(str)):
        raise ValueError('Estructura de tasas no reconocida')
    rt=tabla(raw,2,{'tasa_publicada_pct':rc})
    am='Montos_'+('$' if currency=='ML' else 'u$s')+'_'+AMT_NAMES[holder]
    at=tabla(amounts[am],2,{'monto_operado_publicado':ac})
    result=rt.join(at).reindex(GRID)
    result['monto_publicado_cero']=result.monto_operado_publicado.eq(0)
    result['monto_no_disponible']=result.monto_operado_publicado.isna()
    result['monto_cero_tasa_positiva']=result.monto_publicado_cero & result.tasa_publicada_pct.gt(0)
    # El monto se publica redondeado. Cero junto con tasa positiva no prueba
    # ausencia de operaciones: conservar la tasa y marcar la discrepancia.
    # Cero en ambos campos es ambiguo y no se interpreta como crédito gratuito.
    interpretable=result.tasa_publicada_pct.gt(0) | result.monto_operado_publicado.gt(0)
    result['tasa_cero_sin_soporte']=result.tasa_publicada_pct.eq(0)&~result.monto_operado_publicado.gt(0)
    result['tasa_pct']=result.tasa_publicada_pct.where(interpretable)
    result['fuente_tasa']=rs+f'/columna_{rc}'
    result['fuente_monto']=am+f'/columna_{ac}'
    return result

def descriptors():
    desc=[]
    specs=[('Hipotecarios','Prest-Hip','ML',[927,929,935,936]),
           ('Hipotecarios','Prest-Hip','ME',[938,940,946,947]),
           ('Prendarios','Prest-Prend','ML',[960,962,968,969]),
           ('Prendarios','Prest-Prend','ME',[971,973,979,980]),
           ('Total','Prest-Tot','MEyML',[883,885,891,892])]
    for fam,sheet,mon,ids in specs:
        for col,sid in zip(TITULARES,ids):
            c=col+(13 if mon=='ME' else -13 if mon=='MEyML' else 0)
            desc.append(dict(serie=str(sid),familia=fam,titular=TITULARES[col],moneda=mon,
                             hoja_stock=sheet,col_stock=c,origen='perser_priv',
                             agregado='saldo_fin_mes',unidad_fuente='miles_ARS',
                             ya_cerrado=sid in [927,935,936]))
    for fam,col in [('Personales',29),('Tarjetas',30)]:
        for mon in ['ML','ME']:
            desc.append(dict(serie=f'finserprom_{fam.lower()}_{mon.lower()}_privado',familia=fam,
                             titular='Privado',moneda=mon,hoja_stock='Sector_privado',
                             col_stock=col+(17 if mon=='ME' else 0),origen='finserprom',
                             agregado='promedio_mensual_saldos_diarios',
                             unidad_fuente='millones_USD_equivalentes' if mon=='ME' else 'millones_ARS',ya_cerrado=False))
    return desc

def eda(root=ROOT,output=None):
    output=Path(output or root/'resultados');output.mkdir(parents=True,exist_ok=True)
    (output/'features').mkdir(exist_ok=True)
    stocks,rates,amounts,fx,ipc,api=load_sources(root)
    fin=pd.read_excel(root/'fuentes/finserprom.xls','Sector_privado',header=None)
    assert 'millones de pesos' in fin.iat[15,20]
    assert 'millones de dólares' in fin.iat[15,37]
    desc=descriptors();frames={};audit=[];quality=[]
    for d in desc:
        sid=d['serie'];fam=d['familia'];mon=d['moneda'];holder=d['titular']
        if d['origen']=='perser_priv':
            raw=stocks[d['hoja_stock']]
            assert 'miles de pesos' in raw.iat[17,3]
            sx=tabla(raw,2,{'stock_nominal_millones_ars':d['col_stock']})/1000
            a=api.loc[api.serie_id.eq(int(sid)),['fecha','valor_original']].merge(sx,left_on='fecha',right_index=True)
            a['serie']=sid;a['xls_miles_original']=a.stock_nominal_millones_ars*1000
            a['diferencia_api_millones']=a.valor_original-a.stock_nominal_millones_ars
            a['coincide_redondeo']=a.diferencia_api_millones.abs().le(.501)
            a['api_cero_xls_positivo']=a.valor_original.eq(0)&a.stock_nominal_millones_ars.gt(0)
            audit.append(a)
        else:
            key='stock_usd_equivalentes_millones' if mon=='ME' else 'stock_nominal_millones_ars'
            sx=tabla(fin,2,{key:d['col_stock']},decimal=True)
        f=sx.reindex(GRID).join(ipc[['factor_deflacion']]).join(fx[['tc_a3500','fecha_tc','antiguedad_cierre_dias']])
        if 'stock_nominal_millones_ars' not in f:f['stock_nominal_millones_ars']=np.nan
        if mon=='ME':
            if 'stock_usd_equivalentes_millones' not in f:
                f['stock_usd_equivalentes_millones']=f.stock_nominal_millones_ars/f.tc_a3500
            f['R']=f.stock_usd_equivalentes_millones
            d['unidad_R']='millones_USD_equivalentes_nominales'
            if d['origen']=='perser_priv':
                q=f.stock_usd_equivalentes_millones;e=f.tc_a3500
                f['delta_ars']=f.stock_nominal_millones_ars.diff()
                f['delta_ars_por_volumen']=q.diff()*e.shift(1)
                f['delta_ars_por_tc']=e.diff()*q.shift(1)
                f['delta_ars_interaccion']=q.diff()*e.diff()
                f['residual_fx']=f.delta_ars-f[['delta_ars_por_volumen','delta_ars_por_tc','delta_ars_interaccion']].sum(axis=1,min_count=3)
        else:
            f['R']=f.stock_nominal_millones_ars*f.factor_deflacion
            d['unidad_R']='millones_ARS_dic2016' if mon=='ML' else 'exposicion_mixta_millones_ARS_dic2016'
        if fam!='Total':f=f.join(get_rate(rates,amounts,fam,holder,mon))
        if sid=='927':
            uva=api.loc[api.serie_id.eq(1240)].set_index('fecha').valor_analitico
            f['tasa_pct']=uva.reindex(GRID)
            f['fuente_tasa']='API_1240_TNA_UVA_piloto_vigente'
        if 'tasa_pct' not in f:f['tasa_pct']=np.nan
        f['stock_publicado_cero']=sx.reindex(GRID).iloc[:,0].eq(0)
        f['stock_ausente']=sx.reindex(GRID).iloc[:,0].isna()
        for k in [1,3,12]:f[f'g{k}_pct']=crecimiento(f.R,k)
        f['delta_R_3m']=(f.R-f.R.shift(3)).where(f.R.rolling(4,min_periods=4).count().eq(4))
        f['aceleracion_3m_pp']=f.g3_pct-f.g3_pct.shift(3)
        f['volatilidad_6m_pp']=f.g1_pct.rolling(6,min_periods=6).std(ddof=0)
        f['delta_tasa_3m_pp']=(f.tasa_pct-f.tasa_pct.shift(3)).where(f.tasa_pct.rolling(4,min_periods=4).count().eq(4))
        f['split']=split(f.index)
        f['core_completo']=f[['R','g3_pct','tasa_pct']].notna().all(axis=1)
        f.index.name='fecha_mes'
        f.to_csv(output/'features'/f'{sid}.csv',float_format='%.12g')
        frames[sid]=f
        relevant=f.loc['2016-12-31':]
        counts={s:int((f.split.eq(s)&f.core_completo).sum()) for s in ['train','validacion','retrospectiva']}
        r0=f.loc[f.split.eq('train')&f.core_completo,'R'].median()
        d.update(tasa_encontrada=bool(f.tasa_pct.notna().any()),
                 fuente_stock=d['origen']+'.xls/'+d['hoja_stock']+'/columna_'+str(d['col_stock']),
                 fuente_tasa=';'.join(f.fuente_tasa.dropna().astype(str).unique()) if 'fuente_tasa' in f else '',
                 alcance_poblacion='sector_privado_no_financiero',
                 tasa_proxy='nominal fija/repactable; stock vigente frente a operaciones' if fam!='Tarjetas' else 'nominal fija distinta de cero frente a saldo total de tarjetas',
                 unidad_validada=True,estado='existente_cerrado' if d['ya_cerrado'] else 'evaluacion')
        quality.append(dict(serie=sid,familia=fam,titular=holder,moneda=mon,
                            meses_stock=int(sx.iloc[:,0].notna().sum()),
                            ceros_xls_201612_202606=int(relevant.stock_publicado_cero.sum()),
                            ceros_api_xls_positivo=int(a.api_cero_xls_positivo.sum()) if d['origen']=='perser_priv' else 0,
                            train=counts['train'],validacion=counts['validacion'],retrospectiva=counts['retrospectiva'],
                            R0=float(r0) if pd.notna(r0) else None,
                            elegible_numerico=counts['train']>=60 and counts['validacion']>=18 and pd.notna(r0) and r0>0,
                            ultimo_R=float(f.R.iloc[-1]),ultimo_tasa=float(f.tasa_pct.iloc[-1]) if pd.notna(f.tasa_pct.iloc[-1]) else None))
    pd.DataFrame(desc).to_csv(output/'catalogo_auditado.csv',index=False)
    pd.DataFrame(quality).to_csv(output/'calidad_elegibilidad.csv',index=False)
    pd.concat(audit,ignore_index=True).to_csv(output/'auditoria_api_xls.csv',index=False)
    fx.to_csv(output/'tipo_cambio_cierre.csv')
    composition(root,output,stocks)
    write_json(output/'procedencia_eda.json',dict(fuentes={p.name:hash_file(p) for p in sorted((root/'fuentes').iterdir())},codigo=hash_file(Path(__file__)),version='pendientes_0.1',corte='2026-06-30'))
    return frames,desc,pd.DataFrame(quality)

def composition(root,output,stocks):
    rows=[]
    for family,sn in [('Total','Prest-Tot'),('Hipotecarios','Prest-Hip'),('Prendarios','Prest-Prend')]:
        d=stocks[sn];maps={f'{h}_{m}':c+off for c,h in TITULARES.items() for m,off in [('TOTAL',-13),('ML',0),('ME',13)]}
        t=tabla(d,2,maps)/1000
        for h in TITULARES.values():
            a=t[[h+'_TOTAL',h+'_ML',h+'_ME']].copy();a.columns=['total_millones_ars','ML_millones_ars','ME_millones_ars']
            a['residual_total_menos_partes']=a.total_millones_ars-a.ML_millones_ars-a.ME_millones_ars
            a['participacion_ME_pct']=100*a.ME_millones_ars/a.total_millones_ars.where(a.total_millones_ars.gt(0))
            a['familia']=family;a['titular']=h;rows.append(a)
    pd.concat(rows).to_csv(output/'composicion_moneda_y_residuales.csv',index_label='fecha_mes')

def plots(frames,desc,folder):
    folder.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False})
    for fam in ['Hipotecarios','Prendarios','Personales','Tarjetas','Total']:
        ds=[d for d in desc if d['familia']==fam and not d['ya_cerrado']]
        fig,axs=plt.subplots(len(ds),3,figsize=(15,max(5,len(ds)*2.2)),squeeze=False,layout='constrained')
        for i,d in enumerate(ds):
            f=frames[d['serie']].loc['2016-12-31':]
            label=d['serie'].replace('finserprom_','')+' · '+d['titular']+' · '+d['moneda']
            for j,(col,title) in enumerate([('R','Volumen / exposición'),('tasa_pct','TNA proxy (%)'),('g3_pct','Variación de R a 3 meses (%)')]):
                ax=axs[i,j];ax.plot(f.index,f[col],color=['#2467A0','#9B5227','#258073'][j],lw=1.4)
                if i==0:ax.set_title(title,fontweight='bold')
                if j==0:ax.set_ylabel(label+'\n'+d['unidad_R'].replace('millones_','M ').replace('_',' '),fontsize=8)
                if not f[col].notna().any():ax.text(.5,.5,'Sin tasa compatible' if col=='tasa_pct' else 'Sin datos',ha='center',transform=ax.transAxes,color='#777777')
                ax.axvline(pd.Timestamp('2022-02-28'),color='#aaaaaa',lw=.7,ls='--')
                ax.set_xlim(pd.Timestamp('2016-12-31'),pd.Timestamp('2026-06-30'))
                ax.xaxis.set_major_locator(mdates.YearLocator(2));ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
                ax.grid(alpha=.15)
        fig.suptitle(f'{fam}: exploración inicial · datos sin desestacionalizar · corte junio 2026',fontsize=14,fontweight='bold')
        fig.savefig(folder/f'eda_{fam.lower()}.png',dpi=140);plt.close(fig)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--fase',choices=['eda','modelos','todo'],default='eda');parser.add_argument('--output',type=Path)
    args=parser.parse_args();frames,desc,quality=eda(output=args.output)
    out=Path(args.output or ROOT/'resultados')
    plots(frames,desc,ROOT/'graficos' if args.output is None else out/'graficos')
    print(quality[['serie','ceros_xls_201612_202606','train','validacion','retrospectiva','elegible_numerico']].to_string(index=False))
    if args.fase!='eda':
        from modelos import ejecutar_modelos
        ejecutar_modelos(ROOT,out,frames,desc,quality)

if __name__=='__main__':main()
