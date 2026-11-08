"""Compara pesos C/M congelando referencias. No modifica ni promueve el ICC."""
from pathlib import Path
import argparse, hashlib, json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent

def logistica(x):
    x=np.asarray(x,dtype=float);a=np.exp(-np.abs(x))
    return np.where(x>=0,1/(1+a),a/(1+a))

def score(v,c,m,alpha):
    if not 0<=alpha<=1:raise ValueError('Peso fuera de dominio')
    return 100*np.asarray(v)*(alpha*np.asarray(c)+(1-alpha)*np.asarray(m))

def umbral(a,bb,direction):
    # Cambio de B(alpha) = intercepto + pendiente*alpha.
    intercept=100*(bb.M_momentum*bb.V_volumen-a.M_momentum*a.V_volumen)
    slope=100*(bb.V_volumen*(bb.C_costo-bb.M_momentum)-a.V_volumen*(a.C_costo-a.M_momentum))
    zero=-intercept/slope if abs(slope)>1e-12 else None
    relation='todos' if abs(slope)<1e-12 else ('alpha > umbral' if slope>0 else 'alpha < umbral')
    if direction=='baja' and abs(slope)>1e-12:relation='alpha < umbral' if slope>0 else 'alpha > umbral'
    return {'intercepto_delta':float(intercept),'pendiente_delta':float(slope),'alpha_delta_cero':None if zero is None else float(zero),'condicion_direccion_esperada':relation}

def escenarios(weights):
    # Coords R/R0, (r0-r)/sr, g/sg. Son escenarios relativos de componentes.
    configs=[('referencia',1,0,0),('volumen_muy_bajo_condiciones_buenas',.1,2,2),
             ('debilidad_conjunta',.5,-2,-2),('expansion_conjunta',2,2,2),
             ('tasa_baja_contraccion',1,2,-2),('tasa_alta_expansion',1,-2,2),
             ('rebote_base_baja',.25,0,2),('volumen_alto_sin_dinamismo',2,0,-2)]
    rows=[]
    for name,rr,zc,zm in configs:
        v=rr/(1+rr);c=float(logistica(zc));m=float(logistica(zm))
        for w in weights:rows.append({'escenario':name,'R_sobre_R0':rr,'z_costo':zc,'z_momentum':zm,'V':v,'C':c,'M':m,'peso_costo':w,'icc':float(score(v,c,m,w))})
    return pd.DataFrame(rows)

def ejecutar(inputs,output):
    protocol=json.loads((ROOT/'protocolo_pesos.json').read_text());weights=protocol['pesos_costo']
    output.mkdir(parents=True,exist_ok=True)
    history=[];episodes=[];bounds=[];metrics=[];curves=[]
    hashes={'protocolo':hashlib.sha256((ROOT/'protocolo_pesos.json').read_bytes()).hexdigest(),'codigo':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'fuentes':{}}
    for sid in [935,936]:
        p=inputs/str(sid)/'icc_candidato.csv';hashes['fuentes'][str(sid)]=hashlib.sha256(p.read_bytes()).hexdigest()
        f=pd.read_csv(p);f['fecha_mes']=pd.to_datetime(f.fecha_mes);f=f.set_index('fecha_mes')
        eligible=f.icc_candidato_s1.notna()
        ref=score(f.V_volumen,f.C_costo,f.M_momentum,.8)
        np.testing.assert_allclose(ref,f.icc_candidato_s1,atol=1e-10,equal_nan=True)
        for w in weights:
            v=f.V_volumen;c=f.C_costo;m=f.M_momentum;h=w*c+(1-w)*m
            b=score(v,c,m,w);delta=pd.Series(b,index=f.index).diff()
            dv=100*v.diff()*(h+h.shift(1))/2
            dc=100*(v+v.shift(1))/2*w*c.diff()
            dm=100*(v+v.shift(1))/2*(1-w)*m.diff()
            np.testing.assert_allclose(dv+dc+dm,delta,atol=1e-10,equal_nan=True)
            curves.append(pd.DataFrame({'fecha_mes':f.index,'serie_id':sid,'peso_costo':w,'indicador_candidato':b,'delta':delta,'aporte_delta_volumen':dv,'aporte_delta_costo':dc,'aporte_delta_momentum':dm}).reset_index(drop=True))
            sums=np.array([dv.abs().sum(),dc.abs().sum(),dm.abs().sum()]);shares=sums/sums.sum()*100
            for role,mask in [('train',f.split_temporal.eq('train')),('validacion',f.split_temporal.eq('validacion')),('retrospectiva',f.split_temporal.eq('evaluacion_retrospectiva'))]:
                use=mask&eligible
                metrics.append({'serie_id':sid,'peso_costo':w,'bloque':role,'n':int(use.sum()),'MAE_frente_80_20':float(np.mean(np.abs(b[use]-ref[use]))),'rho_frente_80_20':float(pd.Series(b[use]).corr(pd.Series(ref[use]),method='spearman'))})
            history.append({'serie_id':sid,'peso_costo':w,'ultimo':float(b[eligible][-1]),'participacion_abs_cambios_volumen_pct':float(shares[0]),'participacion_abs_cambios_costo_pct':float(shares[1]),'participacion_abs_cambios_momentum_pct':float(shares[2])})
            for event in protocol['episodios']:
                a=f.loc[event['desde']];bb=f.loc[event['hasta']]
                before=float(score(a.V_volumen,a.C_costo,a.M_momentum,w));after=float(score(bb.V_volumen,bb.C_costo,bb.M_momentum,w))
                change=after-before;expect=event['direccion_esperada'];match=change>0 if expect=='suba' else change<0 if expect=='baja' else None
                episodes.append({'serie_id':sid,'episodio':event['id'],'desde':event['desde'],'hasta':event['hasta'],'peso_costo':w,'nivel_inicial':before,'nivel_final':after,'delta_indice':change,'direccion_esperada':expect,'coincidencia_direccional':match})
        for event in protocol['episodios']:
            if event['direccion_esperada']!='sin_objetivo_unico':bounds.append({'serie_id':sid,'episodio':event['id'],**umbral(f.loc[event['desde']],f.loc[event['hasta']],event['direccion_esperada'])})
    sc=escenarios(weights)
    for name,df in [('escenarios',sc),('episodios',pd.DataFrame(episodes)),('metricas',pd.DataFrame(metrics)),('resumen',pd.DataFrame(history)),('umbrales',pd.DataFrame(bounds)),('trayectorias',pd.concat(curves))]:df.to_csv(output/(name+'.csv'),index=False)
    (output/'procedencia.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n')
    print(pd.DataFrame(episodes).query('peso_costo in [0.5,0.6,0.7,0.8,0.9]').pivot_table(index=['serie_id','episodio'],columns='peso_costo',values='delta_indice').round(2).to_string())
    print(pd.DataFrame(bounds).round(4).to_string(index=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--inputs',type=Path,default=ROOT.parent/'hipotecarios_empresariales_v01/resultados');parser.add_argument('--output',type=Path,default=ROOT/'resultados');args=parser.parse_args();ejecutar(args.inputs,args.output)
