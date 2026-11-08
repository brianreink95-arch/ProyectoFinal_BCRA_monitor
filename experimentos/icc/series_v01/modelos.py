"""Candidatos S1 y decisiones bajo el protocolo 0.1 predefinido."""
import copy,json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from ejecutar import write_json,hash_file,GRID

def logistic(x):
    x=np.asarray(x,dtype=float);a=np.exp(-np.abs(x))
    return np.where(x>=0,1/(1+a),a/(1+a))

def scale(s,floor):
    q=np.quantile(np.asarray(s,dtype=float),[.25,.75],method='linear')
    return float(max((q[1]-q[0])/1.349,floor))

def fit(f,full=True):
    cols=['R','g3_pct','tasa_pct'] if full else ['R','g3_pct']
    z=f.loc[f.split.eq('train')].dropna(subset=cols)
    if len(z)<60:raise ValueError('Train insuficiente: no se reduce mínimo ni se mueven cortes')
    refs=dict(n_train=len(z),fechas_train=[str(d.date()) for d in z.index],R0=float(z.R.median()),sg=scale(z.g3_pct,.5))
    if refs['R0']<=0:raise ValueError('R0 no positivo: no se fabrica una referencia')
    if full:refs.update(r0=float(z.tasa_pct.median()),sr=scale(z.tasa_pct,.1))
    return refs

def components(R,r,g,ref,alpha):
    R=np.asarray(R,float);r=np.asarray(r,float);g=np.asarray(g,float)
    if np.any(R<0) or np.any(r<0) or not 0<=alpha<=1:raise ValueError('Inputs fuera de dominio')
    V=R/(R+ref['R0']);C=logistic((ref['r0']-r)/ref['sr']);M=logistic(g/ref['sg'])
    return V,C,M,100*V*(alpha*C+(1-alpha)*M)

def score(f,ref,alpha):
    out=f.copy();ok=f[['R','g3_pct','tasa_pct']].notna().all(axis=1)&f.split.isin(['train','validacion','retrospectiva'])
    for c in ['V','C','M','icc_candidato']:out[c]=np.nan
    for c,v in zip(['V','C','M','icc_candidato'],components(f.loc[ok,'R'],f.loc[ok,'tasa_pct'],f.loc[ok,'g3_pct'],ref,alpha)):out.loc[ok,c]=v
    out['utilizable']=ok;out['alpha_costo']=alpha
    out['aporte_nivel_costo']=100*out.V*alpha*out.C
    out['aporte_nivel_momentum']=100*out.V*(1-alpha)*out.M
    H=alpha*out.C+(1-alpha)*out.M
    out['delta_icc']=out.icc_candidato.diff()
    out['aporte_delta_volumen']=100*out.V.diff()*(H+H.shift(1))/2
    out['aporte_delta_costo']=100*(out.V+out.V.shift(1))/2*alpha*out.C.diff()
    out['aporte_delta_momentum']=100*(out.V+out.V.shift(1))/2*(1-alpha)*out.M.diff()
    out['aprobacion_operativa']=False;out['disponibilidad_historica_verificada']=False
    return out

def compare(a,b):
    a=pd.Series(np.asarray(a));b=pd.Series(np.asarray(b));rho=a.rank().corr(b.rank()) if a.nunique()>1 and b.nunique()>1 else np.nan
    mae=float((a-b).abs().mean())
    return dict(n=len(a),spearman=float(rho) if pd.notna(rho) else None,mae=mae,pasa=bool(pd.notna(rho) and rho>=.9 and mae<=10))

def sensitivities(f,ref,alpha):
    variants=[('alpha_menos_0.1','alpha',alpha-.1),('alpha_mas_0.1','alpha',alpha+.1),
              ('R0_por_0.75','R0',.75),('R0_por_1.25','R0',1.25),
              ('escalas_por_0.75','escalas',.75),('escalas_por_1.25','escalas',1.25),
              ('g1_en_lugar_g3','g1_pct',.5),('delta_R_3m_en_lugar_g3','delta_R_3m',1.),
              ('costo_0.8_nivel_0.2_delta_tasa','delta_tasa_3m_pp',.1)]
    rows=[]
    for label,family,value in variants:
        modified=dict(ref);weight=alpha
        if family=='alpha':weight=value
        elif family=='R0':modified['R0']*=value
        elif family=='escalas':modified['sr']*=value;modified['sg']*=value
        else:
            train=f.loc[f.split.eq('train')].dropna(subset=['R','tasa_pct','g3_pct',family])
            if len(train)<60:
                rows.append(dict(variante=label,split='train',n=len(train),spearman=None,mae=None,pasa=False));continue
            alt_scale=scale(train[family],value)
        for role,minimum in [('train',60),('validacion',18)]:
            cols=['R','tasa_pct','g3_pct']+([family] if family in ['g1_pct','delta_R_3m','delta_tasa_3m_pp'] else [])
            z=f.loc[f.split.eq(role)].dropna(subset=cols)
            if len(z)<minimum:
                rows.append(dict(variante=label,split=role,n=len(z),spearman=None,mae=None,pasa=False));continue
            V,C,M,B=components(z.R,z.tasa_pct,z.g3_pct,ref,alpha)
            if family in ['g1_pct','delta_R_3m']:alt=100*V*(alpha*C+(1-alpha)*logistic(z[family]/alt_scale))
            elif family=='delta_tasa_3m_pp':alt=100*V*(alpha*(.8*C+.2*logistic(-z[family]/alt_scale))+(1-alpha)*M)
            else:alt=components(z.R,z.tasa_pct,z.g3_pct,modified,weight)[3]
            rows.append(dict(variante=label,split=role,**compare(B,alt)))
    return rows

def economic(ref,alpha):
    v=np.array([0,.01,.1,.25,.5,1,2,5])*ref['R0']
    r=np.unique(np.maximum(0,[0,ref['r0']-2*ref['sr'],ref['r0'],ref['r0']+2*ref['sr']]))
    g=np.array([-2,0,2])*ref['sg'];R,T,G=np.meshgrid(v,r,g,indexing='ij')
    B=components(R,T,G,ref,alpha)[3]
    rules=dict(rango=np.isfinite(B).all() and (B>=0).all() and (B<=100).all(),
               volumen_monotono=(np.diff(B,axis=0)>=-1e-9).all(),
               tasa_monotona=(np.diff(B,axis=1)<=1e-9).all(),
               momentum_monotono=(np.diff(B,axis=2)>=-1e-9).all(),
               bajo_volumen=(B[:4]<=20+1e-9).all(),stock_cero=np.allclose(B[0],0))
    return {k:bool(v) for k,v in rules.items()}

def extract_ecc(root,out):
    path=root/'fuentes/ECC-Familias.xlsx';rows=[];roman={'I':1,'II':2,'III':3,'IV':4}
    for sheet in ['10','13','15']:
        d=pd.read_excel(path,sheet,header=None)
        if sheet in ['10','15']:
            specs=[('Hipotecarios',11),('Prendarios',23),('Tarjetas',35),('Personales',47)]
            specs=[(fam,'estandares' if sheet=='10' else 'demanda',r) for fam,r in specs]
        else:
            specs=[(fam,dim,offset+r) for fam,offset in [('Hipotecarios',0),('Prendarios',53),('Tarjetas',106),('Personales',159)] for dim,r in [('spread',12),('montos',32),('plazo',42)]]
        for fam,dimension,row in specs:
            assert 'ID ponderado' in str(d.iat[row,0])
            for c in range(4,d.shape[1]):
                code=d.iat[3,c]
                if not isinstance(code,str) or '-' not in code:continue
                q,y=code.split('-');v=pd.to_numeric(pd.Series([d.iat[row,c]]),errors='coerce').iloc[0]
                if pd.notna(v):rows.append(dict(trimestre=f'{2000+int(y)}Q{roman[q]}',familia=fam,dimension=dimension,id_ecc=float(v),fuente='ECC-Familias',fila_excel=row+1,columna_excel=c+1))
    ecc=pd.DataFrame(rows);ecc.to_csv(out/'ecc_familias_normalizada.csv',index=False)
    # Ampliar el contraste empresarial previo con montos máximos, desde XLS.
    rr=[];specs={'1':{'estandares':{'general':11,'grandes':23,'pymes':35}},
                 '6':{'demanda':{'general':11,'grandes':23,'pymes':35}},
                 '4':{'spread':{'general':12,'grandes':75,'pymes':138},
                      'montos':{'general':32,'grandes':95,'pymes':158},
                      'plazo':{'general':42,'grandes':105,'pymes':168}}}
    for sheet,dims in specs.items():
        raw=pd.read_excel(root/'fuentes/ECC-Empresas.xlsx',sheet,header=None)
        for dim,pops in dims.items():
            for pop,row in pops.items():
                assert 'ID ponderado' in str(raw.iat[row,0])
                for c in range(4,raw.shape[1]):
                    code=raw.iat[3,c]
                    if not isinstance(code,str) or '-' not in code:continue
                    q,y=code.split('-');value=pd.to_numeric(pd.Series([raw.iat[row,c]]),errors='coerce').iloc[0]
                    if pd.notna(value):rr.append(dict(trimestre=f'{2000+int(y)}Q{roman[q]}',poblacion=pop,dimension=dim,id_ecc=float(value),fila_excel=row+1,columna_excel=c+1,hoja=sheet))
    pd.DataFrame(rr).to_csv(out/'ecc_empresas_normalizada_ampliada.csv',index=False)
    return ecc

def ecc_for(root,ecc,d,out):
    if d['titular'] in ['PH','Privado']:
        return ecc.loc[ecc.familia.eq(d['familia'])],('familias_linea' if d['titular']=='PH' else 'familias_proxy_universo_privado')
    e=pd.read_csv(out/'ecc_empresas_normalizada_ampliada.csv')
    pop='pymes' if d['titular']=='PyMEs' else 'grandes'
    e=e.loc[e.poblacion.eq(pop)].copy()
    # Fuente empresarial normalizada conserva las denominaciones originales.
    return e,'credito_empresarial_amplio_proxy_no_especifica_linea_moneda'

def ecc_metrics(sc,ecc,sid,alpha,proxy):
    rows=[];robust=[];pairs=[]
    # Cierres originales, calendario trimestral íntegro. No comprimir faltantes.
    closes=sc.loc[sc.index.month.isin([3,6,9,12]),'icc_candidato']
    for shift in [-1,0,1]:
        q=pd.DataFrame(index=closes.index)
        for dt in q.index:
            target=dt+pd.offsets.MonthEnd(shift)
            q.loc[dt,'score']=sc.icc_candidato.get(target,np.nan)
        q['cambio']=q.score.diff();q['trimestre']=q.index.to_period('Q').astype(str)
        for dim in ['estandares','demanda','spread','montos','plazo']:
            e=ecc.loc[ecc.dimension.eq(dim),['trimestre','id_ecc']]
            m=q.merge(e,on='trimestre').dropna(subset=['cambio','id_ecc'])
            if shift==0:
                for band in [.5,1,2]:
                    active=m.id_ecc.abs().gt(5)&m.cambio.abs().gt(band)
                    acc=float((np.sign(m.loc[active,'cambio'])==np.sign(m.loc[active,'id_ecc'])).mean()) if active.any() else None
                    rows.append(dict(serie=sid,alpha=alpha,dimension=dim,n=len(m),rho=spearman(m.cambio,m.id_ecc),banda_icc=band,n_activos=int(active.sum()),acuerdo_signo=acc,proxy=proxy))
                p=m.copy();p['serie']=sid;p['alpha']=alpha;p['dimension']=dim;p['proxy']=proxy;pairs.append(p)
                for year in sorted(m.trimestre.str[:4].unique()):
                    z=m.loc[~m.trimestre.str.startswith(year)]
                    robust.append(dict(serie=sid,alpha=alpha,dimension=dim,variante='excluir_'+year,n=len(z),rho=spearman(z.cambio,z.id_ecc)))
            else:
                robust.append(dict(serie=sid,alpha=alpha,dimension=dim,variante=f'cierre_{shift:+d}_mes',n=len(m),rho=spearman(m.cambio,m.id_ecc)))
    return rows,robust,pairs

def spearman(a,b):
    if len(a)<3 or a.nunique()<2 or b.nunique()<2:return None
    r=a.rank().corr(b.rank());return float(r) if pd.notna(r) else None

def ejecutar_modelos(root,out,frames,desc,quality):
    protocol=json.loads((root/'protocolo.json').read_text())
    for folder in ['candidatos','referencias','indices','parciales']:(out/folder).mkdir(exist_ok=True)
    ecc=extract_ecc(root,out)
    sensitivity=[];metrics=[];robust=[];pairs=[];decisions=[];events=[]
    from exploracion import EPOCAS,ejecutar_exploracion
    ejecutar_exploracion(root,out,frames,desc)
    for d in desc:
        sid=d['serie'];f=frames[sid];q=quality.set_index('serie').loc[sid]
        decision=dict(serie=sid,familia=d['familia'],titular=d['titular'],moneda=d['moneda'],agregado=d['agregado'],unidad_R=d['unidad_R'],alpha=None,
                      n_train=int(q.train),n_validacion=int(q.validacion),estado='contexto',motivo='',version='pendientes_0.1',operativo=False)
        if d['ya_cerrado']:
            decision.update(estado='existente_cerrado',alpha=.6 if sid=='935' else .8,motivo='Se preserva el cierre previo; no se recalcula en esta entrega')
            decisions.append(decision);continue
        selected=None;ref=None
        if q.elegible_numerico and d['familia']!='Total':
            ref=fit(f);write_json(out/'referencias'/f'{sid}.json',dict(**ref,unidad_R=d['unidad_R'],protocolo_sha256=hash_file(root/'protocolo.json')))
            e,proxy=ecc_for(root,ecc,d,out)
            for alpha in protocol['alpha_candidatos']+protocol['alpha_extremos_diagnosticos']:
                sc=score(f,ref,alpha)
                sc.to_csv(out/'candidatos'/f'{sid}_C{int(alpha*100)}.csv',float_format='%.12g')
                if alpha in protocol['alpha_candidatos']:
                    checks=sensitivities(f,ref,alpha);ec=economic(ref,alpha)
                    sensitivity.extend([dict(serie=sid,alpha=alpha,**r) for r in checks])
                    passed=all(r['pasa'] for r in checks) and all(ec.values())
                    write_json(out/'referencias'/f'{sid}_C{int(alpha*100)}_controles.json',dict(economia=ec,estabilidad_pasa=bool(passed)))
                    if selected is None and passed:selected=alpha
                    met,rob,pp=ecc_metrics(sc,e,sid,alpha,proxy);metrics.extend(met);robust.extend(rob);pairs.extend(pp)
                for name,a,b in EPOCAS:
                    if a in sc.index and b in sc.index:
                        delta=sc.loc[b,'icc_candidato']-sc.loc[a,'icc_candidato']
                        events.append(dict(serie=sid,alpha=alpha,epoca=name,desde=a,hasta=b,delta_icc=delta))
            if selected is not None:
                sc=score(f,ref,selected);sc=sc.rename(columns={'icc_candidato':'icc_experimental'})
                sc['estado']='cerrado_experimental';sc['equivalente_nivel_otros_indices']=False
                sc.to_csv(out/'indices'/f'icc_{sid}.csv',float_format='%.12g')
                decision.update(estado='ICC_experimental',alpha=selected,motivo='Primera ponderación que pasa controles predefinidos; convención de robustez, no óptimo histórico')
            else:decision['motivo']='Ninguna ponderación pasa todos los controles de estabilidad predefinidos'
        elif d['titular']=='Prestadoras':decision['motivo']='Sin tasa específica; precisión/cobertura revisadas'
        elif d['familia']=='Total':decision['motivo']='Exposición mixta por titular; sin costo único compatible; solapa productos y conserva valuación ME'
        else:decision['motivo']='Cobertura core insuficiente para 60 train y 18 validación; sin relajar protocolo'
        if selected is None and d['familia']!='Total':
            v=f.loc[f.split.eq('validacion')].dropna(subset=['R','g3_pct'])
            try:
                vr=fit(f,full=False)
                if len(v)<18:raise ValueError('Validación parcial insuficiente')
            except ValueError:
                if d['moneda']=='ME' and f.loc['2016-12-31':].R.eq(0).all():decision.update(estado='excluida_diferida',motivo=decision['motivo']+'; saldo cero en todo el período reciente a precisión publicada')
                else:decision['motivo']+='; tampoco hay cobertura/referencia positiva para IVD'
            else:
                part=f.copy();ok=f[['R','g3_pct']].notna().all(axis=1)&f.split.isin(['train','validacion','retrospectiva'])
                part['ivd_parcial']=np.nan;part.loc[ok,'ivd_parcial']=100*f.loc[ok,'R']/(f.loc[ok,'R']+vr['R0'])*logistic(f.loc[ok,'g3_pct']/vr['sg'])
                part['es_icc']=False;part.to_csv(out/'parciales'/f'ivd_{sid}.csv',float_format='%.12g')
                write_json(out/'referencias'/f'{sid}_IVD.json',vr)
                decision.update(estado='indicador_parcial',n_train_ivd=vr['n_train'],n_validacion_ivd=len(v),motivo=decision['motivo']+'; se publica IVD sin costo, no equivalente a ICC')
        decisions.append(decision)
    pd.DataFrame(decisions).to_csv(out/'registro_decisiones.csv',index=False)
    pd.DataFrame(sensitivity).to_csv(out/'sensibilidades.csv',index=False)
    pd.DataFrame(metrics).to_csv(out/'contraste_ecc.csv',index=False)
    pd.DataFrame(robust).to_csv(out/'robustez_ecc.csv',index=False)
    if pairs:pd.concat(pairs,ignore_index=True).to_csv(out/'pares_ecc_icc.csv',index=False)
    pd.DataFrame(events).to_csv(out/'epocas_indices.csv',index=False)
    write_json(out/'decision_global.json',dict(estado='no_calculado',razones=['Escalas de referencia propias sin equivalencia demostrada','ML real y ME nominal USD no tienen un constructo global validado','Stocks medios de consumo y saldos de cierre de titulares no son una partición homogénea','Totales por titular solapan subproductos; residuales total/ML/ME no forzados','Quedan adelantos, documentos y otras líneas fuera de particulares construidos'],formula_aprobada=False,pesos_aprobados=False))
    print(pd.DataFrame(decisions)[['serie','estado','alpha','n_train','n_validacion']].to_string(index=False))
    chart_indices(root,out,decisions)
    write_json(out/'procedencia_modelos.json',dict(protocolo_sha256=hash_file(root/'protocolo.json'),codigo_modelos_sha256=hash_file(Path(__file__)),exploracion_sha256=hash_file(root/'exploracion_inicial.md'),fuentes_sha256={p.name:hash_file(p) for p in sorted((root/'fuentes').iterdir())},uso='descriptivo interno; retrospectivo; sin reserva ni alertas'))
    return decisions

def chart_indices(root,out,decisions):
    ds=[d for d in decisions if d['estado']=='ICC_experimental']
    if not ds:return
    fig,axs=plt.subplots(len(ds),3,figsize=(15,len(ds)*2.3),squeeze=False,layout='constrained')
    for i,d in enumerate(ds):
        sc=pd.read_csv(out/'indices'/f"icc_{d['serie']}.csv",parse_dates=['fecha_mes']).set_index('fecha_mes').loc['2017-03-31':]
        name=d['serie'].replace('finserprom_','')+' · '+d['moneda']
        for j,col in enumerate(['R','tasa_pct','icc_experimental']):
            ax=axs[i,j];ax.plot(sc.index,sc[col],color=['#2467A0','#9B5227','#258073'][j],lw=1.4);ax.grid(alpha=.15)
            if i==0:ax.set_title(['Volumen (unidad propia)','TNA nominal proxy (%)','ICC experimental'][j],fontweight='bold')
            if j==0:ax.set_ylabel(name+'\n'+d['unidad_R'].replace('millones_','M ').replace('_',' '),fontsize=8)
            if j==2:ax.set_ylim(0,100);ax.text(.02,.9,f"C {round(d['alpha']*100)}% · M {round((1-d['alpha'])*100)}%",transform=ax.transAxes,fontsize=9)
    fig.suptitle('Nuevos ICC: stock, tasa y puntaje · referencias propias · sin comparación directa de niveles',fontsize=13,fontweight='bold')
    dest=root/'graficos' if out==root/'resultados' else out/'graficos';dest.mkdir(exist_ok=True)
    fig.savefig(dest/'nuevos_icc_stock_tasa_indice.png',dpi=135);plt.close(fig)
