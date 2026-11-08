"""Entrenar y evaluar S1 offline. Ajusta train; decide con validación; no scorea retrospectiva.

PCA1 es un candidato descriptivo sin etiquetas. Todos los umbrales están
predefinidos: ningún fallo cambia automáticamente el método, pesos o cortes.
"""
from pathlib import Path
import argparse
import json
import sys
import html

import numpy as np
import pandas as pd
import sklearn
from sklearn.decomposition import PCA

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from ml import baseline as b

VERSION_MODELO = '4.0'


def rho(x,y):
    x,y = np.asarray(x,float),np.asarray(y,float)
    if len(x)<3 or not np.isfinite(x).all() or not np.isfinite(y).all():
        return None
    if np.ptp(x)==0 or np.ptp(y)==0:
        return None
    return float(pd.Series(x).corr(pd.Series(y),method='spearman'))


def comparar(default, alternate):
    correlation = rho(default,alternate)
    mae = float(np.abs(np.asarray(default)-np.asarray(alternate)).mean()) if len(default) else None
    return {'n': len(default), 'spearman': correlation, 'mae': mae,
            'pasa': correlation is not None and correlation>=.90 and mae<=10}


def sensibilidades_baseline(train, val, refs):
    results = []
    for family, values in [('peso_momentum',[0.,.30]),('R0',[.75,1.25]),('escalas',[.75,1.25])]:
        for value in values:
            modified = dict(refs)
            weight = .20
            if family=='peso_momentum':
                weight=value
            elif family=='R0':
                modified['R0']*=value
            else:
                modified['sr']*=value
                modified['sg']*=value
            checks={}
            for label, block in [('train',train),('validacion',val)]:
                args = [block[k].to_numpy(float) for k in b.PREDICTORES_BASELINE]
                default=b.componentes(args[0],args[2],args[1],refs)[3]
                alternate=b.componentes(args[0],args[2],args[1],modified,weight)[3]
                checks[label]=comparar(default,alternate)
            results.append({'variante':family,'valor':value,'comparaciones':checks,
                            'pasa':all(c['pasa'] for c in checks.values())})
    # Alternativas conservan intersección con core, no amplían train.
    for feature, floor, label in [(b.G1,.50,'crecimiento_mensual'),
                                  (b.DELTA_STOCK_REAL,1.,'delta_stock_3m'),
                                  (b.DELTA,.10,'cambio_tasa')]:
        t=train.loc[train[feature].notna()]
        v=val.loc[val[feature].notna()]
        if len(t)<60 or len(v)<18:
            results.append({'variante':label,'pasa':False,'motivo':'interseccion_insuficiente',
                            'n_train':len(t),'n_validacion':len(v)})
            continue
        s=b.escala(t[feature],floor)
        checks={}
        for role, block in [('train',t),('validacion',v)]:
            V,C,M,B=b.componentes(block[b.STOCK_REAL],block[b.TASA],block[b.G3],refs)
            if feature==b.DELTA:
                C=.8*C+.2*b.logistica(-block[feature].to_numpy(float)/s)
            else:
                M=b.logistica(block[feature].to_numpy(float)/s)
            checks[role]=comparar(B,100*V*(.8*C+.2*M))
        results.append({'variante':label,'escala_train':s,'comparaciones':checks,
                        'pasa':all(c['pasa'] for c in checks.values())})
    return {'pasa':all(x['pasa'] for x in results),'variantes':results,
            'regla':'rho>=0.90 y MAE<=10 en train y validacion; no elegir ganador'}


def transformar(frame, refs):
    return np.column_stack([np.log1p(frame[b.STOCK_REAL].to_numpy(float)/refs['R0']),
                            -frame[b.TASA].to_numpy(float),
                            np.arcsinh(frame[b.G3].to_numpy(float)/refs['sg'])])


def cargas_admisibles(a):
    a=np.asarray(a,float)
    total=float(a.sum())
    fractions=a/total if total>0 else np.full(3,np.nan)
    ok=bool(np.isfinite(a).all() and (a>=0).all() and
            np.isfinite(fractions).all() and (fractions>=np.array([.20,.20,.10])).all())
    return {'pasa':ok,'cargas':a.tolist(),
            'participaciones_l1':fractions.tolist() if np.isfinite(fractions).all() else None,
            'minimos_l1':[.20,.20,.10]}


def ajustar_factor(Z):
    pca=PCA(n_components=1,svd_solver='full',whiten=False).fit(Z)
    a=pca.components_[0].copy()
    orientation=1. if a[1]>=0 else -1.
    a*=orientation
    f=(Z-pca.mean_)@a
    return {'cargas':a.tolist(),'centro_pca':pca.mean_.tolist(),
            'f0':float(np.median(f)),'sf':b.escala(f,1e-6),
            'varianza_explicada':float(pca.explained_variance_ratio_[0]),
            'solver':'full','whiten':False,'n_components':1}


def proyectar(Z, factor):
    if factor.get('algoritmo') == 'factor_analysis':
        return (np.asarray(Z)-np.asarray(factor['centro_factor']))@np.asarray(factor['pesos_score'])
    return (np.asarray(Z)-np.asarray(factor['centro_pca']))@np.asarray(factor['cargas'])


def score_factor(frame,refs,pca):
    Y=transformar(frame,refs)
    Z=(Y-np.asarray(pca['media_y_train']))/np.asarray(pca['std_y_train'])
    f=proyectar(Z,pca)
    latent=100*b.logistica((f-pca['f0'])/pca['sf'])
    V=frame[b.STOCK_REAL].to_numpy(float)/(frame[b.STOCK_REAL].to_numpy(float)+refs['R0'])
    return f,latent,V*latent


def escenarios_pca(refs,pca):
    def scorer(R,r,g):
        shape=R.shape
        x=pd.DataFrame({b.STOCK_REAL:R.ravel(),b.TASA:r.ravel(),b.G3:g.ravel()})
        return score_factor(x,refs,pca)[2].reshape(shape)
    return b.controles_economicos(refs,scorer)


def perturbaciones(train,val,refs,pca):
    mean=np.asarray(pca['media_y_train'])
    std=np.asarray(pca['std_y_train'])
    Z=(transformar(train,refs)-mean)/std
    Zv=(transformar(val,refs)-mean)/std
    Vv=val[b.STOCK_REAL].to_numpy(float)/(val[b.STOCK_REAL].to_numpy(float)+refs['R0'])
    default=score_factor(val,refs,pca)[2]
    a=np.asarray(pca['cargas'])
    checks=[]
    for col in range(3):
        for multiplier in (.9,1.1):
            D=np.ones(3)
            D[col]=multiplier
            alt=ajustar_factor(Z*D)  # No reestandarizar tras perturbación.
            load=np.asarray(alt['cargas'])*D
            cosine=float(np.dot(load,a)/(np.linalg.norm(load)*np.linalg.norm(a)))
            f=proyectar(Zv*D,alt)
            score=Vv*100*b.logistica((f-alt['f0'])/alt['sf'])
            corr=rho(default,score)
            economic=cargas_admisibles(load)
            checks.append({'columna':['volumen','costo','momentum'][col],'multiplicador':multiplier,
                           'cargas_original_z':load.tolist(),'coseno':cosine,'spearman_val':corr,
                           'cargas_admisibles':economic['pasa'],
                           'pasa':economic['pasa'] and cosine>=.95 and corr is not None and corr>=.90})
    return {'pasa':all(c['pasa'] for c in checks),'casos':checks}


def reconstruccion(train,val,refs,pca):
    mean=np.asarray(pca['media_y_train']);std=np.asarray(pca['std_y_train'])
    Z=(transformar(train,refs)-mean)/std
    Zv=(transformar(val,refs)-mean)/std
    B=b.componentes(train[b.STOCK_REAL],train[b.TASA],train[b.G3],refs)[3]
    Bv=b.componentes(val[b.STOCK_REAL],val[b.TASA],val[b.G3],refs)[3]
    coefficients=np.linalg.lstsq(np.column_stack([np.ones(len(B)),B]),Z,rcond=None)[0]
    a=np.asarray(pca['cargas'])
    center=np.asarray(pca['centro_factor'] if pca.get('algoritmo')=='factor_analysis' else pca['centro_pca'])
    def error(z,base):
        estimated=np.column_stack([np.ones(len(base)),base])@coefficients
        inverse=np.outer(proyectar(z,pca),a)+center
        eb=((z-estimated)**2).mean(axis=0)
        ep=((z-inverse)**2).mean(axis=0)
        valid=bool((eb>1e-12).all() and eb.mean()>1e-12)
        improvement=float(1-ep.mean()/eb.mean()) if valid else None
        ratios=(ep/eb).tolist() if valid else None
        return {'n':len(z),'mse_baseline_por_columna':eb.tolist(),'mse_pca_por_columna':ep.tolist(),
                'mse_baseline':float(eb.mean()),'mse_pca':float(ep.mean()),
                'mejora_relativa':improvement,'ratios_por_columna':ratios,
                'pasa':valid and improvement>=.10 and all(r<=1.25 for r in ratios)}
    n=len(val)//2
    metrics={'train':error(Z,B),'validacion':error(Zv,Bv),
             'bloques_validacion_descriptivos':[{'desde':val['fecha_mes'].iloc[start],
                 'hasta':val['fecha_mes'].iloc[end-1],**error(Zv[start:end],Bv[start:end])}
                 for start,end in [(0,n),(n,len(val))]]}
    return {'pasa':metrics['validacion']['pasa'],'metricas':metrics,
            'coeficientes_comparador_train':coefficients.tolist(),
            'interpretacion':'reconstruccion de inputs estandarizados; no accuracy economica'}


def saturacion(val,refs,pca):
    _,latent,_=score_factor(val,refs,pca)
    V,C,M,_=b.componentes(val[b.STOCK_REAL],val[b.TASA],val[b.G3],refs)
    def rate(x):
        return float(((np.asarray(x)<=1)|(np.asarray(x)>=99)).mean())
    fraction=rate(latent)
    return {'pasa':fraction<=.10,'fraccion_latente':fraction,
            'meses_latente':int(((latent<=1)|(latent>=99)).sum()),'n_validacion':len(val),
            'fraccion_componentes':{k:rate(100*v) for k,v in [('V',V),('C',C),('M',M)]}}


def entrenar_icc(frame, source=None):
    refs=b.ajustar_referencias_icc(frame)
    split=b.asignar_splits_icc(frame);core=b.mascara_core(frame)
    train=frame.loc[split.eq('train')&core].copy()
    val=frame.loc[split.eq('validacion')&core].copy()
    if len(val)<18:
        raise ValueError(f'Validacion insuficiente: {len(val)} meses; minimo 18.')
    economic=b.controles_economicos(refs)
    if not economic['pasa']:
        raise ValueError('Baseline no pasa escenarios económicos; no publicar índice.')
    sensitivities=sensibilidades_baseline(train,val,refs)
    Y=transformar(train,refs); mean=Y.mean(axis=0); std=Y.std(axis=0,ddof=0)
    gates={'cobertura':{'pasa':True,'n_train':len(train),'n_validacion':len(val)},
           'economia_baseline':economic,'sensibilidad_baseline':sensitivities}
    pca=None
    if np.any(std<=1e-12) or not np.isfinite(std).all():
        gates['variacion_pca']={'pasa':False,'std_y_train':std.tolist(),
                                'motivo':'columna sin variacion suficiente'}
    else:
        Z=(Y-mean)/std
        pca={**ajustar_factor(Z),'media_y_train':mean.tolist(),'std_y_train':std.tolist()}
        gates['variacion_pca']={'pasa':True}
        gates['cargas_pca']=cargas_admisibles(pca['cargas'])
        # Factor diagnóstico aun si la dirección económica falla; no candidato ICC.
        gates['economia_pca']=escenarios_pca(refs,pca)
        gates['perturbaciones_pca']=perturbaciones(train,val,refs,pca)
        gates['reconstruccion']=reconstruccion(train,val,refs,pca)
        gates['saturacion']=saturacion(val,refs,pca)
    accepted=all(v['pasa'] for v in gates.values())
    failures=[k for k,v in gates.items() if not v['pasa']]
    artifact={'schema':'icc_s1_modelo_4.0','config_s1':b.CONFIG_S1,'referencias':refs,
              'protocolo':b.comprobar_protocolo_icc(frame),'fuente':source or {'fuentes_reconstruidas':False},
              'parametros_pca':pca,'gates':gates,'pca_aceptado':accepted,
              'metodo_elegido':'pca_s1' if accepted else 'baseline_s1',
              'motivos_rechazo_pca':failures,
              'estado_baseline':'experimental' if sensitivities['pasa'] else 'experimental_sensible',
              'estado_producto':'experimental','disponibilidad_historica_verificada':False,
              'validacion_sha256':b.hash_bloque(val),
              'entorno':{**b.runtime_metadata(),'scikit_learn':sklearn.__version__},
              'codigo_sha256':{name:__import__('hashlib').sha256((Path(__file__).parent/name).read_bytes()).hexdigest()
                               for name in ('baseline.py','train.py','score.py')},
              'limitaciones':['Saldo vigente no mide oferta, originaciones ni personas con acceso.',
                  'TNA UVA y saldo PH representan poblaciones distintas; TNA no es CFT.',
                  'No hay etiquetas supervisadas, test intacto ni vintages verificados.',
                  'Retrospectiva no intervino en entrenamiento ni decisión.',
                  '50 no es neutralidad; punto R0/r0/g=0 del baseline vale 25.',
                  'Sin validación prospectiva de 12 meses no se habilita uso operativo.']}
    artifact['parametros_sha256']=b.hash_json({'referencias':refs,'pca':pca})
    artifact['modelo_id']=b.hash_json(artifact)[:20]
    # No aplicar retrospectiva antes de cerrar modelo y decisión.
    scores=b.aplicar_baseline_icc(frame,refs,roles=('train','validacion'))
    mask=scores['utilizable_baseline']
    scores['factor_pca_diagnostico']=np.nan
    scores['icc_pca_candidato']=np.nan
    if pca is not None:
        f,_,P=score_factor(frame.loc[mask],refs,pca)
        scores.loc[mask,'factor_pca_diagnostico']=f
        if gates['cargas_pca']['pasa']:
            scores.loc[mask,'icc_pca_candidato']=P
    scores['icc_indice']=scores['icc_pca_candidato'] if accepted else scores['icc_baseline_s1']
    scores['metodo_elegido']=artifact['metodo_elegido']
    scores['modelo_id']=artifact['modelo_id']
    return artifact,scores


def render_informe(model, scores):
    def fmt(v):
        if v is None:return 'No definido'
        if isinstance(v,float):return f'{v:.4f}'
        return html.escape(str(v))
    def table(headers,rows):
        return '<table><tr>'+''.join('<th>'+html.escape(h)+'</th>' for h in headers)+'</tr>'+''.join(
            '<tr>'+''.join('<td>'+fmt(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</table>'
    def resumen_comparacion(c, role):
        v=c.get('comparaciones',{}).get(role,{})
        if not v:return c.get('motivo','No definido')
        return f"rho {fmt(v['spearman'])} / MAE {fmt(v['mae'])}"
    gates=model['gates']
    pca=model['parametros_pca']
    verdict='PCA aceptado para el experimento' if model['pca_aceptado'] else 'PCA rechazado; se utiliza el baseline experimental'
    output=['<!doctype html><html lang="es"><meta charset="utf-8"><title>ICC — implementación S1</title>',
            '<style>body{font:17px system-ui;max-width:1100px;margin:40px auto;padding:0 24px;color:#142a38}table{border-collapse:collapse;width:100%;margin:20px 0}td,th{border:1px solid #ccc;padding:10px;text-align:left}h1,h2{color:#175a72}pre{white-space:pre-wrap;font-size:13px}svg{width:100%;height:auto}</style>',
            '<h1>ICC hipotecario: implementación S1</h1><h2>'+verdict+'</h2>',
            '<p>Modelo '+model['modelo_id']+'. '+model['estado_baseline']+'. Train: '+str(gates['cobertura']['n_train'])+
            ' meses; validación: '+str(gates['cobertura']['n_validacion'])+'. Reserva sin score.</p>',
            '<p>El índice combina volumen de crédito real, costo y dinámica. No mide cuántas personas acceden al crédito. '
            'Los umbrales y la fórmula se fijaron antes de esta corrida y no se ajustaron para mejorar el resultado.</p>',
            '<h2>Qué se implementó y qué se aprendió</h2><p>B = 100 × V × (0,80 C + 0,20 M). '
            'V = R/(R+R₀), C = logística((r₀−r)/sᵣ), M = logística(g₃/s𝗀). '
            'Pesos y pisos son criterios normativos; medianas y escalas se aprenden solo en los meses comunes de train. '
            'R=R₀, r=r₀ y g=0 produce 25; 50 no significa neutralidad ni probabilidad.</p>',
            table(['Parámetro aprendido','Valor'],[(k,model['referencias'][k]) for k in ('R0','r0','sr','sg')]),
            '<h2>Controles y decisión</h2>',table(['Control','Resultado'],[(k,'PASA' if v['pasa'] else 'FALLA') for k,v in gates.items()]),
            '<p>Motivos de rechazo: '+html.escape(', '.join(model['motivos_rechazo_pca']) or 'ninguno')+'. '
            'Un fallo conserva su evidencia. No se cambiaron pesos, cortes ni mínimos.</p>',
            '<h2>Sensibilidad del baseline</h2>',
            table(['Variante','Valor/escala','Train rho / MAE','Validación rho / MAE','Resultado'],[
                (c['variante'],c.get('valor',c.get('escala_train','—')),
                 resumen_comparacion(c, 'train'), resumen_comparacion(c, 'validacion'),
                 'PASA' if c['pasa'] else 'FALLA') for c in gates['sensibilidad_baseline']['variantes']])]
    if pca is not None:
        output+=['<h2>Qué aprendió el PCA</h2>',
                 table(['Componente','Carga orientada','Fracción L1'],[(label,pca['cargas'][i],gates['cargas_pca']['participaciones_l1'][i])
                         for i,label in enumerate(['Volumen','Costo','Momentum'])]),
                 '<p>Varianza explicada: '+fmt(pca['varianza_explicada'])+'. Una carga negativa conserva su signo; '
                 'si la dirección no es válida, el factor se mantiene como diagnóstico y no genera un ICC candidato.</p>',
                 '<h2>Reconstrucción: utilidad descriptiva</h2>',
                 table(['Bloque','MSE baseline','MSE PCA','Mejora relativa','Ratios por columna'],[
                     (role,metrics['mse_baseline'],metrics['mse_pca'],metrics['mejora_relativa'],metrics['ratios_por_columna'])
                     for role,metrics in gates['reconstruccion']['metricas'].items() if isinstance(metrics,dict)]),
                 '<p>Se exige 10% menos MSE en validación y ningún input más de 25% peor. '
                 'Estas métricas reconstruyen las entradas; no demuestran acceso ni precisión económica.</p>',
                 '<h2>Saturación y perturbaciones</h2><pre>'+html.escape(json.dumps(
                     {k:gates[k] for k in ('saturacion','perturbaciones_pca')},ensure_ascii=False,indent=2))+'</pre>']
    usable=scores.loc[scores['utilizable_baseline']]
    if not usable.empty:
        ys=usable['icc_indice'].to_numpy(float);w=950;h=240
        points=' '.join(f'{40+i*(w-80)/max(len(ys)-1,1):.2f},{h-30-y*(h-60)/100:.2f}' for i,y in enumerate(ys))
        output+=['<h2>Índice experimental: train y validación</h2><svg viewBox="0 0 950 240" role="img" aria-label="Índice S1 de 0 a 100">'
            '<path d="M40 30 V210 H910" fill="none" stroke="#888"/><text x="4" y="36">100</text><text x="18" y="210">0</text>'
            '<polyline points="'+points+'" fill="none" stroke="#187798" stroke-width="3"/></svg>',
            '<p>'+html.escape(usable['fecha_mes'].iloc[0])+' a '+html.escape(usable['fecha_mes'].iloc[-1])+'. '
            'Escala fija 0–100. Retrospectiva se publica por separado después de cerrar la decisión.</p>']
    output+=['<h2>Alcance y siguiente paso</h2><ul>'+''.join('<li>'+html.escape(x)+'</li>' for x in model['limitaciones'])+'</ul>',
             '<p>La entrada se auditó por identidades internas. Fuentes originales reconstruidas: '+str(model['fuente'].get('fuentes_reconstruidas',False))+'. '
             'Con este CSV independiente no se certifica nuevamente el IPC de origen. Se guarda el modelo en JSON, '
             'con código, entorno, muestra y decisión trazables. Scoring reutiliza estas referencias sin entrenar.</p></html>']
    return ''.join(output)


def exportar_entrenamiento(model,scores,output):
    files={'icc_entrenamiento.csv':scores.to_csv(index=False).encode(),
           'informe_entrenamiento.html':render_informe(model,scores).encode()}
    return b.publicar_bundle(output,files,'modelo_icc.json',model)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--method', choices=('pca','factor_analysis','pca2'), default='pca',
                        help='Candidato explícito: PCA1 4.0, FA1 4.1 o diagnóstico PCA2 4.2.')
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--input',type=Path)
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args()
    frame,source=b.cargar_entrada(args.root,args.input)
    if args.method=='pca2':
        from ml import pca2
        model,diagnostico=pca2.entrenar_icc(frame,source)
        output=args.output_dir or b.directorio_modelo(args.root,frame).parent/'v4.2'/'entrenamiento_pca2'
        pca2.exportar_entrenamiento(model,diagnostico,output)
        print(json.dumps({'salida':str(output),'controles_diagnosticos_pasan':model['controles_diagnosticos_pasan'],
                          'indice_pca2_definido':False,'metodo_indice':'baseline_s1'},ensure_ascii=False))
        return
    if args.method=='factor_analysis':
        from ml import factor
        model,scores=factor.entrenar_icc(frame,source)
        output=args.output_dir or b.directorio_modelo(args.root,frame).parent/'v4.1'/'entrenamiento_fa'
        factor.exportar_entrenamiento(model,scores,output)
        print(json.dumps({'salida':str(output),'metodo':model['metodo_elegido'],
                          'factor_aceptado':model['factor_aceptado'],
                          'motivos':model['motivos_rechazo_factor']},ensure_ascii=False))
        return
    model,scores=entrenar_icc(frame,source)
    output=args.output_dir or b.directorio_modelo(args.root,frame)/'entrenamiento'
    exportar_entrenamiento(model,scores,output)
    print(json.dumps({'salida':str(output),'metodo':model['metodo_elegido'],
                      'pca_aceptado':model['pca_aceptado'],'motivos':model['motivos_rechazo_pca']},ensure_ascii=False))


if __name__=='__main__':
    main()
