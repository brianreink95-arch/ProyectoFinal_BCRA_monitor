"""ICC 4.1: análisis factorial de un factor, candidato experimental posterior a S1.

Reutiliza R/g3/r, referencias, fórmula de volumen y cortes S1. Se distingue
carga generativa L de peso posterior w: f=(Z-mu)w; reconstrucción=mu+fL.
No busca hiperparámetros ni reemplaza silenciosamente el experimento PCA.
"""
from pathlib import Path
import hashlib
import html
import json
import warnings

import numpy as np
import pandas as pd
import sklearn
from sklearn.decomposition import FactorAnalysis
from sklearn.exceptions import ConvergenceWarning

from ml import baseline as b
from ml import train as t

VERSION_FACTOR='4.1'
CONFIG_FA={
    'metodo':'factor_analysis', 'version':VERSION_FACTOR,'adopcion_local':'2026-10-06',
    'config_baseline':b.CONFIG_S1, 'n_components':1,'svd_method':'lapack',
    'rotation':None,'tol':.01,'max_iter':1000,'noise_variance_init':None,
    'orientacion':'un signo global: costo positivo',
    'min_l1_cargas':[.20,.20,.10],'min_l1_pesos_score':[.20,.20,.10],
    'mapping':'100*V*logistica((f-mediana_train_f)/escala_train_f)',
    'comparacion':'exploratoria: validacion ya utilizada en PCA',
    'perturbacion_coseno':'pesos efectivos en Z original: D*w_perturbado',
    'convergencia':'sin ConvergenceWarning; parámetros finitos, psi>0, factor variable',
}


def pesos_posteriores(loadings, noise):
    L=np.asarray(loadings,float);psi=np.asarray(noise,float)
    if L.shape!=(3,) or psi.shape!=(3,) or not np.isfinite([L,psi]).all() or (psi<=0).any():
        raise ValueError('Cargas/varianza propia inválidas.')
    return (L/psi)/(1+float(np.sum(L*L/psi)))


def ajustar_factor(Z):
    """Fit determinista; advertencia de no convergencia permanece visible."""
    estimator=FactorAnalysis(n_components=1,svd_method='lapack',rotation=None,
                             tol=.01,max_iter=1000,noise_variance_init=None)
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter('always',ConvergenceWarning)
        estimator.fit(np.asarray(Z,float))
    L=estimator.components_[0].copy()
    orientation=1. if L[1]>=0 else -1.
    L*=orientation
    psi=estimator.noise_variance_.copy()
    w=pesos_posteriores(L,psi)
    f=(Z-estimator.mean_)@w
    good=bool(np.isfinite(f).all() and np.std(f)>1e-12 and
              not any(issubclass(x.category,ConvergenceWarning) for x in captured))
    total=L**2+psi
    return {'algoritmo':'factor_analysis','cargas':L.tolist(),'pesos_score':w.tolist(),
            'varianza_propia':psi.tolist(),'centro_factor':estimator.mean_.tolist(),
            'f0':float(np.median(f)),'sf':b.escala(f,1e-6),'n_iter':int(estimator.n_iter_),
            'convergio':good,'advertencias':[str(x.message) for x in captured],
            'comunalidades':(L**2/total).tolist(),
            'loglike_final':float(estimator.loglike_[-1]),
            'svd_method':'lapack','rotation':None,'tol':.01,'max_iter':1000,'n_components':1,
            'grados_libertad_covarianza':0}


def direcciones(factor):
    loads=t.cargas_admisibles(factor['cargas'])
    weights=t.cargas_admisibles(factor['pesos_score'])
    return {'pasa':loads['pasa'] and weights['pasa'],
            'cargas_generativas':loads,'pesos_efectivos_score':weights}


def perturbaciones(train,val,refs,factor):
    mean=np.asarray(factor['media_y_train']);std=np.asarray(factor['std_y_train'])
    Z=(t.transformar(train,refs)-mean)/std
    Zv=(t.transformar(val,refs)-mean)/std
    V=val[b.STOCK_REAL].to_numpy(float)/(val[b.STOCK_REAL].to_numpy(float)+refs['R0'])
    base=t.score_factor(val,refs,factor)[2]
    w=np.asarray(factor['pesos_score']);results=[]
    for j in range(3):
        for multiplier in (.9,1.1):
            D=np.ones(3);D[j]=multiplier
            alt=ajustar_factor(Z*D)
            mapped_w=np.asarray(alt['pesos_score'])*D
            mapped_L=np.asarray(alt['cargas'])/D
            norm=np.linalg.norm(mapped_w)*np.linalg.norm(w)
            cosine=float(mapped_w@w/norm) if norm>0 else None
            f=t.proyectar(Zv*D,alt)
            P=100*V*b.logistica((f-alt['f0'])/alt['sf'])
            correlation=t.rho(base,P)
            direction=t.cargas_admisibles(mapped_w)['pasa'] and t.cargas_admisibles(mapped_L)['pasa']
            results.append({'columna':['volumen','costo','momentum'][j],
                            'multiplicador':multiplier,'convergio':alt['convergio'],
                            'pesos_score_original_z':mapped_w.tolist(),
                            'cargas_original_z':mapped_L.tolist(),'coseno':cosine,
                            'spearman_val':correlation,'direccion_admisible':direction,
                            'pasa':bool(alt['convergio'] and direction and cosine is not None and
                                        cosine>=.95 and correlation is not None and correlation>=.90)})
    return {'pasa':all(x['pasa'] for x in results),'casos':results,
            'nota':'FA estima ruido por variable: cambios de escala pueden ser absorbidos; este control no prueba estabilidad temporal.'}


def renombrar_metricas(obj):
    if isinstance(obj,dict):return {k.replace('pca','factor'):renombrar_metricas(v) for k,v in obj.items()}
    if isinstance(obj,list):return [renombrar_metricas(x) for x in obj]
    return obj


def entrenar_icc(frame,source=None):
    refs=b.ajustar_referencias_icc(frame)
    split=b.asignar_splits_icc(frame);core=b.mascara_core(frame)
    train=frame.loc[split.eq('train')&core];val=frame.loc[split.eq('validacion')&core]
    if len(val)<18:raise ValueError('Validacion insuficiente: mínimo 18 meses.')
    economic=b.controles_economicos(refs)
    if not economic['pasa']:raise ValueError('Baseline no pasa escenarios económicos.')
    sensitivities=t.sensibilidades_baseline(train,val,refs)
    Y=t.transformar(train,refs);mean=Y.mean(axis=0);std=Y.std(axis=0,ddof=0)
    gates={'cobertura':{'pasa':True,'n_train':len(train),'n_validacion':len(val)},
           'economia_baseline':economic,'sensibilidad_baseline':sensitivities,
           'variacion_factor':{'pasa':bool(np.isfinite(std).all() and (std>1e-12).all()),
                               'std_y_train':std.tolist()}}
    factor=None
    if gates['variacion_factor']['pasa']:
        factor={**ajustar_factor((Y-mean)/std),'media_y_train':mean.tolist(),'std_y_train':std.tolist()}
        gates['convergencia_factor']={'pasa':factor['convergio'],'n_iter':factor['n_iter'],
                                      'advertencias':factor['advertencias']}
        gates['direccion_factor']=direcciones(factor)
        gates['economia_factor']=t.escenarios_pca(refs,factor)
        gates['perturbaciones_factor']=perturbaciones(train,val,refs,factor)
        gates['reconstruccion']=renombrar_metricas(t.reconstruccion(train,val,refs,factor))
        gates['saturacion']=t.saturacion(val,refs,factor)
    accepted=bool(factor is not None and all(x['pasa'] for x in gates.values()))
    model={'schema':'icc_fa_modelo_4.1','config_fa':CONFIG_FA,'referencias':refs,
           'protocolo':b.comprobar_protocolo_icc(frame),'fuente':source or {'fuentes_reconstruidas':False},
           'parametros_factor':factor,'gates':gates,'factor_aceptado':accepted,
           'metodo_elegido':'factor_analysis' if accepted else 'baseline_s1',
           'motivos_rechazo_factor':[k for k,v in gates.items() if not v['pasa']],
           'estado_baseline':'experimental' if sensitivities['pasa'] else 'experimental_sensible',
           'estado_producto':'experimental','disponibilidad_historica_verificada':False,
           'validacion_sha256':b.hash_bloque(val),
           'entorno':{**b.runtime_metadata(),'scikit_learn':sklearn.__version__},
           'codigo_sha256':{name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest()
                            for name in ('baseline.py','train.py','score.py','factor.py')},
           'limitaciones':['Saldo y TNA son proxies de poblaciones distintas; no acceso individual ni CFT.',
                           'La validación ya se usó para PCA; comparación exploratoria, sin test intacto.',
                           'Tres variables y un factor: cero grados de libertad de covarianza; no prueba de ajuste confirmatoria.',
                           'Perturbar escalas en FA puede ser absorbido por su ruido propio: no equivale a probar estabilidad temporal.',
                           'Sin vintages ni validación prospectiva; no habilita uso operativo.']}
    model['parametros_sha256']=b.hash_json({'referencias':refs,'factor':factor})
    model['modelo_id']=b.hash_json(model)[:20]
    scores=generar_indice(frame,model,roles=('train','validacion'))
    return model,scores


def validar_modelo(model):
    if model.get('schema')!='icc_fa_modelo_4.1' or b.hash_json(model.get('config_fa'))!=b.hash_json(CONFIG_FA):
        raise ValueError('Configuración FA incompatible.')
    original={k:v for k,v in model.items() if k not in ('modelo_id','archivos_sha256')}
    if model.get('modelo_id')!=b.hash_json(original)[:20]:raise ValueError('Integridad FA inválida.')
    refs=model['referencias'];b.validar_referencias(refs)
    dates=refs['fechas_train']
    if (len(dates)!=refs['n_train'] or len(set(dates))!=len(dates) or dates!=sorted(dates)
        or not all(b.CORTES_ICC['train'][0]<=d<=b.CORTES_ICC['train'][1] for d in dates)):
        raise ValueError('Muestra FA fuera del protocolo.')
    gates=model['gates'];factor=model['parametros_factor']
    required={'cobertura','economia_baseline','sensibilidad_baseline','variacion_factor'}
    if factor is not None:
        required|={'convergencia_factor','direccion_factor','economia_factor','perturbaciones_factor','reconstruccion','saturacion'}
        for key in ('cargas','pesos_score','varianza_propia','centro_factor','media_y_train','std_y_train'):
            x=np.asarray(factor[key],float)
            if x.shape!=(3,) or not np.isfinite(x).all():raise ValueError('Vector FA inválido: '+key)
        if (np.asarray(factor['std_y_train'])<=1e-12).any() or factor['sf']<1e-6 or not np.isfinite([factor['f0'],factor['sf']]).all():
            raise ValueError('Escala FA inválida.')
        if not np.allclose(factor['pesos_score'],pesos_posteriores(factor['cargas'],factor['varianza_propia']),rtol=1e-12,atol=1e-12):
            raise ValueError('Pesos posteriores FA inconsistentes.')
        if any(factor[k]!=CONFIG_FA[k] for k in ('svd_method','rotation','tol','max_iter','n_components')):
            raise ValueError('Algoritmo distinto del FA acordado.')
        if gates['direccion_factor']['pasa']!=direcciones(factor)['pasa']:
            raise ValueError('Dirección FA inconsistente.')
        if gates['convergencia_factor']['pasa']!=factor['convergio']:
            raise ValueError('Convergencia FA inconsistente.')
    if set(gates)!=required or not all(isinstance(v.get('pasa'),bool) for v in gates.values()):
        raise ValueError('Controles FA faltantes o inválidos.')
    if not gates['cobertura']['pasa'] or not gates['economia_baseline']['pasa']:
        raise ValueError('Baseline no habilitado.')
    accepted=factor is not None and all(v['pasa'] for v in gates.values())
    if model['factor_aceptado']!=accepted or model['metodo_elegido']!=('factor_analysis' if accepted else 'baseline_s1'):
        raise ValueError('FA pretende saltar controles.')
    if set(model['motivos_rechazo_factor'])!={k for k,v in gates.items() if not v['pasa']}:
        raise ValueError('Motivos FA inconsistentes.')
    if model['parametros_sha256']!=b.hash_json({'referencias':refs,'factor':factor}):
        raise ValueError('Hash de parámetros FA incompatible.')
    return model


def generar_indice(frame,model,roles=None):
    validar_modelo(model)
    refs=model['referencias'];out=b.aplicar_baseline_icc(frame,refs,roles)
    usable=out['utilizable_baseline'];factor=model['parametros_factor']
    out['factor_fa_diagnostico']=np.nan;out['icc_fa_candidato']=np.nan
    if factor is not None:
        f,_,P=t.score_factor(frame.loc[usable],refs,factor)
        out.loc[usable,'factor_fa_diagnostico']=f
        if model['gates']['direccion_factor']['pasa'] and model['gates']['convergencia_factor']['pasa']:
            out.loc[usable,'icc_fa_candidato']=P
    out['icc_indice']=out['icc_fa_candidato'] if model['factor_aceptado'] else out['icc_baseline_s1']
    out['metodo_elegido']=model['metodo_elegido'];out['version_modelo']=VERSION_FACTOR
    out['estado_producto']='fa_experimental' if model['factor_aceptado'] else model['estado_baseline']
    out['motivos_rechazo_factor']=';'.join(model['motivos_rechazo_factor']);out['modelo_id']=model['modelo_id']
    train=frame.loc[b.asignar_splits_icc(frame).eq('train')&b.mascara_core(frame)]
    out['historia_train_coincide']=b.hash_bloque(train)==refs['train_sha256']
    for feature,(lo,hi) in refs['rangos_train'].items():
        out['fuera_rango_train_'+feature]=frame[feature].notna()&(~frame[feature].between(lo,hi))
    out['icc_delta_1m_pp']=out['icc_indice'].diff();b.validar_baseline_icc(out)
    return out


def render_informe(model):
    def fmt(x):
        if isinstance(x,float):return f'{x:.4f}'
        return html.escape(str(x))
    def table(headers,rows):
        return '<table><tr>'+''.join('<th>'+html.escape(h)+'</th>' for h in headers)+'</tr>'+''.join('<tr>'+''.join('<td>'+fmt(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</table>'
    gates=model['gates'];factor=model['parametros_factor']
    verdict='FA aceptado como experimento' if model['factor_aceptado'] else 'FA rechazado: el índice continúa con baseline S1'
    output=['<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>ICC — análisis factorial</title>',
            '<style>body{font:17px system-ui;max-width:1050px;margin:40px auto;padding:0 24px;color:#142a38}table{border-collapse:collapse;width:100%;margin:20px 0}th,td{border:1px solid #ccd;padding:10px;text-align:left}h1,h2{color:#175a72}pre{white-space:pre-wrap}</style>',
            '<h1>ICC: análisis factorial de un factor</h1><h2>'+verdict+'</h2>',
            '<p>Método 4.1. Train: '+str(gates['cobertura']['n_train'])+' meses; validación: '+str(gates['cobertura']['n_validacion'])+'. Modelo '+model['modelo_id']+'.</p>',
            '<p>Buscamos una señal común de volumen, costo y dinámica. Se conservaron el baseline, las referencias, los cortes y los umbrales económicos de S1. '
            'No se buscaron hiperparámetros ni se modificaron controles para aceptar el resultado.</p>',
            '<h2>Decisiones anteriores a la ejecución</h2><p>FA1, solver LAPACK, sin rotación, tolerancia 0,01 y máximo 1.000 iteraciones. '
            'Las entradas son log1p(R/R₀), −r y asinh(g/s𝗀), con escala aprendida solo en train. '
            'El score propuesto es 100 × V × logística((f−f₀)/s_f), con el mismo límite de bajo volumen. '
            'Cargas y pesos efectivos deben ser positivos y sus fracciones mínimas son 20%/20%/10%. '
            'Todos los controles deben pasar para sustituir el baseline.</p>',
            '<h2>Controles</h2>',table(['Control','Resultado'],[(k,'PASA' if v['pasa'] else 'FALLA') for k,v in gates.items()]),
            '<p>Motivos de rechazo: '+html.escape(', '.join(model['motivos_rechazo_factor']) or 'ninguno')+'.</p>']
    if factor is not None:
        direction=gates['direccion_factor']
        output+=['<h2>Cargas, ruido propio y pesos del score</h2><p>Las cargas L explican cómo cada input se relaciona con el factor. '
                 'El cálculo del factor usa pesos posteriores w=(L/ψ)/(1+ΣL²/ψ), que también dependen del ruido ψ. '
                 'Por eso revisar solo las cargas no asegura que todas las señales participen en el índice.</p>',
                 table(['Señal','Carga L','Ruido ψ','Peso score w','Fracción L1 carga','Fracción L1 score','Comunalidad'],[
                     (label,factor['cargas'][i],factor['varianza_propia'][i],factor['pesos_score'][i],
                      (direction['cargas_generativas']['participaciones_l1'] or [None]*3)[i],
                      (direction['pesos_efectivos_score']['participaciones_l1'] or [None]*3)[i],factor['comunalidades'][i])
                     for i,label in enumerate(['Volumen','Costo','Momentum'])]),
                 '<p>Iteraciones: '+str(factor['n_iter'])+'. Convergencia: '+str(factor['convergio'])+'. '
                 'Comunalidad es la fracción de varianza modelada atribuida al factor; no mide acceso.</p>',
                 '<h2>Reconstrucción de entradas</h2>',
                 table(['Bloque','MSE baseline','MSE FA','Mejora relativa','Ratios FA/baseline por input'],[
                     (k,v['mse_baseline'],v['mse_factor'],v['mejora_relativa'],v['ratios_por_columna'])
                     for k,v in gates['reconstruccion']['metricas'].items() if isinstance(v,dict)]),
                 '<p>Exigencia: mejora media ≥10% en validación y ningún input con ratio de error >1,25. '
                 'Esto compara representación de las entradas, no precisión económica ni accesibilidad.</p>',
                 '<h2>Seis perturbaciones de escala</h2>',
                 table(['Columna','Multiplicador','Coseno pesos originales','Spearman val','Dirección','Resultado'],[
                     (x['columna'],x['multiplicador'],x['coseno'],x['spearman_val'],x['direccion_admisible'],x['pasa'])
                     for x in gates['perturbaciones_factor']['casos']]),
                 '<p>'+html.escape(gates['perturbaciones_factor']['nota'])+'</p>',
                 '<h2>Saturación latente</h2><p>'+str(gates['saturacion']['meses_latente'])+'/'+str(gates['saturacion']['n_validacion'])+' meses. Máximo: 10%.</p>']
    output+=['<h2>Baseline y siguientes decisiones</h2><p>Las nueve sensibilidades del baseline: '+('PASA' if gates['sensibilidad_baseline']['pasa'] else 'FALLA')+'. '
             'Si FA falla dirección/convergencia se publica solo su factor diagnóstico; la columna de ICC candidato queda nula. '
             'El índice seleccionado sigue siendo baseline S1 experimental.</p>',
             '<h2>Alcance</h2><ul>'+''.join('<li>'+html.escape(x)+'</li>' for x in model['limitaciones'])+'</ul>',
             '<p>Fuentes reconstruidas: '+str(model['fuente'].get('fuentes_reconstruidas',False))+'. '
             'Retrospectiva solo se aplica tras cerrar la decisión; reserva sin score. 50 no es neutralidad.</p></html>']
    return ''.join(output)


def exportar_entrenamiento(model,scores,output):
    return b.publicar_bundle(output,{'icc_entrenamiento.csv':scores.to_csv(index=False).encode(),
                                    'informe_factorial.html':render_informe(model).encode()},
                            'modelo_icc.json',model)
